#define _GNU_SOURCE

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/module.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <time.h>
#include <unistd.h>

static int wait_for_path(const char *path, int timeout_ms) {
  const int interval_ms = 50;
  int waited = 0;
  struct stat st;
  while (stat(path, &st) != 0) {
    if (errno != ENOENT)
      return -1;
    if (waited >= timeout_ms)
      return -1;
    struct timespec ts = {
        .tv_sec = interval_ms / 1000,
        .tv_nsec = (long)(interval_ms % 1000) * 1000000L,
    };
    nanosleep(&ts, NULL);
    waited += interval_ms;
  }
  return 0;
}

int main(int argc, char **argv, char **envp) {
  int e;

  int cmdline = open("/dev/cmdline", O_RDONLY);
  char line_buf[1024] = {0};
  read(cmdline, line_buf, sizeof(line_buf));
  close(cmdline);

  printf("init: Command line: %s\n", line_buf);

  insertmod("/usr/share/zinnia/modules/nvme.kso", NULL);
  insertmod("/usr/share/zinnia/modules/ext2.kso", NULL);
  insertmod("/usr/share/zinnia/modules/virtio_gpu.kso", NULL);
  insertmod("/usr/share/zinnia/modules/virtio_net.kso", NULL);

  printf("init: Mounting ext2 root partition on /realfs\n");

  // Mount the root partition
  // TODO: Don't use a fixed uuid for this.
  const char *root_dev =
      "/dev/block/parttype-0fc63daf-8483-4772-8e79-3d69d8477de4";
  if (wait_for_path(root_dev, 10000) != 0) {
    fprintf(stderr, "init: timed out waiting for root device %s\n", root_dev);
    return 1;
  }
  e = mount("ext2", "/realfs", 0, root_dev);
  if (e)
    return e;

  printf("init: Switching to new root\n");

  // Switch root
  e = chroot("/realfs");
  if (e)
    return e;
  e = chdir("/");

  printf("init: Mounting devtmpfs on /dev\n");

  // Mount devtmpfs
  e = mount("devtmpfs", "/dev", 0, NULL);
  if (e)
    return e;

  printf("init: Mounting tmpfs on /tmp\n");

  // Mount devtmpfs
  e = mount("tmpfs", "/tmp", 0, NULL);
  if (e)
    return e;

  e = mount("tmpfs", "/var/run", 0, NULL);
  if (e)
    return e;

  // Parse rd.init= from kernel command line
  const char *init_path = "/usr/bin/dinit";
  const char *prefix = "rd.init=";
  size_t prefix_len = strlen(prefix);
  static char init_buf[256];

  char *p = line_buf;
  while (*p) {
    if (strncmp(p, prefix, prefix_len) == 0) {
      p += prefix_len;
      size_t i = 0;
      while (*p && *p != ' ' && i < sizeof(init_buf) - 1)
        init_buf[i++] = *p++;
      init_buf[i] = '\0';
      init_path = init_buf;
      break;
    }
    while (*p && *p != ' ')
      p++;
    while (*p == ' ')
      p++;
  }

  printf("init: Running init from disk: %s\n", init_path);

  char *argv_new[] = {(char *)init_path, NULL};
  char *envp_new[] = {
      "TERM=xterm-256color",
      "HOME=/root",
      "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
      NULL,
  };

  e = execve(init_path, argv_new, envp_new);
  if (e) {
    perror("execve");
    return e;
  }

  return 1;
}

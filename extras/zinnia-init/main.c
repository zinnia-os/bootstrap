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

#define MODULES_DIR "/usr/share/zinnia/modules"

static int is_blacklisted(const char *name, const char *cmdline) {
  const char *prefix = "rd.blacklist=";
  size_t prefix_len = strlen(prefix);
  size_t name_len = strlen(name);

  const char *p = cmdline;
  while (*p) {
    if (strncmp(p, prefix, prefix_len) == 0) {
      const char *val = p + prefix_len;
      if (strncmp(val, name, name_len) == 0 &&
          (val[name_len] == '\0' || val[name_len] == ' '))
        return 1;
    }
    while (*p && *p != ' ')
      p++;
    while (*p == ' ')
      p++;
  }
  return 0;
}

static void load_modules(const char *cmdline) {
  DIR *dir = opendir(MODULES_DIR);
  if (!dir) {
    perror("init: opendir modules");
    return;
  }

  struct dirent *ent;
  while ((ent = readdir(dir)) != NULL) {
    size_t len = strlen(ent->d_name);
    if (len < 5 || strcmp(ent->d_name + len - 4, ".kso") != 0)
      continue;

    size_t base_len = len - 4;
    char *name = malloc(base_len + 1);
    if (!name)
      continue;
    memcpy(name, ent->d_name, base_len);
    name[base_len] = '\0';

    if (is_blacklisted(name, cmdline)) {
      printf("init: Skipping blacklisted module %s\n", name);
      free(name);
      continue;
    }

    char path[512];
    snprintf(path, sizeof(path), "%s/%s", MODULES_DIR, ent->d_name);
    printf("init: Loading module %s\n", name);
    if (insertmod(path, NULL) != 0)
      fprintf(stderr, "init: failed to load %s: %s\n", path, strerror(errno));
    free(name);
  }

  closedir(dir);
}

static const char *cmdline_option(const char *cmdline, const char *key,
                                  char *out, size_t size) {
  size_t key_len = strlen(key);

  const char *p = cmdline;
  while (*p) {
    if (strncmp(p, key, key_len) == 0) {
      const char *val = p + key_len;
      size_t i = 0;
      while (*val && *val != ' ' && *val != '\n' && i < size - 1)
        out[i++] = *val++;
      out[i] = '\0';
      return out;
    }
    while (*p && *p != ' ')
      p++;
    while (*p == ' ')
      p++;
  }
  return NULL;
}

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

  load_modules(line_buf);

  static char root_buf[256];
  static char root_path[320];
  static char fstype_buf[64];

  const char *root_dev =
      "/dev/block/parttype-0fc63daf-8483-4772-8e79-3d69d8477de4";
  const char *root_spec =
      cmdline_option(line_buf, "root=", root_buf, sizeof(root_buf));
  if (root_spec) {
    if (strncmp(root_spec, "PARTUUID=", 9) == 0) {
      snprintf(root_path, sizeof(root_path), "/dev/block/partuuid-%s",
               root_spec + 9);
      root_dev = root_path;
    } else {
      root_dev = root_spec;
    }
  }

  const char *root_fstype =
      cmdline_option(line_buf, "rootfstype=", fstype_buf, sizeof(fstype_buf));
  if (!root_fstype)
    root_fstype = "ext2";

  printf("init: Mounting %s root %s on /realfs\n", root_fstype, root_dev);

  // Mount the root partition
  if (wait_for_path(root_dev, 10000) != 0) {
    fprintf(stderr, "init: timed out waiting for root device %s\n", root_dev);
    return 1;
  }
  e = mount(root_fstype, "/realfs", 0, root_dev);
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

  printf("init: Mounting tmpfs on /dev/shm\n");

  mkdir("/dev/shm", 01777);
  e = mount("tmpfs", "/dev/shm", 0, NULL);
  if (e)
    return e;

  // Parse rd.init= from kernel command line
  static char init_buf[256];
  const char *init_path =
      cmdline_option(line_buf, "rd.init=", init_buf, sizeof(init_buf));
  if (!init_path)
    init_path = "/usr/bin/dinit";

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

# bootstrap

This repository builds a fully bootable distribution for the
[Zinnia](https://github.com/zinnia-os/zinnia) kernel.

It also includes several ports of popular programs and tools.

## Prerequisites

To build the distribution you will need the following tools installed on your system:

- Bash
- GNU make
- curl
- wget
- zstd
- `unshare` (util-linux)
- `free` (procps)

To create a bootable image you will additionally need:

- dosfstools (for mkfs.vfat)
- e2fsprogs (for mkfs.ext2)
- sgdisk (for partitioning the image)
- build dependencies for the [xbps package manager](https://docs.voidlinux.org/xbps/index.html)


## Build instructions

You can either build everything from source, or download pre-built packages.

### Building from source

The easiest way to get a bootable image from source is to run:
```sh
$ make
```
in the root of the repository.
This will build a small subset of the distribution and create a bootable image
named `zinnia.img` in the build directory.

> [!NOTE]
> On some distributions, you may need to run the build command as root
> to fix a `file not found` error when bootstrap attempts to run `sgdisk`

You can also build separate packages by running `../jinx/jinx build <package>`
inside the respective build directory for the target architecture.

For example, to build the `zinnia` package for the x86_64 architecture, you would
run the following commands (assuming you are in the root of the repository):

```sh
$ cd build-x86_64           # Switch to the x86_64 build directory
$ ../jinx/jinx build zinnia # Build the zinnia package
$ sudo ../jinx/jinx install -f sysroot zinnia # Force install the package (sudo to preserve file attributes)
```

The built package will be located in the `pkgs` directory.

> [!WARNING]
> If you want a build of the **ENTIRE** distribution, you will need a lot of free disk space (>50GB) and some patience.

### Live installation medium

```sh
$ make live
```

builds `zinnia-live.img`, a bootable GPT image containing the graphical text
installer. Write it to a USB stick with `dd`:

```sh
$ sudo dd if=build-x86_64/zinnia-live.img of=/dev/sdX bs=4M status=progress conv=fsync
```

### Using pre-built packages

You can pull pre-built packages and host packages from our Buildbot workers into the build directory.

> [!NOTE]
> Host packages are only built to run on a x86_64 Linux host.
> If you're using an aarch64 machine, you'll have to build from source.

Example usage:

```sh
$ mkdir build-x86_64
$ cd build-x86_64
$ ../jinx/jinx init ..                # Setup build dir, pointing to the recipes in the parent
$ ../jinx/jinx download bash          # A single package and its dependencies
$ ../jinx/jinx download '*'           # Every target package
$ ../jinx/jinx download 'host:*'      # Every host package (toolchain etc.)
```

Downloads are checksum-verified against the repository index.
Afterwards, `make` will only build what is still missing.

## Running the image

Download the UEFI firmware once per architecture:

```sh
$ ./tasks/get-ovmf.sh x86_64
```

To run the image in QEMU, use `scripts/vm-util.py`:

```sh
$ ./scripts/vm-util.py run                # For zinnia.img
$ ./scripts/vm-util.py run --live         # For the live installation medium
```

`--live` attaches `build-x86_64/zinnia-live.img` as a USB disk and creates a
blank `zinnia.img` next to it to install onto.

This will run the image using QEMU with the appropriate options for the
target architecture. If you want to pass your own QEMU flags, you can do so
after a `--` separator, e.g.:

```sh
$ ./scripts/vm-util.py run -- -d int
```

See `./scripts/vm-util.py run --help` for all options, such as `--arch`,
`--smp`, `--mem`, `--headless`, `--nic` and `--pci`.

## Working on the kernel

The most common use case of bootstrap is working on the kernel itself.
It is recommended to build it once from source.

For quick iteration speeds, you can run `make remake-kernel image` to rebuild the kernel and install it in the image.

## Debugging

Run QEMU with a GDB stub and the CPU halted, with KVM disabled:

```sh
$ ./scripts/vm-util.py run --kvm off -- -s -S
```

and then attach your debugger.
For convenicence, there is a debugging configuration using CodeLLDB for VS Code.
Simply select Run > Start Debugging and use `.vscode/launch.json` as the config.

Remember to build the kernel in debug mode and make sure KASLR
has been disabled in the bootloader, or you have provided the debugger with the base address.

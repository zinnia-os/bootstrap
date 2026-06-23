# bootstrap

This repository builds a fully bootable distribution for the
[Zinnia](https://github.com/zinnia-os/zinnia) kernel.

It also includes several ports of popular programs and tools.

## Prerequisites

To build the distribution you will need the following tools installed on your system:

- Bash
- GNU make
- curl

To create a bootable image you will additionally need:

- dosfstools (for mkfs.vfat)
- e2fsprogs (for mkfs.ext2)
- sgdisk (for partitioning the image)

To run the built image you will also need QEMU for the target architecture.

## Build instructions

The easiest way to get a bootable image is to run

```sh
$ make
```

in the root of the repository.
This will build a small subset of the distribution and create a bootable image
named `zinnia.img` in the build directory.

> [!TIP]
> On some distributions, you may need to run the build command as root
> to fix a `file not found` error when bootstrap attempts to run `sgdisk`

You can also build separate packages by running `../jinx/jinx build <package>`
inside the respective build directory for the target architecture.

For example, to build the `zinnia` package for the x86_64 architecture, you would
run the following commands (assuming you are in the root of the repository):

```sh
$ cd build-x86_64           # Switch to the x86_64 build directory
$ ../jinx/jinx build zinnia # Build the zinnia package
```

The built package will be located in the `pkgs` directory.

If you want a build of the **ENTIRE** distribution, you will need a lot of
free disk space (>20GB) and some patience.

## Running the ISO/image

To run the ISO/image in qemu, you can use the provided make targets:

```sh
$ make qemu     # For zinnia.img
$ make qemu-iso # For zinnia.iso
```

This will run the image using QEMU with the appropriate options for the
target architecture. If you want to pass your own QEMU flags,
you can do so by setting the `QEMUFLAGS` variable, e.g.:

```sh
$ make qemu QEMUFLAGS="-s -d int"
```

## Debugging

To debug Zinnia, build a normal image, but make sure to also build the package
`zinnia-debug`.
The binary is unstripped and contains debuginfo.

Run QEMU with:

```sh
$ make qemu QEMUFLAGS="-s -S" KVM=0
```

and then attach your debugger.
For convenicence, there is a debugging configuration using CodeLLDB for VS Code.
Simply select Run > Start Debugging and use `.vscode/launch.json` as the config.

Finally, start the `zinnia-debug` kernel in the bootloader and make sure KASLR
has been disabled or you have provided the debugger with the base address.

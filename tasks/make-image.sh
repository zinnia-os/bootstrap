#!/bin/bash

set -e

SYSTEM_ROOT="$1"
INITRAMFS_PATH="$2"
OUTPUT_IMAGE="$3"
ARCH="$4"

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"
BUILD_DIR="$ROOT_DIR/build-$ARCH"

# Setup loop device
LOOPDEV=$(sudo losetup --find --show --partscan "$OUTPUT_IMAGE")
ESP_PART="${LOOPDEV}p1"
ROOT_PART="${LOOPDEV}p2"

cleanup() {
    # Unmount and detach loop device
    sudo umount "$tmpdir/root/boot" || true
    sudo umount "$tmpdir/root" || true
    sudo losetup -d "$LOOPDEV" || true
    sudo rm -rf "$tmpdir" || true
}

trap 'cleanup' EXIT

# Create temporary directories
tmpdir=$(sudo mktemp -d)
sudo mkdir -p "$tmpdir/root"
# Mount root partition
sudo mount "$ROOT_PART" "$tmpdir/root"
# Mount the ESP inside /boot
sudo mkdir -p "$tmpdir/root/boot"
# FAT has no UIDs, so simulate a user, otherwise cp will complain.
sudo mount -o uid=1000,gid=1000 "$ESP_PART" "$tmpdir/root/boot"
# Create ESP directory layout
sudo mkdir -p "$tmpdir/root/boot/EFI/BOOT"

# Copy system root
sudo rsync -avr --checksum "$SYSTEM_ROOT/" "$tmpdir/root"

# Install kernel
sudo cp "$SYSTEM_ROOT/usr/share/zinnia/zinnia" "$tmpdir/root/boot/zinnia"

# Install initrd
sudo cp $INITRAMFS_PATH "$tmpdir/root/boot/initramfs.tar"

# Install bootloader
efi_filename=""
case "${ARCH}" in
    x86_64) efi_filename="BOOTX64.EFI" ;;
    aarch64) efi_filename="BOOTAA64.EFI" ;;
    riscv64) efi_filename="BOOTRISCV64.EFI" ;;
    loongarch64) efi_filename="BOOTLOONGARCH64.EFI" ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

sudo cp "$SYSTEM_ROOT/usr/share/limine/${efi_filename}" "$tmpdir/root/boot/EFI/BOOT/"

ROOT_GUID=$(sudo sgdisk -i 2 "$LOOPDEV" | sed -n 's/^Partition unique GUID: //p' | tr 'A-Z' 'a-z')
if [ -z "$ROOT_GUID" ]; then
    echo "Could not determine the root partition GUID"
    exit 1
fi

sed -e "s|@ROOT@|PARTUUID=${ROOT_GUID}|g" \
    "$ROOT_DIR/extras/zinnia-installer/limine.conf.in" |
    sudo tee "$tmpdir/root/boot/limine.conf" >/dev/null

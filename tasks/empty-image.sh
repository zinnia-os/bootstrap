#!/bin/bash

set -e

OUTPUT_IMAGE="$1"
IMAGE_SIZE="$2"
ESP_SIZE="$3"
ROOT_GUID="${4:-}"

# Create an empty disk image.
rm -f "$OUTPUT_IMAGE"
truncate -s $IMAGE_SIZE "$OUTPUT_IMAGE"

# Setup loop device
LOOPDEV=$(sudo losetup --find --show "$OUTPUT_IMAGE")
ESP_PART="${LOOPDEV}p1"
ROOT_PART="${LOOPDEV}p2"

cleanup() {
    sudo losetup -d "$LOOPDEV" 2>/dev/null || true
}
trap cleanup EXIT

# Wipe any existing GPT/MBR before laying down a fresh one.
sudo sgdisk --zap-all "$LOOPDEV" >/dev/null 2>&1 || true

# Create partitions
sudo sgdisk "$LOOPDEV" \
    --new=1:1M:+${ESP_SIZE} --typecode=1:C12A7328-F81F-11D2-BA4B-00A0C93EC93B \
    --new=2:0:0 --typecode=2:0FC63DAF-8483-4772-8E79-3D69D8477DE4

if [ -n "$ROOT_GUID" ]; then
    sudo sgdisk "$LOOPDEV" --partition-guid=2:"$ROOT_GUID"
fi

# Re-read partition table
sudo partprobe "$LOOPDEV"

# Format partitions
sudo mkfs.vfat -F 32 "$ESP_PART"
sudo mkfs.ext2 "$ROOT_PART"

#!/bin/bash

set -e

SYSTEM_ROOT="$1"
INITRAMFS_PATH="$2"
OUTPUT_IMAGE="$3"
ARCH="$4"

SCRIPT_DIR="$(dirname "$(realpath "$0")")"

ESP_SIZE=256M
ESP_SLACK_MIB=320
ROOT_SLACK_MIB=256
LIVE_ROOT_GUID="5a1f9c2e-7b64-4f0d-9a3e-2c8d6b1e4f70"

if [ ! -d "$SYSTEM_ROOT" ]; then
    echo "Live system root $SYSTEM_ROOT does not exist. Run 'make live-install' first"
    exit 1
fi

root_mib=$(sudo du -sm --apparent-size "$SYSTEM_ROOT" | cut -f1)
image_mib=$((root_mib + ROOT_SLACK_MIB + ESP_SLACK_MIB))

echo "Live system root is ${root_mib} MiB, building a ${image_mib} MiB image"

"$SCRIPT_DIR/empty-image.sh" "$OUTPUT_IMAGE" "${image_mib}M" "$ESP_SIZE" "$LIVE_ROOT_GUID"
"$SCRIPT_DIR/make-image.sh" "$SYSTEM_ROOT" "$INITRAMFS_PATH" "$OUTPUT_IMAGE" "$ARCH"

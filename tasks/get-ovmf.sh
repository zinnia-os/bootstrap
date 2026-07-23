#!/bin/bash

set -e

ARCH="${1:-x86_64}"

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
ROOT_DIR="$(realpath "$SCRIPT_DIR/..")"
OUTPUT="$ROOT_DIR/ovmf/ovmf-code-$ARCH.fd"

mkdir -p "$ROOT_DIR/ovmf"
curl -Lo "$OUTPUT" \
    "https://github.com/osdev0/edk2-ovmf-nightly/releases/download/nightly-2025-03-03/ovmf-code-$ARCH.fd"

# Pad the firmware to the size the machine model expects.
case "$ARCH" in
    aarch64) dd if=/dev/zero of="$OUTPUT" bs=1 count=0 seek=67108864 2>/dev/null ;;
    riscv64) dd if=/dev/zero of="$OUTPUT" bs=1 count=0 seek=33554432 2>/dev/null ;;
esac

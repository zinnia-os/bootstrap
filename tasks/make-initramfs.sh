#!/bin/bash

set -e

JINX="$(realpath $1)"
BUILD_DIR="$(realpath $2)"
INITRAMFS_DIR="$BUILD_DIR/initramfs"
INITRAMFS_PATH="$(realpath $3)"

# Make sure the initramfs doesn't already exist.
rm -f $INITRAMFS_PATH
mkdir -p $INITRAMFS_DIR

# Install all the programs we want in the initrd to the directory.
cd $BUILD_DIR

# We want these packages in the initramfs.
PKGS=(
    zinnia
    zinnia-init
)
$JINX install -f $INITRAMFS_DIR "${PKGS[@]}"

# `tar` operates on the CWD.
cd $INITRAMFS_DIR

# Create a symlink to init.
ln -fs usr/bin/zinnia-init init

# Create empty directories
mkdir -p realfs

# From those packages, create the initramfs with the following files.
FILES=(
    # Base directories
    realfs
    # Init
    init
    usr/bin/zinnia-init
)

# Kernel modules (optional because there may be none compiled).
shopt -s nullglob
FILES+=(usr/share/zinnia/modules/*)
shopt -u nullglob
echo "Installing:" ${FILES[@]}

tar --format=ustar --owner 0 --group 0 -cf $INITRAMFS_PATH "${FILES[@]}"

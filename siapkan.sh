#!/bin/sh
# siapkan.sh — mengambil aset biner yang dibutuhkan uji & rootfs
# ke folder aset/ (tidak ikut ke repo): BusyBox statis resmi dan
# alat uji hog yang dikompilasi dari hog.c.
set -e
cd "$(dirname "$0")"
mkdir -p aset
if [ ! -x aset/busybox ]; then
    echo "Mengunduh BusyBox statis..."
    curl -sL https://busybox.net/downloads/binaries/1.35.0-x86_64-linux-musl/busybox -o aset/busybox
    chmod +x aset/busybox
fi
if [ ! -x aset/hog ]; then
    echo "Mengompilasi hog..."
    cc -static -O2 -o aset/hog hog.c
fi
echo "Aset siap: aset/busybox, aset/hog"

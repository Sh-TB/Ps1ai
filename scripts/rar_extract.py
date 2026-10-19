#!/usr/bin/env python3.13
"""Extract RAR5 archive using libarchive (proper RAR5 support)."""
import libarchive
import os, sys

rar_path = "/home/z/my-project/ps1-test/downloads/bios_psx.rar"
out_dir = "/home/z/my-project/ps1-test/extracted/bios_libarchive"
os.makedirs(out_dir, exist_ok=True)

with libarchive.file_reader(rar_path) as arch:
    for entry in arch:
        dest = os.path.join(out_dir, entry.pathname)
        if entry.isdir:
            os.makedirs(dest, exist_ok=True)
            print(f"[DIR ] {entry.pathname}")
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            for block in entry.get_blocks():
                f.write(block)
        print(f"[FILE] {entry.pathname}  size={entry.size}  ->  {os.path.getsize(dest)}")

print("\n--- MD5 of extracted files ---")
import hashlib
for root, _, files in os.walk(out_dir):
    for name in sorted(files):
        p = os.path.join(root, name)
        h = hashlib.md5(open(p, "rb").read()).hexdigest()
        print(f"{h}  {os.path.getsize(os.path.join(root, name)):>8}  {name}")

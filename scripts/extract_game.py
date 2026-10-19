#!/usr/bin/env python3.13
"""Extract Metal Slug X 7z and verify PS1 image contents."""
import py7zr, os, hashlib

src = "/home/z/my-project/ps1-test/downloads/metal_slug_x.7z"
out = "/home/z/my-project/ps1-test/extracted/metal_slug_x"
os.makedirs(out, exist_ok=True)

with py7zr.SevenZipFile(src, mode="r") as z:
    print("=== Archive contents ===")
    for f in z.list():
        print(f"  {f.filename:60s} uncompressed={f.uncompressed}")
    z.extractall(out)

print("\n=== Extracted files ===")
for root, _, files in os.walk(out):
    for name in sorted(files):
        p = os.path.join(root, name)
        size = os.path.getsize(p)
        md5 = hashlib.md5(open(p, "rb").read(1024 * 1024)).hexdigest()[:8]
        print(f"  {os.path.relpath(p, out):60s} {size:>12,} B  md5[:8]={md5}")

# If cue exists, show it
for root, _, files in os.walk(out):
    for name in files:
        if name.lower().endswith(".cue"):
            p = os.path.join(root, name)
            print(f"\n=== {name} ===")
            print(open(p).read())

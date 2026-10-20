#!/usr/bin/env python3
"""make_audio_fixture.py — generate a lawful self-made PS1 test content image.

Creates <out>/audio_fixture.cue + audio_fixture.bin: a 4-second silent
CDDA track in raw 2352-byte sectors. The image contains zero copyrighted
material (pure silence, generated here), yet it exercises the REAL
libretro content path: cue parsing, disc TOC construction, BIOS CD
player boot. It is a fixture, NOT a game; it never enters the repo.
"""
import argparse
import os
import sys

SECTOR = 2352
SECS = 4 * 75  # 4 seconds of audio sectors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/ps1play_fixture")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    bin_path = os.path.join(a.out, "audio_fixture.bin")
    cue_path = os.path.join(a.out, "audio_fixture.cue")

    # Raw CDDA sector: 12 sync + 4 header (ignored for audio) + audio.
    # Silence = all zero samples (digital silence, valid audio).
    with open(bin_path, "wb") as f:
        for _ in range(SECS):
            f.write(b"\x00" * SECTOR)
    with open(cue_path, "w") as f:
        f.write('FILE "audio_fixture.bin" BINARY\n')
        f.write("  TRACK 01 AUDIO\n")
        f.write("    INDEX 01 00:00:00\n")
    print(f"fixture written: {bin_path} ({SECS * SECTOR} bytes)")
    print(f"cue written    : {cue_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

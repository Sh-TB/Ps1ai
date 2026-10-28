#!/usr/bin/env python3
"""r24t0_doukutsu_asset.py — rebuild the doukutsupsx (Cave Story PSX)
local license-patched image after the 4th filesystem rollback.

Same pipeline as r13_new_games.py (imported, not duplicated): download
the v0.7 release iso, verify sha256 against the manifest-recorded value,
wrap to MODE2/2352 if needed, apply the local retail license sectors.

Verification anchor: manifest records doukutsu_lic.bin = 32,565,792 B,
sha256 bf15559eef20cded...7554 (identical to the release iso because the
release already carries the standard US license block — overwrite was a
no-op in r13). We assert the rebuilt image matches byte-for-byte.
No game bytes are committed: output stays in emu/games_homebrew/patched/.
"""
import hashlib
import os
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))

from r13_new_games import (DOUKUTSU_URL, EMU, PATCHED, apply_license,  # noqa: E402
                           download, sha256)
from r13_new_games import wrap_mode2_2352  # noqa: E402

MANIFEST_SHA = "bf15559eef20cded0d728e4c97da6830a1d4f7bb83a5c1e5dffb5fc755c27554"
MANIFEST_BYTES = 32565792


def main():
    os.makedirs(PATCHED, exist_ok=True)
    dst = os.path.join(EMU, "doukutsu_r7_us.iso")
    download(DOUKUTSU_URL, dst)
    iso = open(dst, "rb").read()
    h_iso = sha256(iso)
    print(f"iso: {len(iso)} bytes sha256={h_iso}")
    assert h_iso == MANIFEST_SHA, "release iso sha256 mismatch vs manifest"
    assert len(iso) == MANIFEST_BYTES

    size = len(iso)
    if size % 2352 == 0 and size % 2048 != 0:
        raw = iso
        assert raw[16 * 2352 + 25:16 * 2352 + 30] == b"CD001"
        print("iso is already raw MODE2/2352")
    else:
        assert size % 2048 == 0, "unexpected iso size"
        assert iso[16 * 2048 + 1:16 * 2048 + 6] == b"CD001"
        raw = wrap_mode2_2352(iso)
        open(os.path.join(EMU, "doukutsu.bin"), "wb").write(raw)
        print(f"wrapped 2048->2352: {len(raw)} bytes")

    p, h = apply_license(raw, "doukutsu")
    print(f"patched: {p} sha256={h}")
    assert h == MANIFEST_SHA, (
        f"rebuilt lic image {h} != manifest {MANIFEST_SHA} "
        "(r13 recorded the license overwrite as a no-op)")
    print("OK: doukutsu_lic.bin byte-identical to the r13 image")


if __name__ == "__main__":
    main()

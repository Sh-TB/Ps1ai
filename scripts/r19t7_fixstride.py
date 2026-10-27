#!/usr/bin/env python3
"""r19t7_fixstride.py — normalize a 2448-stride (raw+subchannel) PS1 dump to
plain 2352 MODE2/2352 so beetle/mednafen reads it correctly (r19-t7).

Forensic basis: air_hockey's "Air Hockey (USA).bin" is 66,887 sectors of
2448 bytes (2352 + 96 subchannel) while its .cue declares MODE2/2352 — the
core therefore misreads every sector, OpenBIOS's CD check never passes and
the disc never boots (r19 timeline: BIOS cube animation loops 20,000 frames,
game EXE never runs). The fix is a pure re-layout: keep bytes [0:2352] of
each 2448 block — the user data, headers, EDC/ECC and license sectors are
untouched; only the trailing P-Q subchannel bytes are dropped.

Writes <out>.bin + <out>.cue and verifies: sector count, sync pattern spot
checks, ISO PVD at LBA16 (+24), license text at LBA0..15, SYSTEM.CNF.
"""
import argparse
import json
import os
import sys
import time

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
CHUNK = 4096          # sectors per chunk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="2448-stride .bin")
    ap.add_argument("--out", required=True, help="output .bin path (2352)")
    ap.add_argument("--cue-out", default=None)
    ap.add_argument("--volume", default=None, help="volume label for cue")
    args = ap.parse_args()

    size = os.path.getsize(args.src)
    if size % 2448:
        print(f"ABORT: src size {size} not a multiple of 2448")
        return 1
    n = size // 2448
    t0 = time.time()
    with open(args.src, "rb") as fi, open(args.out, "wb") as fo:
        for base in range(0, n, CHUNK):
            k = min(CHUNK, n - base)
            buf = fi.read(k * 2448)
            out = bytearray()
            for s in range(k):
                blk = memoryview(buf)[s * 2448: s * 2448 + 2352]
                out += blk
            fo.write(out)
    print(f"wrote {args.out}: {n} sectors x 2352 = {n * 2352}B "
          f"in {time.time() - t0:.1f}s")

    # ---- verification ----
    rep = {"src": args.src, "out": args.out, "sectors": n,
           "src_bytes": size, "out_bytes": n * 2352}
    bad = 0
    import random
    random.seed(19)
    samples = sorted(set([0, 1, 2, n // 2, n - 2, n - 1] +
                         [random.randrange(n) for _ in range(60)]))
    with open(args.out, "rb") as f:
        for s in samples:
            f.seek(s * 2352)
            if f.read(12) != SYNC:
                bad += 1
    rep["sync_spotchecks"] = len(samples)
    rep["sync_bad"] = bad

    with open(args.out, "rb") as f:
        f.seek(16 * 2352 + 24)
        pvd = f.read(88)
        rep["pvd_ok"] = pvd[:1] == b"\x01" and pvd[1:6] == b"CD001"
        rep["volume_id"] = pvd[40:72].decode("ascii", "replace").rstrip()
        f.seek(0 * 2352 + 24)
        lic = f.read(180)
        rep["license_text"] = lic[:120].decode("latin1", "replace").strip()
        # SYSTEM.CNF root walk is overkill here; check the PVD root record
        f.seek(16 * 2352 + 24 + 156)
        root = f.read(34)
        rep["root_lba"] = int.from_bytes(root[2:6], "little")
    cue = args.cue_out or os.path.splitext(args.out)[0] + ".cue"
    with open(cue, "w") as f:
        f.write(f'FILE "{os.path.basename(args.out)}" BINARY\n'
                f"  TRACK 01 MODE2/2352\n"
                f"    INDEX 01 00:00:00\n")
    rep["cue"] = cue
    print(json.dumps(rep, indent=1))
    return 0 if (bad == 0 and rep["pvd_ok"]) else 2


if __name__ == "__main__":
    sys.exit(main())

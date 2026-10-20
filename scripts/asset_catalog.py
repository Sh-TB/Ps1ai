#!/usr/bin/env python3
"""asset_catalog.py — extract and catalogue graphics/stage assets from the
owner's local disc image (Issue #3 Phase D).

Method:
  1. walk the ISO9660 records (via game_rebuild_index.DiscImage)
  2. scan every file for PS1 TIM signatures (magic 0x00000010 + bpp flag
     + structurally-valid CLUT/image blocks) — no assumption that assets
     are standalone TIM files; embedded TIMs inside containers are found
     by the same scan
  3. full structural validation before acceptance (bounds, dims, lens)
  4. decode 4/8/16bpp images with their CLUTs to PNG thumbnails
  5. contact sheets + a local HTML browser in the EXTERNAL workspace
  6. assets.json (workspace) + distilled metadata registry for the repo
     (offsets/hashes/dims only — zero copyrighted pixels committed)

Non-TIM files get a container-candidate record (entropy, TIM density,
sector-pattern notes) instead of a guess.

Usage:
  python3 scripts/asset_catalog.py --game <cue/bin> --out <analysis-dir>
      [--max-files N] [--thumbs] [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from game_rebuild_index import (  # noqa: E402
    DiscImage, parse_pvd, walk_disc, parse_system_cnf,
)

CONFIG_VERSION = "asset-catalog-1"
TIM_MAGIC = 0x00000010
BPP_NAME = {0: "4bpp+clut", 1: "8bpp+clut", 2: "16bpp",
            3: "24bpp", 4: "mixed", 8: "4bpp+clut(ext)",
            9: "8bpp+clut(ext)"}
ROLE_HINTS = [
    ("PAT", "player-pattern (hypothesis)"),
    ("X1", "stage-1 tile/pattern (hypothesis)"),
    ("ST01", "stage-1 container (hypothesis)"),
    ("ENEMY", "enemy graphics (hypothesis)"),
    ("ART", "gallery/art (hypothesis)"),
    ("TITLE", "title screen (hypothesis)"),
    ("MISSION", "mission-select (hypothesis)"),
    ("RANKING", "ranking screen (hypothesis)"),
    ("X801", "large shared container (hypothesis)"),
    ("X09", "large shared container (hypothesis)"),
    ("MCARD", "memory-card screen (hypothesis)"),
    ("LOADING", "loading screen (hypothesis)"),
]


def role_hint(path):
    up = path.upper()
    for key, role in ROLE_HINTS:
        if key in up:
            return role
    return "unknown (hypothesis: none)"


def shab(b):
    return hashlib.sha1(b).hexdigest()[:16]


def scan_tim(data, path, limit=None):
    """Return list of validated TIM records inside `data`."""
    out = []
    n = len(data)
    i = 0
    step = 4
    while i + 20 <= n:
        if limit and len(out) >= limit:
            break
        magic = struct.unpack_from("<I", data, i)[0]
        if magic != TIM_MAGIC:
            i += step
            continue
        flag = struct.unpack_from("<I", data, i + 4)[0]
        bpp = flag & 0x7
        if bpp not in (0, 1, 2, 3, 4) and (flag & 0xF) not in (8, 9):
            i += step
            continue
        rec = {"file": path, "abs_off": i, "flag": flag,
               "bpp_name": BPP_NAME.get(flag & 0xF, f"flag{flag}")}
        p = i + 8
        try:
            if (flag & 0xF) in (0, 1, 8, 9):        # has CLUT block
                clut_len = struct.unpack_from("<I", data, p)[0]
                if not (12 <= clut_len <= 1024 * 1024
                        and p + clut_len <= n
                        and clut_len % 4 == 0):
                    i += step
                    continue
                cb = data[p + 12:p + clut_len]
                cw = struct.unpack_from("<H", data, p + 8)[0]
                ch = struct.unpack_from("<H", data, p + 10)[0]
                rec["clut"] = {"block_len": clut_len,
                               "x": struct.unpack_from("<H", data,
                                                       p + 4)[0],
                               "y": struct.unpack_from("<H", data,
                                                       p + 6)[0],
                               "w": cw, "h": ch,
                               "colors": len(cb) // 2,
                               "sha1_16": shab(cb)}
                p += clut_len
            img_len = struct.unpack_from("<I", data, p)[0]
            if not (12 <= img_len <= 4_000_000 and p + img_len <= n
                    and img_len % 4 == 0):
                i += step
                continue
            ix = struct.unpack_from("<H", data, p + 4)[0]
            iy = struct.unpack_from("<H", data, p + 6)[0]
            iw = struct.unpack_from("<H", data, p + 8)[0]
            ih = struct.unpack_from("<H", data, p + 10)[0]
            if not (0 < iw <= 1024 and 0 < ih <= 512):
                i += step
                continue
            rec["image"] = {"block_len": img_len, "x": ix, "y": iy,
                            "w": iw, "h": ih,
                            "sha1_16": shab(
                                data[p + 12:p + img_len])}
            rec["valid"] = True
            out.append(rec)
            i = p + img_len                          # next candidate
        except struct.error:
            i += step
    return out


def decode_tim(data, rec):
    """Decode a validated TIM record to a PIL RGBA image (or None)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    i = rec["abs_off"]
    flag = rec["flag"]
    mode = flag & 0xF
    p = i + 8
    clut = None
    if mode in (0, 1, 8, 9):
        clut_len = struct.unpack_from("<I", data, p)[0]
        raw = data[p + 12:p + clut_len]
        clut = list(struct.unpack(f"<{len(raw)//2}H", raw))
        p += clut_len
    img_len = struct.unpack_from("<I", data, p)[0]
    iw = struct.unpack_from("<H", data, p + 8)[0]
    ih = struct.unpack_from("<H", data, p + 10)[0]
    body = data[p + 12:p + img_len]
    try:
        if mode in (0, 8):                            # 4bpp
            w4 = iw * 4
            px = Image.new("RGBA", (w4, ih))
            pix = px.load()
            for y in range(ih):
                row = body[y * iw * 2:(y + 1) * iw * 2]
                for x in range(w4):
                    b = row[x // 2]
                    idx = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    c = clut[idx] if clut and idx < len(clut) else 0
                    pix[x, y] = ((c & 0x1F) << 3, ((c >> 5) & 0x1F) << 3,
                                 ((c >> 10) & 0x1F) << 3,
                                 255 if c & 0x8000 or idx else 0)
            return px
        if mode in (1, 9):                            # 8bpp
            w8 = iw * 2
            px = Image.new("RGBA", (w8, ih))
            pix = px.load()
            for y in range(ih):
                row = body[y * iw * 2:(y + 1) * iw * 2]
                for x in range(w8):
                    idx = row[x]
                    c = clut[idx] if clut and idx < len(clut) else 0
                    pix[x, y] = ((c & 0x1F) << 3, ((c >> 5) & 0x1F) << 3,
                                 ((c >> 10) & 0x1F) << 3,
                                 255 if c & 0x8000 or idx else 0)
            return px
        if mode == 2:                                 # 16bpp direct
            px = Image.new("RGBA", (iw, ih))
            pix = px.load()
            for y in range(ih):
                row = struct.unpack_from(f"<{iw}H", body,
                                         y * iw * 2)
                for x, c in enumerate(row):
                    pix[x, y] = ((c & 0x1F) << 3, ((c >> 5) & 0x1F) << 3,
                                 ((c >> 10) & 0x1F) << 3,
                                 255 if c & 0x8000 else 0)
            return px
    except Exception:
        return None
    return None


def entropy(b):
    if not b:
        return 0.0
    from collections import Counter
    import math
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-files", type=int, default=4096)
    ap.add_argument("--thumbs", action="store_true",
                    help="decode PNG thumbnails + contact sheets")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()
    disc = DiscImage(args.game)
    pvd = parse_pvd(disc)
    files, _dirs = walk_disc(disc, pvd, max_files=args.max_files)
    assets, containers = [], []
    thumbs_dir = os.path.join(args.out, "thumbs")
    if args.thumbs:
        os.makedirs(thumbs_dir, exist_ok=True)

    for k, f in enumerate(sorted(files, key=lambda x: x["path"])):
        if f["size"] < 64:
            continue
        try:
            data = disc.read_user_range(f["lba"], f["size"])
        except OSError:
            continue
        recs = scan_tim(data, f["path"])
        if recs:
            for r in recs:
                r["asset_id"] = (f["path"].split("/")[-1].upper()
                                 .replace(";1", "").replace(".", "_")
                                 + f"_{r['abs_off']:06X}")
                r["role_hypothesis"] = role_hint(f["path"])
                r["source"] = {"file": f["path"], "lba": f["lba"],
                               "file_size": f["size"]}
            assets.extend(recs)
            if args.thumbs:
                for r in recs:
                    img = decode_tim(data, r)
                    if img is None:
                        continue
                    w, h = img.size
                    scale = max(1, max(w, h) // 128)
                    img = img.resize((max(1, w // scale),
                                      max(1, h // scale)))
                    img.save(os.path.join(thumbs_dir,
                                          r["asset_id"] + ".png"))
                    r["thumb"] = "thumbs/" + r["asset_id"] + ".png"
        else:
            head = data[:4096]
            containers.append({
                "file": f["path"], "lba": f["lba"], "size": f["size"],
                "entropy_head4k": round(entropy(head), 3),
                "head16": head[:16].hex(),
                "note": "no TIM found in file body (compressed or "
                        "raw-tile container candidate)",
            })
        if k % 40 == 0:
            print(f"[{k}/{len(files)}] assets={len(assets)} "
                  f"containers={len(containers)} "
                  f"({time.time()-t0:.0f}s)")

    # contact sheets (external workspace only)
    if args.thumbs and assets:
        try:
            from PIL import Image, ImageDraw
            cols, cell = 10, 132
            per = 200
            sheets = []
            for s in range(0, min(len(assets), 1000), per):
                chunk = [a for a in assets[s:s + per] if a.get("thumb")]
                if not chunk:
                    continue
                rows = (len(chunk) + cols - 1) // cols
                sheet = Image.new("RGBA", (cols * cell, rows * cell),
                                  (24, 24, 28, 255))
                d = ImageDraw.Draw(sheet)
                for i, a in enumerate(chunk):
                    im = Image.open(os.path.join(args.out, a["thumb"]))
                    x, y = (i % cols) * cell, (i // cols) * cell
                    sheet.paste(im, (x + 2, y + 2))
                    d.text((x + 4, y + cell - 14),
                           a["asset_id"][-9:], fill=(220, 220, 160))
                p = os.path.join(args.out, f"contact_{s//per:02d}.png")
                sheet.convert("RGB").save(p)
                sheets.append(os.path.basename(p))
        except Exception as e:
            sheets = []
            print("contact sheet failed:", e)

    # HTML browser (external)
    if args.thumbs:
        with open(os.path.join(args.out, "asset_browser.html"), "w") as f:
            f.write("<html><head><meta charset='utf-8'>"
                    "<title>MSX asset browser</title></head>"
                    "<body style='background:#181820;color:#ddd'>"
                    "<h1>Metal Slug X asset browser "
                    "(local lawful copy, external workspace)</h1>"
                    "<table cellpadding=4 border=1>")
            for a in assets:
                f.write(f"<tr><td>{a['asset_id']}</td>"
                        f"<td>{a['bpp_name']}</td>"
                        f"<td>{a.get('image',{}).get('w')}x"
                        f"{a.get('image',{}).get('h')}</td>"
                        f"<td>{a['role_hypothesis']}</td>"
                        f"<td><img src='{a.get('thumb','')}'></td></tr>")
            f.write("</table></body></html>")

    # distilled registry (repo-safe: metadata only)
    registry = {
        "schema": "ps1play-assets/1",
        "serial": "SLUS-01212",
        "config_version": CONFIG_VERSION,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                       time.gmtime()),
        "image_sha256_note": "hashes identify; no pixels committed",
        "counts": {"tim_assets": len(assets),
                   "container_candidates": len(containers)},
        "assets": [{
            "asset_id": a["asset_id"],
            "source_file": a["source"]["file"],
            "abs_off": a["abs_off"],
            "flag": a["flag"],
            "bpp": a["bpp_name"],
            "dims": [a.get("image", {}).get("w"),
                     a.get("image", {}).get("h")],
            "clut_colors": a.get("clut", {}).get("colors"),
            "image_sha1_16": a.get("image", {}).get("sha1_16"),
            "role_hypothesis": a["role_hypothesis"],
            "status": "EXTRACTED_UNVERIFIED",
        } for a in assets],
        "containers": containers,
    }
    with open(os.path.join(args.out, "assets.json"), "w") as f:
        json.dump(registry, f, indent=1)
    print(f"assets={len(assets)} containers={len(containers)} "
          f"-> {args.out}/assets.json "
          f"({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()

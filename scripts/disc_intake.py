#!/usr/bin/env python3
"""disc_intake.py — one-shot local-disc intake tool (Issue #6/#9 helper-tool push).

Given a local .cue/.bin, produce a metadata-only intake report:
  * track/sector geometry (MODE2/2352 vs 2048)
  * license-block + region-marker presence (LBA 0..15 / LBA 4)
  * PSX-flavored PVD parse (root dir record at 156 OR ECMA 168 — r13 finding)
  * full directory walk, SYSTEM.CNF BOOT line, PS-EXE inventory (pc0/t_size)
  * string census: ASCII runs and SJIS runs (counts only — never committed)
  * boot-route recommendation per docs/tiny_games_playbook.md decision tree

Everything derived from disc CONTENT stays local (--json-out goes to scratch/);
the committed artifacts are facts: serials, sizes, counts, verdicts.

Usage:
  python3 scripts/disc_intake.py --cue "path/to/game.cue" [--json-out out.json]
  python3 scripts/disc_intake.py --batch <dir-with-cues> [--out-md docs/old_games_intake.md]
"""
import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

RAW = 2352
USER = 2048
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


# ---------------------------------------------------------------- cue parsing
def parse_cue(cue_path):
    """Return (bin_path, cue_claimed_sector_size_or_None, index1_lba_offset)."""
    text = Path(cue_path).read_text(errors="replace")
    mode = None
    bin_path = None
    idx1 = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'FILE\s+"?([^"]+)"?\s+BINARY', line, re.I)
        if m:
            bin_path = m.group(1)
        m = re.match(r"TRACK\s+\d+\s+MODE2/(\d+)", line, re.I)
        if m:
            mode = int(m.group(1))
        m = re.match(r"TRACK\s+\d+\s+MODE1/(\d+)", line, re.I)
        if m:
            mode = int(m.group(1))
        m = re.match(r"INDEX\s+01\s+(\d+):(\d+):(\d+)", line, re.I)
        if m and idx1 is None:
            mm, ss, ff = (int(x) for x in m.groups())
            idx1 = (mm * 60 + ss) * 75 + ff
    if bin_path is None:
        raise ValueError(f"no FILE directive in {cue_path}")
    if not os.path.isabs(bin_path):
        bin_path = os.path.join(os.path.dirname(cue_path), bin_path)
    return bin_path, mode, idx1 or 0


STRIDE_RAW_SUB = 2448  # 2352 + 96 P-W subchannel bytes (dump says MODE2/2352 but packs subcode)


def detect_stride(bin_path):
    """Measure the real sector stride from sync-pattern spacing.
    Known dumps: 2352 (raw), 2448 (raw+subcode), 2048 (user only)."""
    with open(bin_path, "rb") as f:
        head = f.read(4 * 1024 * 1024)
    j = head.find(SYNC)
    if j < 0:
        return 2048  # user-only dump (or plain ISO)
    k = head.find(SYNC, j + 12)
    if k < 0 or not (2040 <= k - j <= 2500):
        return RAW
    return k - j


class DiscReader:
    def __init__(self, bin_path, sector_size=None, lba_offset=0):
        self.f = open(bin_path, "rb")
        self.stride = sector_size or detect_stride(bin_path)
        self.lba_offset = lba_offset

    def calibrate_pvd(self):
        """Choose the file offset that puts a real PVD at LBA 16.
        Cues disagree about whether the 150-sector pregap is packed into the
        bin (redump-style cues say 00:02:00 with data at file sector 0 for
        some writers, and self-generated images omit the pregap entirely)."""
        for cand in (self.lba_offset, 0, 150):
            save = self.lba_offset
            self.lba_offset = cand
            if self.user_sector(16)[1:6] == b"CD001":
                return self.lba_offset
            self.lba_offset = save
        return self.lba_offset

    def user_sector(self, lba):
        """Return 2048 user bytes for logical sector lba."""
        phys = (lba + self.lba_offset) * self.stride
        self.f.seek(phys)
        raw = self.f.read(RAW)
        if len(raw) < RAW:
            raw = raw + b"\x00" * (RAW - len(raw))
        if raw[:12] != SYNC:
            # 2048-byte user-only dump — phys IS the user data
            self.f.seek(phys)
            u = self.f.read(USER)
            return u.ljust(USER, b"\x00")
        mode = raw[15]
        if mode == 2:
            return raw[24:24 + USER]  # sync12+header4+subheader8
        return raw[16:16 + USER]      # MODE1/2352

    def close(self):
        self.f.close()


# ------------------------------------------------------------------ PS-EXE
def parse_psexe(data):
    if data[:8] != b"PS-X EXE":
        return None
    pc0, gp, t_addr, t_size = struct.unpack_from("<IIII", data, 0x10)
    # exe version / region-ish strings live at 0x4C..0x4C+0x50
    stamp = data[0x4C:0x4C + 0x50].split(b"\x00")[0].decode("ascii", "replace")
    return {"pc0": pc0, "t_addr": t_addr, "t_size": t_size, "stamp": stamp}


# ------------------------------------------------------------- dir records
def parse_dir_record(buf, off):
    """One ISO9660 directory record -> dict or None."""
    ln = buf[off]
    if ln == 0:
        return None
    rec = {}
    rec["extent"] = struct.unpack_from("<I", buf, off + 2)[0]
    rec["size"] = struct.unpack_from("<I", buf, off + 10)[0]
    rec["flags"] = buf[off + 25]
    nlen = buf[off + 32]
    name = buf[off + 33:off + 33 + nlen]
    if nlen == 1 and name[0] in (0, 1):
        rec["name"] = "." if name[0] == 0 else ".."
    else:
        rec["name"] = name.decode("ascii", "replace").split(";")[0]
    return rec


def find_root_record(pvd):
    """PSX BIOS reads the root dir record at offset 156 (r13 finding);
    strict ECMA-119 puts it at 156 too — 168 was the old misread. Try both,
    verify with the ".'' self record signature (extent == extent of '..'s
    parent i.e. the record must self-reference sensibly: size 2048, flags 2)."""
    for off in (156, 168):
        r = parse_dir_record(pvd, off)
        if r and (r["flags"] & 2) and r["size"] >= 2048:
            return off, r
    return None, None


def walk_tree(reader, root_extent, root_size, max_files=4096):
    files, dirs = [], []
    queue = [(root_extent, root_size, "")]
    seen = set()
    while queue and len(files) < max_files:
        extent, size, prefix = queue.pop(0)
        if (extent, size) in seen:
            continue
        seen.add((extent, size))
        nsec = max(1, (size + USER - 1) // USER)
        for s in range(nsec):
            buf = reader.user_sector(extent + s)
            off = 0
            while off < USER:
                rec = parse_dir_record(buf, off)
                if rec is None:
                    break
                off += rec_len(buf, off)
                if rec["name"] in (".", ".."):
                    continue
                path = f"{prefix}{rec['name']}"
                if rec["flags"] & 2:
                    dirs.append(path)
                    queue.append((rec["extent"], rec["size"], path + "/"))
                else:
                    files.append((path, rec["extent"], rec["size"]))
    return files, dirs


def rec_len(buf, off):
    ln = buf[off]
    if ln == 0:  # records do not span sectors; scan to next boundary handled by caller
        step = USER - off
        return step if step >= 34 else 1
    return ln


# ------------------------------------------------------------- string census
ASCII_RUN = re.compile(rb"[\x20-\x7e]{6,}")
SJIS_LEAD = ((0x81, 0x9F), (0xE0, 0xEF))
SJIS_TRAIL = (0x40, 0xFC)


def sjis_runs(data, min_len=4):
    runs = []
    i, n = 0, len(data)
    while i + 1 < n:
        b = data[i]
        ok = any(lo <= b <= hi for lo, hi in SJIS_LEAD)
        if not ok:
            i += 1
            continue
        t = data[i + 1]
        if not (SJIS_TRAIL[0] <= t <= SJIS_TRAIL[1] and t != 0x7F):
            i += 1
            continue
        j = i
        run = []
        while j + 1 < n:
            b2, t2 = data[j], data[j + 1]
            if (any(lo <= b2 <= hi for lo, hi in SJIS_LEAD)
                    and SJIS_TRAIL[0] <= t2 <= SJIS_TRAIL[1] and t2 != 0x7F):
                run.append(data[j:j + 2])
                j += 2
            else:
                break
        if len(run) >= min_len:
            runs.append(b"".join(run))
        i = j + 2 if j > i else i + 1
    return runs


def census(data):
    asc = ASCII_RUN.findall(data)
    sj = sjis_runs(data)
    sj_chars = sum(len(r) // 2 for r in sj)
    return {
        "ascii_runs": len(asc),
        "ascii_chars": sum(len(r) for r in asc),
        "sjis_runs": len(sj),
        "sjis_chars": sj_chars,
    }


# ------------------------------------------------------------------ main intake
SERIAL_RE = re.compile(r"^(SLUS|SCUS|SLPS|SCPS|SLES|SCES|SLPM|SCPM)_?(\d{2,5})(\.(\d{1,2}))?$", re.I)
REGION_BY_PREFIX = {"SLUS": "US", "SCUS": "US", "SLES": "EU", "SCES": "EU",
                    "SLPS": "JP", "SCPS": "JP", "SLPM": "JP", "SCPM": "JP"}


def intake(cue_path):
    bin_path, _claim, lba_off = parse_cue(cue_path)
    rdr = DiscReader(bin_path, None, lba_off)
    rdr.calibrate_pvd()
    rep = {"cue": str(cue_path), "bin": bin_path, "sector_stride": rdr.stride,
           "bin_bytes": os.path.getsize(bin_path)}
    # license block LBA 0..15
    lic = b"".join(rdr.user_sector(l) for l in range(16))
    rep["license_block_nonzero"] = sum(1 for b in lic if b) > 512
    rep["license_ascii_prefix"] = "".join(
        chr(b) if 0x20 <= b < 0x7F else ("\n" if b in (10, 13) else " ")
        for b in lic[0:132]).strip().replace("\n", " | ")
    reg = rdr.user_sector(4)
    reg_txt = bytes(b for b in reg if 0x20 <= b < 0x7F).lower().replace(b" ", b"")
    region = "NA" if b"america" in reg_txt else (
        "EU" if (b"europe" in reg_txt or b"pal" in reg_txt) else (
            "JP" if b"japan" in reg_txt else "UNKNOWN"))
    rep["region"] = region
    # PVD
    pvd = rdr.user_sector(16)
    rep["pvd_magic_ok"] = pvd[1:6] == b"CD001"
    rep["volume_id"] = pvd[40:72].decode("ascii", "replace").strip()
    root_off, root = find_root_record(pvd)
    rep["root_record_off"] = root_off
    if root:
        files, dirs = walk_tree(rdr, root["extent"], root["size"])
        rep["n_files"] = len(files)
        rep["n_dirs"] = len(dirs)
        exes = []
        cnf = None
        for path, ext, size in files:
            base = path.rsplit("/", 1)[-1]
            is_exe_name = base.upper().endswith(".EXE") or SERIAL_RE.match(base)
            if size >= 2048 and is_exe_name:
                data = b"".join(rdr.user_sector(ext + s)
                                for s in range(min(4, (size + USER - 1) // USER)))
                pe = parse_psexe(data)
                if pe:
                    pe["path"] = path
                    pe["size"] = size
                    exes.append(pe)
            if path.upper() == "SYSTEM.CNF" and size <= USER * 4:
                cnf = rdr.user_sector(ext)[:size].decode("ascii", "replace")
        rep["psx_exe"] = exes
        if cnf:
            m = re.search(r"BOOT\s*=\s*cdrom:?\\?([^;\r\n]+)", cnf, re.I)
            rep["boot_line"] = m.group(1).strip() if m else None
            rep["system_cnf_present"] = True
        else:
            rep["system_cnf_present"] = False
    else:
        rep["n_files"] = None
        rep["psx_exe"] = []
    # string census over the main exe (first 2 MB max)
    main = rep["psx_exe"][0] if rep["psx_exe"] else None
    if main:
        mext = next((e for p, e, s in files if p == main["path"]), None)
        nsec = min((main["size"] + USER - 1) // USER, 2 * 1024 * 1024 // USER)
        blob = b"".join(rdr.user_sector(mext + s) for s in range(nsec))
        rep["string_census"] = census(blob)
    else:
        rep["string_census"] = census(b"".join(rdr.user_sector(16 + s) for s in range(64)))
    # boot route per playbook decision tree
    if rep["license_block_nonzero"]:
        route = "route 1: license sectors ON disc — direct boot expected"
    else:
        exsz = main["t_size"] if main else 0
        if exsz and exsz <= 32768:
            route = "route 3: <=32 KB EXE — container swap viable"
        elif exsz:
            route = "route 4: >32 KB no-license EXE — license-patch local copy"
        else:
            route = "route 2: license-patch local copy (no PS-EXE found at top level)"
    rep["boot_route"] = route
    # serial identity (exe name wins over the region-marker heuristic)
    for cand in ([main["path"].rsplit("/", 1)[-1]] if main else []) + [rep["volume_id"]]:
        base = cand.upper().replace(";1", "")
        m = SERIAL_RE.match(base)
        if m:
            prefix = m.group(1).upper()
            num = m.group(2)
            rev = m.group(4) or ""
            rep["serial"] = f"{prefix}-{num}{rev}"  # SLUS_004.86 -> SLUS-00486
            rep["region"] = REGION_BY_PREFIX.get(prefix, rep["region"])
            break
    rdr.close()
    return rep


def md_row(rep, name):
    ex = rep["psx_exe"][0] if rep["psx_exe"] else None
    sc = rep.get("string_census", {})
    return ("| {n} | {ser} | {reg} | {exe} | {tsz} | {pc} | {lic} | {nf} | {ar} | {sr} | {rt} |".format(
        n=name,
        ser=rep.get("serial", rep["volume_id"])[:16],
        reg=rep["region"],
        exe=(ex or {}).get("path", "—")[:28],
        tsz=f"{(ex or {}).get('t_size', 0):,}" if ex else "—",
        pc=f"0x{(ex or {}).get('pc0', 0):08X}" if ex else "—",
        lic="YES" if rep["license_block_nonzero"] else "NO",
        nf=rep.get("n_files") if rep.get("n_files") is not None else "—",
        ar=sc.get("ascii_runs", "—"),
        sr=sc.get("sjis_runs", "—"),
        rt=rep["boot_route"].split(":")[0],
    ))


MD_HEADER = ("| game | serial | region | exe path | t_size | pc0 | license | "
             "files | ascii runs | sjis runs | boot route |\n"
             "|---|---|---|---|---|---|---|---|---|---|---|\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cue")
    ap.add_argument("--batch", help="directory scanned recursively for .cue files")
    ap.add_argument("--json-out")
    ap.add_argument("--out-md")
    args = ap.parse_args()

    cues = []
    if args.cue:
        cues.append(args.cue)
    if args.batch:
        for root, _dirs, files in os.walk(args.batch):
            for f in files:
                if f.lower().endswith(".cue"):
                    cues.append(os.path.join(root, f))
    reps = []
    for c in cues:
        name = Path(c).stem
        try:
            rep = intake(c)
        except Exception as e:  # noqa: BLE001 — intake must never die mid-batch
            rep = {"cue": c, "error": f"{type(e).__name__}: {e}"}
        rep["game"] = name
        reps.append(rep)
        print(f"== {name}: {rep.get('error') or rep['boot_route']}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(reps, indent=1))
    if args.out_md:
        lines = [MD_HEADER]
        for rep in reps:
            if "error" in rep:
                lines.append(f"| {rep['game']} | ERR | {rep['error'][:40]} | — | — | "
                             f"— | — | — | — | — |\n")
            else:
                lines.append(md_row(rep, rep["game"]))
        Path(args.out_md).write_text("".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

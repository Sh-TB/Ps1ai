#!/usr/bin/env python3
"""overlay_index.py — Issue #5 Priority Refinement: index the runtime
overlay modules (ENEMY.BIN, MISSION.BIN) INTO the existing re_index
infrastructure (no parallel knowledge base).

Mapping method (evidence-first, never file_off == runtime addr):
  1. detect the code-like region inside the file (j/jal density);
  2. collect absolute j/jal targets of that region (position
     independent — j/jal targets are absolute KSEG addresses);
  3. fit the destination by containment: the true destination D
     maximizes targets inside [D, D+code_len); the exe text end
     (t_addr + t_size) is the preferred candidate when it scores
     within 95% of the best fit (natural allocator boundary);
  4. record every candidate + score in the output (auditable).

Outputs (metadata only — no game bytes are ever written):
  <out>/overlay_index.json   full index + mapping evidence
  <out>/re_index.sqlite      EXTENDED with module-tagged tables:
                             overlay_files / overlay_functions /
                             overlay_edges / overlay_grefs
  cache: <out>/.overlay_cache.json keyed on exe-text + module sha256s

Module identity is preserved on every row, so cache results and
address mappings can never silently mix regions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from game_rebuild_index import (  # noqa: E402
    DiscImage, parse_pvd, walk_disc, scan_global_refs,
)

CONFIG_VERSION = "overlay-index-2"
OVERLAY_MODULES = ("ENEMY.BIN", "MISSION.BIN")
# code-region file offsets + load destinations with provenance.
# ENEMY.BIN: LIVE-VERIFIED verbatim copy at 0x8009C0E8 (issue5_probe3
# V1: 0 mismatch runs across all 115,400 bytes; V2: code head at
# base+0xD180 = 0x800A9268). The static text-end fit (0x800A7800) was
# FALSIFIED by the live check — live override takes precedence.
# code_off: refit against the live-fixed destination (containment).
# MISSION.BIN: not resident at mission-1 gameplay (probe V3, 0 hits at
# 4/5 anchors) — dest stays unresolved, functions not emitted.
MODULE_REGISTRY = {
    "ENEMY.BIN": {"code_off": 0xD180,
                  "code_off_source": "issue3_structural_decode"
                                     "+live_base_refit",
                  "dest": 0x8009C0E8,
                  "dest_source": "LIVE verbatim pattern match "
                                 "(issue5_probe3 V1/V2, 0 mismatch "
                                 "runs, delta-consistent 27 anchors)",
                  "status": "TESTED"},
    "MISSION.BIN": {"code_off": None, "code_off_source": "detect",
                    "dest": None,
                    "dest_source": "NOT resident at mission-1 "
                                   "gameplay (issue5_probe3 V3)",
                    "status": "NOT_FOUND_IN_RAM"},
}
EXE_LO = 0x80010000
SEARCH_LO, SEARCH_HI = 0x80000000, 0x80200000
DENSITY_WINDOW = 512          # words per density window (2 KB)
DENSITY_MIN = 12              # j/jal words to call a window code-like
TEXT_END_PREFER = 0.95        # accept text-end within 95% of best fit


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def words_of(data: bytes) -> np.ndarray:
    return np.frombuffer(data[:len(data) // 4 * 4], dtype="<u4")


def jjal(words: np.ndarray, va0: int):
    """(site_vas, target_vas) for every j/jal word."""
    ops = words >> np.uint32(26)
    idx = np.flatnonzero((ops == 2) | (ops == 3))
    sites = va0 + idx * 4
    tgts = 0x80000000 | ((words[idx] & np.uint32(0x3FFFFFF))
                         << np.uint32(2))
    return sites.astype(np.int64), tgts.astype(np.int64)


def detect_code_region(words: np.ndarray):
    """First..last j/jal-dense window -> (lo_off, hi_off) BYTE offsets."""
    ops = words >> np.uint32(26)
    isj = ((ops == 2) | (ops == 3)).astype(np.int32)
    n_words = len(words)
    n_bytes = n_words * 4
    dense = []
    for w in range(0, n_words, DENSITY_WINDOW):
        if int(isj[w:w + DENSITY_WINDOW].sum()) >= DENSITY_MIN:
            dense.append(w)
    if not dense:
        return None
    return dense[0] * 4, min(n_bytes, (dense[-1] + DENSITY_WINDOW) * 4)


def fit_destination(targets: np.ndarray, code_len: int, text_end: int):
    """Containment fit. Returns dict with chosen dest + all candidates."""
    ts = np.sort(targets)
    cands = {}

    def count_in(lo):
        return int(((ts >= lo) & (ts < lo + code_len)).sum())

    # densest window start (exact: max targets in any window of len L)
    best_lo, best_c = text_end, count_in(text_end)
    j = 0
    for i in range(len(ts)):
        while ts[i] - ts[j] >= code_len:
            j += 1
        c = i - j + 1
        if c > best_c:
            best_c, best_lo = c, int(ts[j])
    cands[f"{best_lo:08x}"] = {"dest": f"0x{best_lo:08X}",
                               "internal_targets": best_c,
                               "kind": "densest_window"}
    cands[f"{text_end:08x}"] = {"dest": f"0x{text_end:08X}",
                                "internal_targets": count_in(text_end),
                                "kind": "exe_text_end"}
    chosen, why = best_lo, "densest_window"
    if count_in(text_end) >= TEXT_END_PREFER * best_c:
        chosen, why = text_end, "exe_text_end_preferred"
    return {"dest": chosen, "rule": why,
            "internal_targets": count_in(chosen),
            "total_targets": int(len(ts)),
            "candidates": cands}


def scan_functions(words_code: np.ndarray, dest: int, prefix="ovl"):
    """Functions = union(prologue candidates, j/jal targets inside)."""
    ops = words_code >> np.uint32(26)
    n = len(words_code)
    idx = np.flatnonzero((ops == 2) | (ops == 3))
    tgts = 0x80000000 | ((words_code[idx] & np.uint32(0x3FFFFFF))
                         << np.uint32(2))
    inside = sorted(set(tgts[(tgts >= dest)
                             & (tgts < dest + n * 4)].tolist()))
    prologues = []
    for i in range(n - 1):
        w = int(words_code[i])
        if (w >> 26) == 0x09:
            rs, rt, imm = ((w >> 21) & 31), ((w >> 16) & 31), w & 0xFFFF
            if rs == 29 and rt == 29 and imm >= 0x8000:
                w2 = int(words_code[i + 1])
                if (w2 >> 26) == 0x2B and ((w2 >> 16) & 31) == 31:
                    prologues.append(dest + i * 4)
    starts = {}
    for va in prologues:
        starts.setdefault(va, set()).add("prologue")
    for va in inside:
        starts.setdefault(va, set()).add("jal_target")
    ordered = sorted(starts)
    funcs = []
    for k, va in enumerate(ordered):
        end = ordered[k + 1] if k + 1 < len(ordered) else dest + n * 4
        kinds = starts[va]
        conf = ("verified" if kinds == {"prologue", "jal_target"}
                else "medium" if "prologue" in kinds else "low")
        funcs.append({"va": f"0x{va:08X}", "size": max(4, end - va),
                      "name": f"{prefix}_{va:08X}",
                      "confidence": conf,
                      "evidence": sorted(kinds)})
    return funcs


def scan_edges(words_code: np.ndarray, dest: int, exe_hi: int,
               module: str):
    ops = words_code >> np.uint32(26)
    idx = np.flatnonzero((ops == 2) | (ops == 3))
    sites = dest + idx * 4
    tgts = 0x80000000 | ((words_code[idx] & np.uint32(0x3FFFFFF))
                         << np.uint32(2))
    kind = np.where(ops[idx] == 2, "j", "jal")
    n = len(words_code) * 4
    edges = []
    for s, t, k in zip(sites.tolist(), tgts.tolist(), kind.tolist()):
        if dest <= t < dest + n:
            reg = "internal"
        elif EXE_LO <= t < exe_hi:
            reg = "exe"
        elif t >= 0x800A7800:
            reg = "ram_high"
        else:
            reg = "unknown"
        edges.append({"module": module, "src": f"0x{s:08X}",
                      "dst": f"0x{t:08X}", "kind": k,
                      "dst_region": reg})
    return edges


def scan_grefs(words_code: np.ndarray, dest: int, module: str,
               exe_hi: int):
    refs = scan_global_refs(words_code, dest)
    out = []
    for eff, sites in refs.items():
        region = ("exe" if EXE_LO <= eff < exe_hi
                  else "internal" if dest <= eff < dest
                  + len(words_code) * 4 else "ram_high"
                  if eff >= 0x800A7800 else "unknown")
        for pc, k in sites:
            out.append({"module": module, "va": f"0x{eff:08X}",
                        "pc": f"0x{pc:08X}", "kind": k,
                        "region": region})
    return out


def module_strings(data: bytes, code_off: int, dest: int, min_len=6):
    va0, text = dest, data[code_off:]
    out, cur, start = [], [], 0
    printable = set(range(0x20, 0x7F))
    for off, b in enumerate(text):
        if b in printable:
            if not cur:
                start = off
            cur.append(b)
        else:
            if len(cur) >= min_len:
                out.append((f"0x{va0 + start:08X}",
                            bytes(cur).decode("ascii", "replace")[:80]))
            cur = []
    return out


def find_overlay_files(disc, pvd):
    files, _dirs = walk_disc(disc, pvd)
    found = {}
    for f in files:
        base = f["path"].split("/")[-1].split(";")[0].upper()
        if base in OVERLAY_MODULES:
            found[base] = f
    return found


def cache_key_for(mod_data: dict, exe_sha: str) -> dict:
    """Cache identity: exe text + every module file + config version.
    Any byte change in any input invalidates the cache."""
    key = {"config": CONFIG_VERSION, "exe_text_sha256": exe_sha}
    for name in sorted(mod_data):
        key[f"sha256:{name}"] = sha256(mod_data[name])
    return key


def write_sqlite(dbp: str, master: dict):
    """Module-tagged tables merged INTO the existing re_index db.
    (module, va) is the key everywhere — regions cannot mix."""
    import sqlite3
    con = sqlite3.connect(dbp)
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS overlay_files "
                "(module TEXT PRIMARY KEY, lba INT, size INT, "
                "sha256 TEXT, code_off INT, code_end INT, "
                "dest_va TEXT, status TEXT, rule TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS overlay_functions "
                "(module TEXT, va TEXT, size INT, name TEXT, "
                "confidence TEXT, evidence TEXT, "
                "PRIMARY KEY (module, va))")
    cur.execute("CREATE TABLE IF NOT EXISTS overlay_edges "
                "(module TEXT, src TEXT, dst TEXT, kind TEXT, "
                "dst_region TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS overlay_grefs "
                "(module TEXT, va TEXT, pc TEXT, kind TEXT, "
                "region TEXT)")
    for t in ("overlay_functions", "overlay_edges", "overlay_grefs"):
        cur.execute(f"DELETE FROM {t}")
    cur.execute("DELETE FROM overlay_files")
    for name, m in master["modules"].items():
        if m["status"] != "INDEXED":
            continue
        cur.execute("INSERT INTO overlay_files VALUES (?,?,?,?,?,?,?,?,?)",
                    (name, m["file"]["lba"], m["file"]["size"],
                     m["file"]["sha256"],
                     int(m["code_region_file_off"][0], 16),
                     int(m["code_region_file_off"][1], 16),
                     m["mapping"]["dest"], m["status"],
                     m["mapping"]["rule"]))
        cur.executemany("INSERT INTO overlay_functions VALUES (?,?,?,?,?,?)",
                        [(name, f["va"], f["size"], f["name"],
                          f["confidence"], ",".join(f["evidence"]))
                         for f in m["functions"]])
        cur.executemany("INSERT INTO overlay_edges VALUES (?,?,?,?,?)",
                        [(e["module"], e["src"], e["dst"], e["kind"],
                          e["dst_region"]) for e in m["edges"]])
        cur.executemany("INSERT INTO overlay_grefs VALUES (?,?,?,?,?)",
                        [(g["module"], g["va"], g["pc"], g["kind"],
                          g["region"]) for g in m["grefs"]])
    con.commit()
    con.close()


def build(game, out_dir, force=False):
    import sqlite3
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    cache_path = os.path.join(out_dir, ".overlay_cache.json")
    disc = DiscImage(game)
    pvd = parse_pvd(disc)
    if pvd is None:
        raise SystemExit("no ISO9660 PVD")
    recs = find_overlay_files(disc, pvd)
    missing = [m for m in OVERLAY_MODULES if m not in recs]
    if missing:
        raise SystemExit(f"overlay files not on disc: {missing}")

    exe_id_path = os.path.join(out_dir, "exe_identity.json")
    if not os.path.exists(exe_id_path):
        raise SystemExit("run game_rebuild_index.py first (need "
                         "exe_identity.json for the load address)")
    exe_id = json.load(open(exe_id_path))
    t_addr = int(exe_id["header"]["t_addr"], 0) \
        if isinstance(exe_id["header"]["t_addr"], str) \
        else exe_id["header"]["t_addr"]
    t_size = exe_id["header"]["t_size"]
    text_end = t_addr + t_size
    exe_sha = exe_id["hashes"]["sha256"]

    mod_data, cache_key = {}, {"config": CONFIG_VERSION,
                               "exe_text_sha256": exe_sha}
    for name in OVERLAY_MODULES:
        rec = recs[name]
        data = disc.read_user_range(rec["lba"], rec["size"])
        mod_data[name] = data
    cache_key = cache_key_for(mod_data, exe_sha)

    if not force and os.path.exists(cache_path):
        old = json.load(open(cache_path))
        if old.get("key") == cache_key:
            print("overlay index cache HIT — recomputing nothing")
            return json.load(open(os.path.join(out_dir,
                                               "overlay_index.json")))

    master = {
        "schema": "ps1play overlay_index/1",
        "config_version": CONFIG_VERSION,
        "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
        "exe_text": {"lo": f"0x{t_addr:08X}", "hi": f"0x{text_end:08X}",
                     "sha256": exe_sha},
        "modules": {}, "copyright_note": "metadata only",
    }
    for name in OVERLAY_MODULES:
        data = mod_data[name]
        words = words_of(data)
        reg_entry = MODULE_REGISTRY.get(name, {})
        code_off_cfg = reg_entry.get("code_off")
        region = detect_code_region(words)
        if code_off_cfg is not None:
            code_off = code_off_cfg
            code_end = region[1] if region else len(data) & ~3
            off_source = reg_entry["code_off_source"]
        elif region is not None:
            code_off, code_end = region
            off_source = "detect"
        else:
            master["modules"][name] = {"status": "NO_CODE_DETECTED"}
            continue
        wcode = words[code_off // 4:code_end // 4]
        reg_dest = reg_entry.get("dest")
        _sites, tgts = jjal(wcode, 0)          # targets are absolute
        fit = fit_destination(tgts, code_end - code_off, text_end)
        if reg_dest is not None:
            dest_va0 = reg_dest
            fit["rule"] = "live_override"
            fit["live_dest"] = f"0x{reg_dest:08X}"
            fit["dest_source"] = reg_entry.get("dest_source")
            fit["status"] = reg_entry.get("status", "TESTED")
        else:
            dest_va0 = None
            master["modules"][name] = {
                "status": reg_entry.get("status", "UNRESOLVED_DEST"),
                "file": {"lba": recs[name]["lba"],
                         "size": recs[name]["size"],
                         "sha256": sha256(data)},
                "dest_source": reg_entry.get("dest_source"),
                "note": "no verified load address; functions not "
                        "emitted (would be address-invalid)",
            }
            print(f"{name}: dest unresolved ({reg_entry.get("dest_source")})"
                  " — not indexed")
            continue
        if dest_va0 < EXE_LO or dest_va0 > 0x80200000:
            raise SystemExit(f"{name}: implausible dest {dest_va0:#x}")
        prefix = name.split(".")[0].lower()
        funcs = scan_functions(wcode, dest_va0, prefix)
        edges = scan_edges(wcode, dest_va0, text_end, name)
        grefs = scan_grefs(wcode, dest_va0, name, text_end)
        strings = module_strings(data, code_off, dest_va0)
        n_exe = sum(1 for e in edges if e["dst_region"] == "exe")
        master["modules"][name] = {
            "status": "INDEXED",
            "file": {"lba": recs[name]["lba"], "size": recs[name]["size"],
                     "sha256": sha256(data)},
            "code_region_file_off": [f"0x{code_off:X}", f"0x{code_end:X}"],
            "code_off_source": off_source,
            "code_bytes": code_end - code_off,
            "mapping": {**fit,
                        "file_off_at_dest": f"0x{code_off:X}",
                        "va_range": [f"0x{dest_va0:08X}",
                                     f"0x{dest_va0 + code_end - code_off:08X}"]},
            "counts": {"functions": len(funcs), "edges": len(edges),
                       "edges_into_exe": n_exe, "grefs": len(grefs),
                       "strings": len(strings)},
            "functions": funcs, "edges": edges, "grefs": grefs,
            "strings": strings,
        }
        print(f"{name}: code file[{code_off:#x}:{code_end:#x}] -> "
              f"{dest_va0:#010x} ({fit['rule']}, "
              f"{fit['internal_targets']}/{fit['total_targets']} "
              f"internal targets), {len(funcs)} funcs, {len(edges)} "
              f"edges ({n_exe} into exe), {len(grefs)} grefs")

    # ---- sqlite merge (module-tagged tables in the SAME db) ----
    dbp = os.path.join(out_dir, "re_index.sqlite")
    write_sqlite(dbp, master)

    with open(os.path.join(out_dir, "overlay_index.json"), "w") as f:
        json.dump(master, f, indent=1)
    with open(cache_path, "w") as f:
        json.dump({"key": cache_key,
                   "generated_utc": master["generated_utc"]}, f, indent=1)
    print(f"overlay index done in {time.time() - t0:.1f}s -> {out_dir}")
    return master


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    m = build(a.game, a.out, a.force)
    for name, mod in m["modules"].items():
        print(name, mod.get("status"),
              mod.get("counts") if mod.get("status") == "INDEXED" else "")


if __name__ == "__main__":
    main()

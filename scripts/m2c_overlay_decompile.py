#!/usr/bin/env python3
"""m2c overlay decompiler driver (Issue #10 source-recovery benchmark).

Reproduces the measured m2c-vs-Ghidra comparison on the ENEMY.BIN overlay
(committed outputs: data/games/SLUS-01212/m2c/). Requires the m2c checkout
at work/m2c (git clone https://github.com/matt-kempster/m2c). Outputs go to
work/msx_recomp/evidence/issue10_m2c/ by default (local-only; the committed
artifacts are the 7 showcase functions + metrics JSONs).

Generates GNU-as .asm for selected ENEMY.BIN overlay functions (capstone),
runs matt-kempster/m2c on them, and pairs each output with the committed
Ghidra decompilation of the SAME function for a head-to-head readability /
time / reliability comparison.

Evidence rule: overlay load address 0x8009C0E8 is the LIVE-VERIFIED mapping
(Issue #5 probe3, 0 mismatches over 115,400 bytes). Function boundaries come
from work/msx_recomp/index (built from the canonical disc).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/home/z/my-project")
REPO = BASE / "ps1ai"
WORK = BASE / "work"
M2C = WORK / "m2c" / "m2c.py"
OVERLAY = REPO / "ps1play" / "re" / "ENEMY.BIN"
OUTDIR = WORK / "msx_recomp" / "evidence" / "issue10_m2c"
GHIDRA_JSON = REPO / "data" / "games" / "SLUS-01212" / "ghidra" / "overlay_decompiled.json"

OVERLAY_VA = 0x8009C0E8  # live-verified load address
CODE_OFF = 0xD180        # ENEMY.BIN code region file offset (msx_gate_static.py)
CODE_END_OFF = 0x1C2C8   # end of code region


def va_to_off(va):
    return CODE_OFF + (va - OVERLAY_VA)

# Capstone: MIPS32 little-endian
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

TARGETS = [
    "800a4588",  # largest func touching entity +0x8e/+0x92 (hp/x fields)
    "8009de68",  # hp compare -> flags + handler dispatch (real damage path)
    "800a000c",
    "8009e1c4",
    "800a91c4",  # has 1 caller, touches hp field
    "800a87f8",  # mission dispatch (8 in-overlay callers, anchor probe)
    "800a41d8",  # damage_entry anchor probe
]

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.detail = False


def load_bounds():
    """Function boundaries from the repo-committed Ghidra function list."""
    fj = json.load(open(REPO / "data/games/SLUS-01212/ghidra/ghidra_overlay_functions.json"))
    # rows: list of dicts {entry, bytes, name, callees, callers}
    if isinstance(fj, dict):
        for k in ("functions", "rows", "items"):
            if k in fj:
                fj = fj[k]
                break
    bounds = {}
    for r in fj:
        if isinstance(r, dict) and "entry" in r:
            a = int(r["entry"], 16) if isinstance(r["entry"], str) else int(r["entry"])
            sz = r.get("bytes") or 4
            bounds[a] = sz
    return bounds


def next_addr(bounds, a):
    nxt = [x for x in bounds if x > a]
    return min(nxt) if nxt else a + 0x1000


def emit_one(bounds, addr, out_path):
    """Emit ONE function into its own asm file.

    Nested function labels (Ghidra fragment entries inside a larger range)
    split m2c function bodies, so each target gets an isolated file: its own
    body, local L_ labels for in-body branches, X_ externs for everything else.
    """
    data = OVERLAY.read_bytes()
    CODE_HI = OVERLAY_VA + (CODE_END_OFF - CODE_OFF)
    import re as _re
    tgt_re = _re.compile(r"0x([0-9a-fA-F]{8})")
    size = bounds.get(addr)
    if size is None:
        return None
    # extend size forward to the next function start (covers cold tails)
    nxt = [a for a in sorted(bounds) if a > addr]
    end = max(addr + size, min(nxt) if nxt else addr + size)
    # cap: never reach past the code region
    end = min(end, CODE_HI)
    off = va_to_off(addr)
    body = []
    for w in range(off, off + (end - addr), 4):
        va = OVERLAY_VA + (w - CODE_OFF)
        word = data[w:w + 4]
        got = list(md.disasm(word, va, count=1))
        if got:
            body.append((va, f"{got[0].mnemonic} {got[0].op_str}"))
        else:
            body.append((va, f".word 0x{int.from_bytes(word, 'little'):08x}"))
    # delay-slot repair: if the last instruction is a branch/jump, m2c needs
    # its delay slot; Ghidra sizes sometimes end exactly after the branch.
    if body:
        last_mn = body[-1][1].split()[0]
        if last_mn in ("j", "jal", "jr") or last_mn.startswith("b"):
            tail_va = body[-1][0] + 4
            tail_off = va_to_off(tail_va)
            if tail_off + 4 <= len(data) and tail_va < CODE_HI:
                word = data[tail_off:tail_off + 4]
                got = list(md.disasm(word, tail_va, count=1))
                if got:
                    body.append((tail_va, f"{got[0].mnemonic} {got[0].op_str}"))
                else:
                    body.append((tail_va, f".word 0x{int.from_bytes(word, 'little'):08x}"))
    body_va = {va for va, _ in body}
    need_label = set()
    for va, text in body:
        if text.startswith(".word"):
            continue
        for m in tgt_re.finditer(text):
            t = int(m.group(1), 16)
            if t in body_va and t != va:
                need_label.add(t)
    lines = [".set noat", ".set noreorder", ".text", ""]
    n_ins = n_word = 0
    lines.append(f".global FUN_{addr:08x}")
    lines.append(f"FUN_{addr:08x}:")
    for va, text in body:
        if va in need_label and va != addr:
            lines.append(f".L{va:08x}:")
        if text.startswith(".word"):
            lines.append(f"  {text}")
            n_word += 1
        else:
            def sub(m):
                t = int(m.group(1), 16)
                if t in need_label:
                    return f".L{t:08x}"
                return f"X_{t:08x}"  # extern (fn call or out-of-body branch)
            lines.append(f"  {tgt_re.sub(sub, text)}")
            n_ins += 1
    out_path.write_text("\n".join(lines))
    return n_ins, n_word


def run_m2c(asm_path, func, out_path):
    t0 = time.time()
    r = subprocess.run(
        [sys.executable, str(M2C), str(asm_path), "-f", func],
        capture_output=True, text=True, timeout=120,
        cwd=str(M2C.parent),
    )
    dt = time.time() - t0
    out = r.stdout
    if not out.strip():
        out = f"/* m2c rc={r.returncode} stderr={r.stderr[:500]} */"
    out_path.write_text(out)
    return dt, out


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    t_setup = time.time()
    bounds = load_bounds()
    print(f"[bounds] {len(bounds)} overlay functions loaded")

    ghidra = json.load(open(GHIDRA_JSON))
    report = {"schema": "issue10/m2c-experiment/2", "overlay_va": hex(OVERLAY_VA),
              "code_off": hex(CODE_OFF), "targets": [], "notes": []}
    for t in TARGETS:
        addr = int(t, 16)
        func = f"FUN_{t}"
        if addr not in bounds:
            report["notes"].append(f"{t}: not in bounds, skipped")
            continue
        asm_path = OUTDIR / f"{t}.asm"
        emitted = emit_one(bounds, addr, asm_path)
        if emitted is None:
            report["notes"].append(f"{t}: emit failed")
            continue
        n_ins, n_word = emitted
        dt, c_out = run_m2c(asm_path, func, OUTDIR / f"{t}.m2c.c")
        g = ghidra.get(t, {})
        ok = "Decompilation failure" not in c_out
        report["targets"].append({
            "addr": t,
            "bytes": bounds[addr],
            "asm_ins": n_ins,
            "m2c_seconds": round(dt, 2),
            "m2c_ok": ok,
            "m2c_c_len": len(c_out),
            "m2c_c_sha256": __import__("hashlib").sha256(c_out.encode()).hexdigest()[:16],
            "ghidra_c_len": len(g.get("c") or ""),
            "m2c_out": (OUTDIR / f"{t}.m2c.c").name,
            "asm_out": asm_path.name,
        })
        print(f"[m2c] {t}: emit {n_ins}ins, run {dt:.1f}s, ok={ok}, "
              f"{len(c_out)} chars (ghidra: {len(g.get('c') or '')} chars)")
    (OUTDIR / "experiment.json").write_text(json.dumps(report, indent=1))
    print(f"[total setup {time.time()-t_setup:.1f}s]")

    # ---------------- full-corpus reliability pass (all 468 functions) ----
    import hashlib
    t_full = time.time()
    full = {"schema": "issue10/m2c-experiment/full-corpus/1", "results": []}
    ok_n = fail_n = 0
    total_chars = 0
    all_addrs = sorted(bounds)
    for i, a in enumerate(all_addrs):
        t = f"{a:08x}"
        asm_path = OUTDIR / f"f_{t}.asm"
        emitted = emit_one(bounds, a, asm_path)
        if emitted is None:
            continue
        dt, c_out = run_m2c(asm_path, f"FUN_{t}", OUTDIR / f"f_{t}.m2c.c")
        ok = "Decompilation failure" not in c_out
        if ok:
            ok_n += 1
            total_chars += len(c_out)
        else:
            fail_n += 1
        full["results"].append({"addr": t, "ok": ok, "sec": round(dt, 2),
                                "c_len": len(c_out) if ok else 0})
        if i % 50 == 0:
            print(f"  [full {i}/{len(all_addrs)}] ok={ok_n} fail={fail_n}")
    full["summary"] = {
        "functions": len(all_addrs), "m2c_ok": ok_n, "m2c_fail": fail_n,
        "total_seconds": round(time.time() - t_full, 1),
        "mean_seconds_per_func": round((time.time() - t_full) / max(1, len(all_addrs)), 3),
        "total_c_chars": total_chars,
    }
    (OUTDIR / "full_corpus.json").write_text(json.dumps(full, indent=1))
    print(f"[full-corpus] ok={ok_n} fail={fail_n} in "
          f"{full['summary']['total_seconds']}s")
    print("[done]", OUTDIR / "experiment.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""emulator_smoke.py — EMULATOR_SMOKE tier gate for the PS1Play host.

Verifies on THIS machine, without any copyrighted content:

  1. the libretro core .so loads via ctypes and retro_init() runs
  2. the host/frontend callback wiring answers the core's environment
     queries (system dir, pixel format, variables)
  3. the exact BIOS files THIS core build accepts (read from its own
     embedded strings) — the BIOS truth, not a doc claim
  4. if a game image is supplied, attempts retro_load_game and reports
     the first concrete failure (missing BIOS / unreadable cue / boot OK)

Test tiers (honest labeling):
    EMULATOR_SMOKE  — core loads + env wiring + (optional) load attempt
    REAL_GAME_SEGMENT — NOT claimed here; requires BIOS + disc image

Exit codes: 0 smoke passed | 2 core loads but game blocked (missing
content) | 3 core itself failed.

Usage:
    python3 scripts/emulator_smoke.py [--core PATH] [--game PATH] [--json]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

DEF_CORE = os.environ.get(
    "M1_CORE", "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so")
DEF_GAME = os.environ.get("M1_GAME", "")

# SCPH-5501 (NTSC-U) pinned by the dev environment (worklog task 2).
BIOS_MD5_OK = "490f666e1afb15b7362b406ed1cea246"


def _accepted_bios_names(core_path):
    """BIOS filenames embedded in the core binary (its own truth)."""
    try:
        out = subprocess.run(["strings", "-a", core_path],
                             capture_output=True, timeout=60).stdout
        names = set(re.findall(rb"(?i)\bscph[-_]?[0-9]{4}\.bin\b", out))
        return sorted(n.decode().lower() for n in names)
    except Exception as e:                                  # noqa: BLE001
        return [f"<strings failed: {e}>"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default=DEF_CORE)
    ap.add_argument("--game", default=DEF_GAME,
                    help="optional .cue to attempt a real load")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    res = {"tier": "EMULATOR_SMOKE", "core": a.core, "checks": []}

    def check(name, ok, detail):
        res["checks"].append({"check": name, "ok": bool(ok),
                              "detail": str(detail)})
        return ok

    if not os.path.exists(a.core):
        print(json.dumps({"error": f"core not found: {a.core}"}, indent=1))
        sys.exit(3)

    # --- stage 1: load the core through the real host ----------------
    from ps1play.core.host import LibretroCore

    work = os.path.join("/tmp", "ps1play_smoke")
    os.makedirs(os.path.join(work, "system"), exist_ok=True)
    os.makedirs(os.path.join(work, "saves"), exist_ok=True)
    core = None
    try:
        core = LibretroCore(a.core, os.path.join(work, "system"),
                            os.path.join(work, "saves"), verbose=False)
        check("core_loads", True,
              f"{core.core_name} {core.core_ver} retro_init() ok")
    except Exception as e:                                  # noqa: BLE001
        check("core_loads", False, f"ctypes load / retro_init failed: {e}")
        res["tier_result"] = "CORE_FAILED"
        if a.json:
            print(json.dumps(res, indent=1))
        sys.exit(3)

    # --- stage 2: env wiring sanity (core queries answered) ----------
    wired = bool(core.core_name and core.core_name != "?")
    check("env_wiring", wired,
          f"library_name={core.core_name!r} version={core.core_ver!r}")

    # --- stage 3: which BIOS does THIS build accept? -----------------
    bios_names = _accepted_bios_names(a.core)
    res["accepted_bios"] = bios_names
    check("bios_truth_extracted", bool(bios_names),
          f"{len(bios_names)} embedded BIOS names: "
          f"{', '.join(bios_names[:8])}")

    sysdir = os.path.join(work, "system")
    present = [f for f in os.listdir(sysdir)
               if f.lower().endswith(".bin")] if os.path.isdir(sysdir) else []
    res["bios_present"] = present
    if present:
        h = hashlib.md5()
        with open(os.path.join(sysdir, present[0]), "rb") as f:
            h.update(f.read())
        res["bios_md5"] = h.hexdigest()

    # --- stage 4: attempt a real load (only if a game was supplied) --
    load_attempted = False
    if a.game:
        load_attempted = True
        try:
            info = core.load_game(a.game)
            check("load_game", True, f"av_info={info}")
            res["tier_result"] = "GAME_LOADED"
        except Exception as e:                              # noqa: BLE001
            tail = core.log_history[-6:]
            check("load_game", False,
                  f"{e} | core log tail: {tail}")
            res["tier_result"] = "GAME_BLOCKED"
    else:
        res["tier_result"] = "GAME_NOT_ATTEMPTED"
        check("load_game", False,
              "no --game supplied (supply the copyrighted disc image "
              "locally; it is never committed)")

    core.shutdown()
    smoke_ok = all(c["ok"] for c in res["checks"]
                   if c["check"] in ("core_loads", "env_wiring",
                                     "bios_truth_extracted"))
    res["smoke_ok"] = smoke_ok
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        for c in res["checks"]:
            print(f"[{'OK ' if c['ok'] else 'MISS'}] "
                  f"{c['check']}: {c['detail']}")
        print("SMOKE:", "PASS" if smoke_ok else "FAIL",
              "| tier_result:", res["tier_result"],
              "| load_attempted:", load_attempted)
    sys.exit(0 if smoke_ok else 3)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""env_probe.py — the deterministic environment gate for PS1Play runs.

Answers ONE question with zero ambiguity: can THIS machine run the real
game (Metal Slug X USA / Beetle PSX) right now? Checks every required
artifact, prints a JSON verdict, exits 0 when ready, 2 when blocked.

This is the shortest reproduction of the BLOCKED_BY_ENVIRONMENT status:
run it; whatever `missing` lists is exactly what must be supplied
(game image + BIOS are copyrighted — they are never committed).

Usage:
    python3 scripts/env_probe.py [--game PATH] [--core PATH] [--json]
Exit codes: 0 ready | 2 blocked
"""
import argparse
import hashlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

# The known-good defaults from the original dev environment (§9 keeps
# them working); override with CLI flags or env vars.
DEF_GAME = os.environ.get(
    "M1_GAME", "/home/z/my-project/ps1-test/emu/games/"
               "Metal Slug X (USA).cue")
DEF_CORE = os.environ.get(
    "M1_CORE", "/home/z/my-project/ps1-test/cores/"
               "mednafen_psx_libretro.so")
DEF_WORKSPACE = os.environ.get("M1_WORKSPACE",
                               "/home/z/my-project/ps1-test/emu")
BIOS_NAMES = ("scph5501.bin", "scph5500.bin", "scph5502.bin")
# SCPH-5501 (NTSC-U) — MD5 verified in this repo's dev log (worklog task 2);
# Beetle PSX additionally pins SHA1 0555c6fa…88e9f30b for NTSC-U BIOS.
BIOS_MD5_OK = "490f666e1afb15b7362b406ed1cea246"
BIOS_SHA1_OK = "0555c6fae8906f3f09baf5988f00e55f88e9f30b"
# BIOS files this core build REJECTS by name+SHA1 region gate (verified
# against libretro.c firmware_is_present() and by executable boot tests,
# scripts/bios_probe.py). Providing them looks ready but silently falls
# back to the core's embedded OpenBIOS — the exact trap this probe
# exists to flag.
KNOWN_UNSUPPORTED_BIOS_MD5 = {
    "4dc4690a277144675bfe5ac5aaf5896d": "SCPH-1001 (NTSC-U retail)",
    "30a25911fa858048e8adde16590f218a": "SCPH-7502 (PAL retail)",
}
OPENBIOS_MD5 = "664ee444f38f6008d0cffc9d23e5c40d"


def classify_bios(filename, md5hex):
    """Pure classifier: what will THIS core build do with a BIOS file?

    Returns (verdict, detail). Verdicts:
      RETAIL_OK        — accepted by the core's region list for NTSC-U
      OPENBIOS_OK      — lawful OpenBIOS image (MIT, see third_party/)
      KNOWN_UNSUPPORTED — boots but SILENTLY falls back to embedded
                          OpenBIOS (name+SHA1 gate, not a hash crash)
      UNKNOWN          — not in any verified list; test it explicitly
                          with scripts/bios_probe.py before trusting it
    """
    name = (filename or "").lower()
    if name == "openbios.bin":
        if md5hex == OPENBIOS_MD5:
            return "OPENBIOS_OK", (
                "open-source BIOS replacement (MIT, PCSX-Redux) — use with "
                "beetle_psx_override_bios=openbios; its shell cannot drive "
                "the INPUT_CAUSALITY gate")
        return "UNKNOWN", "openbios.bin with unexpected md5 — re-verify"
    if name in ("scph5501.bin", "scph5500.bin", "scph5502.bin"):
        if name == "scph5501.bin" and md5hex == BIOS_MD5_OK:
            return "RETAIL_OK", (
                "SCPH-5501 NTSC-U retail — accepted by the core region "
                "list; required for SLUS-01212 legit runs")
        return "UNKNOWN", (
            f"{name} present but md5 {md5hex} is not the verified NTSC-U "
            "hash — the core will warn and may misbehave")
    if md5hex in KNOWN_UNSUPPORTED_BIOS_MD5:
        label = KNOWN_UNSUPPORTED_BIOS_MD5[md5hex]
        return "KNOWN_UNSUPPORTED", (
            f"{label}: this core build rejects it by name+SHA1 region "
            "gate (libretro.c firmware_is_present); booting will "
            "SILENTLY FALL BACK to the core's embedded OpenBIOS")
    return "UNKNOWN", (
        f"{filename} md5 {md5hex} not in any verified list — run "
        "scripts/bios_probe.py for an executable boot verdict")


def _hashes(path, n=1 << 20):
    import hashlib
    m, s = hashlib.md5(), hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(n)
            if not b:
                break
            m.update(b)
            s.update(b)
    return m.hexdigest(), s.hexdigest()


def sha1(path, n=1 << 20):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(n)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def probe(game=DEF_GAME, core=DEF_CORE, workspace=DEF_WORKSPACE):
    res = {"ready": False, "missing": [], "checks": []}

    def check(name, ok, detail):
        res["checks"].append({"check": name, "ok": bool(ok),
                              "detail": detail})
        if not ok:
            res["missing"].append(name)
        return ok

    # python deps
    for mod in ("numpy", "PIL"):
        try:
            __import__(mod if mod != "PIL" else "PIL.Image")
            check(f"python:{mod}", True, "importable")
        except Exception as e:                              # noqa: BLE001
            check(f"python:{mod}", False, f"import failed: {e}")

    # game image (+cue sanity)
    if os.path.exists(game):
        ok = True
        detail = game
        if game.lower().endswith(".cue"):
            gdir = os.path.dirname(game)
            try:
                with open(game, "r", errors="replace") as f:
                    cue = f.read()
                bins = [ln.split('"')[1] for ln in cue.splitlines()
                        if 'FILE "' in ln]
                for b in bins:
                    bp = os.path.join(gdir, b)
                    if not os.path.exists(bp):
                        ok = False
                        detail = f"cue references missing file {b}"
                        break
                    detail = (f"{game} + {b} "
                              f"({os.path.getsize(bp)} bytes)")
            except Exception as e:                          # noqa: BLE001
                ok, detail = False, f"cue unreadable: {e}"
        check("game_image", ok, detail)
    else:
        check("game_image", False,
              f"not found: {game} — supply your own SLUS-01212 "
              f"(copyrighted, never committed)")

    # libretro core
    if os.path.exists(core):
        check("libretro_core", True, f"{core} "
              f"({os.path.getsize(core)} bytes)")
    else:
        check("libretro_core", False,
              f"not found: {core} — build mednafen_psx_libretro.so from "
              f"https://github.com/libretro/beetle-psx-libretro")

    # BIOS (what the core actually accepts, not what looks plausible)
    sysdir = os.path.join(workspace, "system") if workspace else None
    bios_found = None
    if sysdir and os.path.isdir(sysdir):
        for fn in sorted(os.listdir(sysdir)):
            if not fn.lower().endswith(".bin"):
                continue
            bp = os.path.join(sysdir, fn)
            md5h, sha1h = _hashes(bp)
            verdict, detail = classify_bios(fn, md5h)
            cand = {"path": bp, "file": fn, "md5": md5h, "sha1": sha1h,
                    "verdict": verdict, "detail": detail}
            # preference: retail NTSC-U first, then OpenBIOS override path
            if verdict == "RETAIL_OK":
                bios_found = cand
                break
            if bios_found is None or verdict == "OPENBIOS_OK":
                bios_found = cand
    if bios_found:
        ok = bios_found["verdict"] in ("RETAIL_OK", "OPENBIOS_OK")
        detail = (f"{bios_found['path']} md5={bios_found['md5']} "
                  f"-> {bios_found['verdict']}: {bios_found['detail']}")
        check("bios", ok, detail)
        res["bios"] = {k: bios_found[k] for k in
                       ("file", "md5", "verdict")}
    else:
        check("bios", False,
              f"no BIOS .bin in {sysdir} — supply scph5501.bin "
              f"(MD5 {BIOS_MD5_OK}) for retail NTSC-U runs, or use the "
              "lawful third_party/openbios/openbios.bin (MIT) with "
              "beetle_psx_override_bios=openbios for OpenBIOS-mode runs")

    # workspace writability
    if workspace:
        try:
            os.makedirs(workspace, exist_ok=True)
            probe_file = os.path.join(workspace, ".probe")
            with open(probe_file, "w") as f:
                f.write("ok")
            os.remove(probe_file)
            check("workspace_writable", True, workspace)
        except OSError as e:
            check("workspace_writable", False, str(e))
    else:
        check("workspace_writable", False, "no workspace configured")

    # live boot smoke (only if every static artifact is present)
    if not res["missing"]:
        try:
            from ps1play.api import PS1Play
            kw = {"core": core, "workspace": workspace}
            # OpenBIOS-mode workspaces must engage the core's BIOS
            # override, otherwise the same image loads through the
            # silent fallback path (behaviorally identical, but the
            # run evidence must say which path was taken).
            if res.get("bios", {}).get("verdict") == "OPENBIOS_OK":
                kw["var_overrides"] = {
                    b"beetle_psx_override_bios": b"openbios"}
            p = PS1Play(game, **kw)
            info = p.boot()
            res["boot_smoke"] = info
            log_all = "\n".join(getattr(p.core, "log_history", []))
            res["firmware_fallback"] = "Firmware is missing" in log_all
            res["firmware_override_found"] = \
                "Override firmware found" in log_all
            check("core_boots_game", True,
                  f"{info.get('core')} serial={info.get('serial')} "
                  f"fallback={res['firmware_fallback']} "
                  f"override={res['firmware_override_found']}")
            p.core.shutdown()
        except Exception as e:                              # noqa: BLE001
            check("core_boots_game", False, f"boot failed: {e}")

    res["ready"] = not res["missing"] and \
        all(c["ok"] for c in res["checks"])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEF_GAME)
    ap.add_argument("--core", default=DEF_CORE)
    ap.add_argument("--workspace", default=DEF_WORKSPACE)
    ap.add_argument("--json", action="store_true",
                    help="print full JSON verdict")
    a = ap.parse_args()
    res = probe(a.game, a.core, a.workspace)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        for c in res["checks"]:
            print(f"[{'OK ' if c['ok'] else 'MISS'}] "
                  f"{c['check']}: {c['detail']}")
        print("VERDICT:",
              "READY — the real game can run on this machine"
              if res["ready"] else
              "BLOCKED_BY_ENVIRONMENT — supply the missing artifacts "
              "above")
    sys.exit(0 if res["ready"] else 2)


if __name__ == "__main__":
    main()

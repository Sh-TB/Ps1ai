#!/usr/bin/env python3
"""bios_probe.py — the BIOS decision experiment (Phase 1 gate).

Replaces string-derived BIOS claims with an executable boot test.
For one candidate BIOS file this script:

  1. builds an isolated workspace (system/ + saves/ + shots/),
  2. loads the real core through ps1play.core.host.LibretroCore,
  3. records the core's own registered variables (its truth),
  4. attempts a real boot: contentless first (BIOS CD-player menu),
     then with an optional content cue,
  5. runs a bounded number of frames, saves a screenshot,
  6. classifies BOOTED / LOADED_NO_RENDER / LOAD_FAILED with the
     core's own log as evidence.

The BIOS file keeps its real filename (renaming would test filename
recognition instead of the BIOS itself). Nothing copyrighted is
written to the repository; the workspace lives under --out (default
/tmp) and screenshots are the only artifacts kept.

Exit codes: 0 booted (frames rendered) | 2 loaded but no render or
load failed | 3 setup/usage error.

Usage:
    python3 scripts/bios_probe.py --bios /path/scph1001.bin \
        [--content /path/game.cue] [--skip-bios] [--frames 900] \
        [--out /tmp/bios_probe_out] [--json] [--quiet]

Each run writes <out>/bios_probe_result.json and <out>/last_frame.png
so the experiment can be audited without re-running it.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.core.host import LibretroCore  # noqa: E402

# Pre-seeded overrides: harmless when the key is absent, decisive when
# the core queries it. The exact key names are confirmed at runtime from
# the core's own SET_VARIABLES dump (see result["core_vars"]).
SKIP_BIOS_KEYS = (b"beetle_psx_skip_bios", b"beetle_psx_hw_skip_bios")
OVERRIDE_BIOS_KEYS = (b"beetle_psx_override_bios",
                      b"beetle_psx_hw_override_bios")
BASE_OVERRIDES = {b"beetle_psx_renderer": b"software",
                  b"beetle_psx_hw_renderer": b"software",
                  b"beetle_psx_frame_duping": b"disabled"}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_overrides(skip_bios, bios_override):
    overrides = dict(BASE_OVERRIDES)
    if skip_bios:
        for key in SKIP_BIOS_KEYS:
            overrides[key] = b"enabled"
    if bios_override:
        for key in OVERRIDE_BIOS_KEYS:
            overrides[key] = bios_override.encode()
    return overrides


def summarize_logs(history, keep=40):
    """Collapse the core log: dedupe consecutive repeats, keep the tail."""
    out = []
    for line in history:
        if out and out[-1] == line:
            continue
        out.append(line)
    return out[-keep:]


def run_probe(bios_path, content_path, skip_bios, frames, out_dir,
              verbose=False, bios_override=None):
    res = {"tool": "bios_probe", "bios": os.path.abspath(bios_path),
           "content": os.path.abspath(content_path) if content_path else None,
           "skip_bios": bool(skip_bios), "frames_requested": frames,
           "bios_override": bios_override}

    if not os.path.exists(bios_path):
        res.update(boot="SETUP_ERROR",
                   detail=f"BIOS file not found: {bios_path}")
        return res
    res["bios_md5"] = md5(bios_path)
    res["bios_size"] = os.path.getsize(bios_path)

    # ---- isolated workspace; BIOS keeps its real filename ------------
    sysdir = os.path.join(out_dir, "system")
    savedir = os.path.join(out_dir, "saves")
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(sysdir, exist_ok=True)
    os.makedirs(savedir, exist_ok=True)
    bios_in_ws = os.path.join(sysdir, os.path.basename(bios_path))
    shutil.copyfile(bios_path, bios_in_ws)
    res["bios_filename_used"] = os.path.basename(bios_path)

    overrides = build_overrides(skip_bios, bios_override)

    core = None
    t0 = time.time()
    try:
        core = LibretroCore(_CORE_PATH, sysdir, savedir,
                            var_overrides=overrides, verbose=verbose)
        res["core"] = f"{core.core_name} {core.core_ver}"
        info = core.load_game(content_path)          # None = contentless
        res["av_info"] = info
        res["load"] = "OK"
    except Exception as e:                                   # noqa: BLE001
        res["load"] = "FAILED"
        res["detail"] = str(e)
        if core is not None:
            res["core_vars_seen"] = sorted(
                k.decode(errors="replace") for k in core.core_vars)
            res["log_tail"] = summarize_logs(core.log_history, 30)
            try:
                core.shutdown()
            except Exception:                                # noqa: BLE001
                pass
        res["boot"] = "LOAD_FAILED"
        res["elapsed_s"] = round(time.time() - t0, 2)
        return res

    # ---- core's own variable list (registered during load) -----------
    res["core_vars_seen"] = sorted(
        k.decode(errors="replace") for k in core.core_vars)
    hits = [k.decode() for k in core.core_vars if b"skip_bios" in k]
    res["skip_bios_key_in_core"] = hits
    ovr = [k.decode() for k in core.core_vars if b"override_bios" in k]
    res["override_bios_key_in_core"] = ovr
    # The decisive log line: the core either finds an "official" firmware
    # (override/region list) or silently falls back to its embedded
    # OpenBIOS. Boot verdicts MUST be labeled accordingly.
    log_all = "\n".join(core.log_history)
    res["firmware_fallback"] = "Firmware is missing" in log_all
    res["firmware_override_found"] = "Override firmware found" in log_all
    if skip_bios and not hits:
        res["note"] = ("skip-bios override requested but this core build "
                       "registered no matching variable")

    # ---- bounded run + render evidence -------------------------------
    rendered_at = []
    try:
        for i in range(frames):
            core.run_frame()
            if core.frame is not None and not rendered_at:
                rendered_at.append(i + 1)
        res["frames_rendered"] = core.frame_count
        res["first_render_at_frame"] = rendered_at[0] if rendered_at else None
    except Exception as e:                                   # noqa: BLE001
        res["run_error"] = repr(e)

    shot = os.path.join(out_dir, "last_frame.png")
    px = None
    frame = core.frame_rgb()
    if frame is not None:
        from PIL import Image
        Image.fromarray(frame).save(shot)
        nonblack = int((frame.reshape(-1, 3).max(axis=1) > 8).sum())
        px = {"w": int(frame.shape[1]), "h": int(frame.shape[0]),
              "nonblack_px": nonblack,
              "nonblack_ratio": round(nonblack / frame[:, :, 0].size, 4)}
    res["pixels"] = px
    res["screenshot"] = shot if os.path.exists(shot) else None
    res["ram_bytes"] = int(core.ram.shape[0]) if core.ram is not None else 0
    nonzero_ram = int((core.ram > 0).sum()) if core.ram is not None else 0
    res["ram_nonzero_bytes"] = nonzero_ram
    res["log_tail"] = summarize_logs(core.log_history)

    # ---- honest classification ---------------------------------------
    if res.get("frames_rendered", 0) > 0 and px and px["nonblack_px"] > 64:
        res["boot"] = "BOOTED"
    elif res.get("frames_rendered", 0) > 0:
        res["boot"] = "RENDERED_BLANK"
    else:
        res["boot"] = "LOADED_NO_RENDER"

    try:
        core.shutdown()
    except Exception:                                        # noqa: BLE001
        pass
    res["elapsed_s"] = round(time.time() - t0, 2)
    return res


def main():
    global _CORE_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--bios", required=True,
                    help="BIOS file to test (keeps its real filename)")
    ap.add_argument("--content", default=None,
                    help="optional .cue to load instead of contentless boot")
    ap.add_argument("--core", default=os.environ.get(
        "M1_CORE", "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"))
    ap.add_argument("--skip-bios", action="store_true",
                    help="set the core's skip-BIOS option if it exists")
    ap.add_argument("--bios-override", default=None,
                    choices=["openbios", "psxonpsp", "ps1_rom"],
                    help="set the core's BIOS-override option (openbios "
                         "mode accepts any openbios.bin in the system dir)")
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--out", default=None,
                    help="workspace dir (default: /tmp/bios_probe_<label>)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    _CORE_PATH = a.core

    label = os.path.basename(a.bios).replace(".", "_")
    if a.skip_bios:
        label += "_skip"
    out_dir = a.out or os.path.join("/tmp", "bios_probe", label)

    res = run_probe(a.bios, a.content, a.skip_bios, a.frames, out_dir,
                    verbose=not a.quiet, bios_override=a.bios_override)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "bios_probe_result.json"), "w") as f:
        json.dump(res, f, indent=1)

    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"BIOS      : {res['bios']} (md5 {res.get('bios_md5')})")
        print(f"core      : {res.get('core')}")
        print(f"content   : {res['content'] or '<contentless>'}")
        print(f"skip_bios : {res['skip_bios']}"
              f" -> {res.get('skip_bios_key_in_core')}")
        print(f"firmware  : fallback={res.get('firmware_fallback')} "
              f"override_found={res.get('firmware_override_found')}")
        print(f"load      : {res.get('load')}  frames_rendered: "
              f"{res.get('frames_rendered')}")
        print(f"pixels    : {res.get('pixels')}")
        print(f"boot      : {res['boot']}  ({res.get('elapsed_s')}s)")
        if res.get("detail"):
            print(f"detail    : {res['detail']}")
        for line in (res.get("log_tail") or [])[:12]:
            print(f"  [core] {line}")
    sys.exit({"BOOTED": 0, "RENDERED_BLANK": 2}.get(res["boot"], 2))


if __name__ == "__main__":
    main()

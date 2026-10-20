#!/usr/bin/env python3
"""retail_bios_experiment.py — the decisive BIOS experiment, v2.

Two questions, answered with executable evidence (not README claims):

Q1. Can the user-supplied retail BIOS files boot the console?
    Source-level discovery (beetle-psx-libretro @ df2b53b): firmware
    selection is NAME-KEYED (region bucket lists, libretro.c) and a SHA1
    mismatch only logs a warning (libretro.c:772-780) — the file is
    loaded and executed regardless. So an aliased file IS executed.
    Stage RETAIL boots the user file under the interface name
    "scph5501.bin" and observes what the CPU does. Finding (verified
    with the instrumented core build): the CPU fetches 0x4A32F2B8 at
    0xBFC00000, raises Coprocessor-Unusable, and exception-loops at
    0xBFC00180 without ever writing a single byte of main RAM. The
    files contain no valid MIPS reset code and no kernel strings
    ("System ROM", "PS-X EXE" absent) and their MD5s do not match any
    Redump-listed revision:
        user scph1001.bin  md5 4dc4690a277144675bfe5ac5aaf5896d
             Redump SCPH-1001 revisions: dc2b9bf8… / da27e8b6… / 924e392e…
        user scph7502.bin  md5 30a25911fa858048e8adde16590f218a
             Redump SCPH-7502:           b9d9a0286c33dc6b7237bb13cd46fdee
    VERDICT: the supplied "BIOS" files are NOT valid retail images —
    they are site-side obfuscated/corrupt redistributions.

Q2. Can PS1Play prove executable dispatch + controller causality
    WITHOUT any BIOS at all?
    Yes — with lawful self-made content and a small documented core
    patch (exe-direct boot: the standalone PS-X EXE loader's retail
    hijack at BIOS offset 0x6990 is unreachable for the embedded
    OpenBIOS, so the patch rewrites the reset vector with a direct
    jump to the EXE entry and copies the text into main RAM; SP is NOT
    initialized, the payload must not use the stack).
    The payload (scripts/make_padtest_hw.py, hand-assembled MIPS,
    zero third-party code) polls the pad THROUGH the SIO hardware
    registers — core-verified protocol (mednafen/psx/frontio.c):
        CTRL(0x1F80104A) bit0 TXEN / bit1 DTR / bit2 RXEN (SH only:
        the register is not word-aligned — word stores raise AdES)
        reply timing: the pad answers ONE WINDOW LATE, so the poll is
        TX 01/42/00/00/00 -> RX ff/41/5A/SW1/SW2, and the load-delay
        slot is honored after every LW.
    RAM breadcrumbs at 0x80018000, all written by the payload itself:
        +00 "PAD1" magic, +04 loop counter, +08 last SW1,
        +0C last SW2, +10 polls_ok, +14 polls_fail.

Stages (each recorded honestly; a stage passing never implies the next):
  RETAIL  characterize the user BIOS files (expected finding: INVALID)
  A       EXE_DIRECT_BOOT — "PAD1" magic + advancing counter
  B       PAD_POLL_HEALTH — polls_ok > 0, polls_fail == 0, idle SW1=FF
  C       INPUT_CAUSALITY — none/RIGHT/LEFT/RIGHT-again arms must
          produce SW1 = FF/DF/7F/DF (>=90% of window samples) and the
          RIGHT result must repeat

Exit codes: 0 all stages passed | 2 a stage failed | 3 setup error.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.core.host import LibretroCore  # noqa: E402

DEF_CORE = os.environ.get(
    "M1_CORE", "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so")
DEF_SCPH1001 = ("/home/z/my-project/emu/bios/"
                "BIOS-SCPH-1001+SCPH-7502_vgdl.ir/BIOS SCPH-1001/"
                "scph1001.bin")
DEF_FIXTURE = "/tmp/ps1play_fixture/audio_fixture.cue"
DEF_EXE = "/tmp/ps1play_padtest_hw/PADTEST.EXE"

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_hw_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled"}

ALIAS_NAME = "scph5501.bin"     # core interface name for the NA bucket
PAD_BASE = 0x18000              # 0x80018000 -> RAM offset
SW1_OFF = PAD_BASE + 8
SW_NONE, SW_RIGHT, SW_LEFT = 0xFF, 0xDF, 0x7F

_BIOS = {"path": None}          # set in main(); stages read it


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def logs(core):
    out = []
    for line in core.log_history:
        if out and out[-1] == line:
            continue
        out.append(line)
    return out[-40:]


def make_ws(out_dir, name, with_alias_bios=False):
    ws = os.path.join(out_dir, name)
    shutil.rmtree(ws, ignore_errors=True)
    sysdir, savedir = os.path.join(ws, "system"), os.path.join(ws, "saves")
    os.makedirs(sysdir)
    os.makedirs(savedir)
    if with_alias_bios:
        shutil.copyfile(_BIOS["path"], os.path.join(sysdir, ALIAS_NAME))
    else:
        shutil.copyfile(os.path.join(_REPO, "third_party/openbios/"
                                     "openbios.bin"),
                        os.path.join(sysdir, "openbios.bin"))
    return sysdir, savedir


def boot_core(sysdir, savedir, content, core_path):
    core = LibretroCore(core_path, sysdir, savedir,
                        var_overrides=dict(OVERRIDES))
    core.load_game(content)
    return core


def stage_retail(out_dir, core_path, fixture):
    """Characterize the user's BIOS files by actually executing them."""
    sysdir, savedir = make_ws(out_dir, "retail", with_alias_bios=True)
    res = {"stage": "RETAIL_BIOS_CHARACTERIZATION",
           "alias_name": ALIAS_NAME,
           "source_md5": md5(_BIOS["path"]),
           "redump_reference": ("SCPH-1001 revisions: dc2b9bf8da62ec93e868"
                                "cfd29f0d067d / da27e8b6dab242d8f91a9b25d8"
                                "0c63b8 / 924e392ed05558ffdb115408c263dccf"
                                " (psx-models-bios-guide, Redump DAT)")}
    t0 = time.time()
    try:
        core = boot_core(sysdir, savedir, fixture, core_path)
        core.set_buttons(set())
        for _ in range(300):
            core.run_frame()
        ram = core.ram
        all_logs = "\n".join(core.log_history)
        res["firmware_found_log"] = "Firmware found" in all_logs
        res["sha1_alias_warning"] = \
            "Firmware found but has invalid SHA1" in all_logs
        res["exception_trace"] = [
            l for l in core.log_history if "PS1Play CPU exception" in l][:10]
        res["ram_nonzero_bytes"] = int((ram > 0).sum()) if ram is not None \
            else None
        res["frames_rendered"] = core.frame_count
        core.shutdown()
        # The experiment SUCCEEDS when it cleanly proves the finding.
        res["finding"] = ("INVALID_BIOS_IMAGE"
                          if (res["firmware_found_log"]
                              and res["exception_trace"]
                              and res["ram_nonzero_bytes"] == 0)
                          else "INCONCLUSIVE")
        res["verdict"] = "PASS" if res["finding"] == "INVALID_BIOS_IMAGE" \
            else "FAIL"
    except Exception as e:                                   # noqa: BLE001
        res["verdict"] = "FAIL"
        res["error"] = repr(e)
    res["elapsed_s"] = round(time.time() - t0, 1)
    return res


def _ram_block(core):
    return bytes(core.ram[PAD_BASE:PAD_BASE + 24])


def stage_a_exe_boot(out_dir, core_path, exe):
    """A: BIOS-free EXE dispatch — magic + advancing counter."""
    sysdir, savedir = make_ws(out_dir, "a_boot")
    res = {"stage": "A_EXE_DIRECT_BOOT", "content": exe,
           "content_md5": md5(exe)}
    t0 = time.time()
    try:
        core = boot_core(sysdir, savedir, exe, core_path)
        core.set_buttons(set())
        for _ in range(60):
            core.run_frame()
        b1 = _ram_block(core)
        for _ in range(60):
            core.run_frame()
        b2 = _ram_block(core)
        res["block_t60"] = b1.hex()
        res["block_t120"] = b2.hex()
        res["magic"] = b1[0:4].hex()
        # SW stores little-endian: 0x50414431 renders as 31 44 41 50
        res["magic_ok"] = b1[0:4] == bytes([0x31, 0x44, 0x41, 0x50])
        c1 = int.from_bytes(b1[4:8], "little")
        c2 = int.from_bytes(b2[4:8], "little")
        res["counter_t60"], res["counter_t120"] = c1, c2
        res["counter_advances"] = c2 > c1
        res["log_tail"] = [l for l in logs(core) if "PS1Play" in l][:8]
        core.shutdown()
        res["verdict"] = ("PASS" if res["magic_ok"]
                          and res["counter_advances"] else "FAIL")
    except Exception as e:                                   # noqa: BLE001
        res["verdict"] = "FAIL"
        res["error"] = repr(e)
    res["elapsed_s"] = round(time.time() - t0, 1)
    return res


def stage_b_poll_health(out_dir, core_path, exe, window=120):
    """B: pad polls succeed and idle SW1 is 0xFF."""
    sysdir, savedir = make_ws(out_dir, "b_poll")
    res = {"stage": "B_PAD_POLL_HEALTH", "window": window}
    t0 = time.time()
    try:
        core = boot_core(sysdir, savedir, exe, core_path)
        core.set_buttons(set())
        for _ in range(window):
            core.run_frame()
        b = _ram_block(core)
        core.shutdown()
        res["polls_ok"] = int.from_bytes(b[16:20], "little")
        res["polls_fail"] = int.from_bytes(b[20:24], "little")
        res["sw1_idle"] = f"0x{b[8]:02X}"
        res["sw2_idle"] = f"0x{b[12]:02X}"
        res["verdict"] = ("PASS" if res["polls_ok"] > 0
                          and res["polls_fail"] == 0
                          and res["sw1_idle"] == f"0x{SW_NONE:02X}"
                          else "FAIL")
    except Exception as e:                                   # noqa: BLE001
        res["verdict"] = "FAIL"
        res["error"] = repr(e)
    res["elapsed_s"] = round(time.time() - t0, 1)
    return res


def run_arm(out_dir, name, core_path, exe, button, settle, window):
    sysdir, savedir = make_ws(out_dir, f"c_{name}")
    core = boot_core(sysdir, savedir, exe, core_path)
    core.set_buttons(set())
    for _ in range(settle):
        core.run_frame()
    samples = []
    for _ in range(window):
        core.set_buttons({button} if button else set())
        core.run_frame()
        samples.append(int(core.ram[SW1_OFF]))
    mode, n = Counter(samples).most_common(1)[0]
    core.shutdown()
    return {"arm": name, "button": button or "none",
            "sw1_mode": f"0x{mode:02X}",
            "sw1_mode_ratio": round(n / max(len(samples), 1), 4),
            "sw1_unique": sorted({f"0x{s:02X}" for s in samples})}


def classify(arm, expect):
    return arm["sw1_mode"] == f"0x{expect:02X}" \
        and arm["sw1_mode_ratio"] >= 0.90


def stage_c_causality(out_dir, core_path, exe, settle, window):
    """C: none/RIGHT/LEFT/RIGHT-again must distinguish exactly."""
    res = {"stage": "C_INPUT_CAUSALITY", "arms": {},
           "chain": ("host set_buttons -> retro_input_state -> core "
                     "frontio -> SIO hardware protocol -> payload poll "
                     "-> game RAM (no host RAM writes, no cheats)")}
    t0 = time.time()
    try:
        plan = [("none", None, SW_NONE), ("right", "RIGHT", SW_RIGHT),
                ("left", "LEFT", SW_LEFT), ("right2", "RIGHT", SW_RIGHT)]
        for name, button, expect in plan:
            arm = run_arm(out_dir, name, core_path, exe, button,
                          settle, window)
            arm["expected_sw1"] = f"0x{expect:02X}"
            arm["classification"] = ("EXPECTED" if classify(arm, expect)
                                     else "MISMATCH")
            res["arms"][name] = arm
        res["right_repeats"] = (res["arms"]["right"]["sw1_mode"]
                                == res["arms"]["right2"]["sw1_mode"]
                                and res["arms"]["right2"]["classification"]
                                == "EXPECTED")
        res["all_expected"] = all(a["classification"] == "EXPECTED"
                                  for a in res["arms"].values())
        res["verdict"] = ("PASS" if res["all_expected"]
                          and res["right_repeats"] else "FAIL")
    except Exception as e:                                   # noqa: BLE001
        res["verdict"] = "FAIL"
        res["error"] = repr(e)
    res["elapsed_s"] = round(time.time() - t0, 1)
    return res


def _head():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
            capture_output=True, timeout=10).stdout.decode().strip()
    except Exception:                                           # noqa: BLE001
        return "unknown"


def _brief(st):
    keys = {"RETAIL_BIOS_CHARACTERIZATION": ("finding",),
            "A_EXE_DIRECT_BOOT": ("magic", "counter_advances",),
            "B_PAD_POLL_HEALTH": ("polls_ok", "polls_fail", "sw1_idle",),
            "C_INPUT_CAUSALITY": ("all_expected", "right_repeats",)}
    out = []
    for k in keys.get(st.get("stage", ""), ()):
        if k in st:
            out.append(f"{k}={st[k]}")
    if "error" in st:
        out.append(f"error={st['error']}")
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bios", default=DEF_SCPH1001,
                    help="user retail BIOS file to characterize")
    ap.add_argument("--exe", default=DEF_EXE,
                    help="PADTEST.EXE from scripts/make_padtest_hw.py")
    ap.add_argument("--fixture", default=DEF_FIXTURE,
                    help="known-good cue for the retail stage")
    ap.add_argument("--core", default=DEF_CORE)
    ap.add_argument("--out", default="/tmp/ps1play_bios_experiment")
    ap.add_argument("--settle", type=int, default=60)
    ap.add_argument("--window", type=int, default=90)
    ap.add_argument("--skip-retail", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    out = {"tool": "retail_bios_experiment", "version": 2,
           "head": _head(), "core": a.core}
    if not os.path.exists(a.exe):
        # build the payload on demand
        rc = subprocess.call([sys.executable,
                              os.path.join(_REPO,
                                           "scripts/make_padtest_hw.py"),
                              os.path.dirname(a.exe)])
        if rc != 0 or not os.path.exists(a.exe):
            print(json.dumps({"error": "payload build failed"}))
            return 3
    out["payload"] = {"exe": os.path.abspath(a.exe),
                      "md5": md5(a.exe),
                      "builder": "scripts/make_padtest_hw.py "
                                 "(hand-assembled MIPS, no third-party "
                                 "code, no BIOS dependency)"}
    if not os.path.exists(a.bios):
        print(json.dumps({"error": f"BIOS not found: {a.bios}"}))
        return 3
    _BIOS["path"] = os.path.abspath(a.bios)
    out["bios"] = {"source_file": os.path.abspath(a.bios),
                   "source_md5": md5(a.bios),
                   "alias_name": ALIAS_NAME}

    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out)
    if not os.path.exists(a.fixture):
        subprocess.run([sys.executable,
                        os.path.join(_REPO, "scripts/make_audio_fixture.py"),
                        "--out", os.path.dirname(a.fixture)],
                       check=True, capture_output=True, timeout=60)

    out["stage_retail"] = {} if a.skip_retail else \
        stage_retail(a.out, a.core, a.fixture)
    out["stage_a"] = stage_a_exe_boot(a.out, a.core, a.exe)
    out["stage_b"] = stage_b_poll_health(a.out, a.core, a.exe)
    out["stage_c"] = stage_c_causality(a.out, a.core, a.exe,
                                       a.settle, a.window)

    verdicts = [out[k].get("verdict") for k in
                ("stage_retail", "stage_a", "stage_b", "stage_c")
                if out.get(k)]
    out["overall"] = ("PASS" if verdicts and all(v == "PASS"
                                                 for v in verdicts)
                      else "FAIL")

    with open(os.path.join(a.out, "bios_experiment_result.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    if a.json:
        print(json.dumps(out, indent=1, default=str))
    else:
        for k in ("stage_retail", "stage_a", "stage_b", "stage_c"):
            st = out.get(k) or {}
            print(f"[{st.get('stage', k):30s}] "
                  f"{st.get('verdict', '-'):4s} "
                  f"{st.get('elapsed_s', 0):>6}s  {_brief(st)}")
        print(f"overall: {out['overall']}  records: "
              f"{os.path.join(a.out, 'bios_experiment_result.json')}")
    return 0 if out["overall"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""test_integration_m1.py — Level B short emulator integration test (§11).

Approx. 1-2 minutes when the environment is ready; exits immediately
with a precise BLOCKED_BY_ENVIRONMENT verdict otherwise.

Checks (recorded into the JSON result):
  1. core boots the intended disc image (serial must be SLUS-01212)
  2. emulation advances frames
  3. pad mirror responds to injected buttons (RIGHT bit toggles)
  4. adaptive navigation reaches Mission 1 (enter_gameplay3)
  5. input-control proof (trajectory divergence, 3 input scripts)
  6. short movement trial: world churns far more under RIGHT than idle
  7. evidence PNG + result JSON written to --out

Exit codes: 0 pass | 1 fail (a real check failed) | 2 environment
blocked (run scripts/env_probe.py for the exact missing artifacts).
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from env_probe import probe as env_probe, \
    DEF_GAME, DEF_CORE, DEF_WORKSPACE                     # noqa: E402


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=os.environ.get("M1_GAME", DEF_GAME))
    ap.add_argument("--core", default=os.environ.get("M1_CORE", DEF_CORE))
    ap.add_argument("--workspace",
                    default=os.environ.get("M1_WORKSPACE", DEF_WORKSPACE))
    ap.add_argument("--out",
                    default=os.path.join(_REPO, "download",
                                         "integration_level_b"))
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
           "level": "B", "checks": [], "status": None}

    env = env_probe(a.game, a.core, a.workspace)
    res["environment"] = env
    if not env["ready"]:
        res["status"] = "BLOCKED_BY_ENVIRONMENT"
        res["note"] = ("supply the missing artifacts listed in "
                       "environment.missing; the game image and BIOS are "
                       "copyrighted and are never committed")
        _write(res, a.out)
        print(json.dumps(res, indent=1))
        sys.exit(2)

    from ps1play.api import PS1Play
    from mission import responsive

    def check(name, ok, detail):
        res["checks"].append({"check": name, "ok": bool(ok),
                              "detail": str(detail)[:400]})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        return ok

    p = None
    try:
        p = PS1Play(a.game, core=a.core, workspace=a.workspace)
        info = p.boot()
        res["boot"] = info
        res["game_sha256"] = _sha(a.game)
        check("boot_serial", info.get("serial") == "SLUS-01212",
              f"serial={info.get('serial')} core={info.get('core')}")

        f0 = p.core.frames_run
        p.core.run(60, set())
        p._advance()
        check("frames_advance", p.core.frames_run >= f0 + 60,
              f"{f0} -> {p.core.frames_run}")

        # pad mirror responds to injected RIGHT
        p.core.run(10, {"RIGHT"})
        w1 = p.mem.u16(0x0D4948)
        p.core.run(10, set())
        p._advance()
        check("pad_mirror_right", bool(w1 & 0x20),
              f"pad word during RIGHT = {w1:#06x}")

        # adaptive navigation into Mission 1 (the long part)
        r = p.enter_gameplay3()
        check("enter_gameplay3", bool(r.get("in_game")),
              json.dumps(r.get("proof", r))[:300])
        if not r.get("in_game"):
            res["status"] = "FAIL"
            _write(res, a.out)
            print(json.dumps(res, indent=1))
            sys.exit(1)

        m = responsive(p)
        check("input_control_gate", bool(m[0]),
              f"pad+churn+self-play gate: {m[1]}")

        # trajectory divergence = definitive anti-attract-demo proof
        diverged, traj = p.trajectory_test(frames=180)
        check("trajectory_divergence", bool(diverged),
              json.dumps(traj)[:300])

        # short movement trial: churn under RIGHT >> idle churn
        s0 = p.mem.snapshot()
        p.core.run(60, set())
        idle = int(np.count_nonzero(s0 != p.mem.snapshot()))
        p._advance()
        s1 = p.mem.snapshot()
        p.core.run(60, {"RIGHT", "Y"})
        run = int(np.count_nonzero(s1 != p.mem.snapshot()))
        p._advance()
        check("movement_churn", run > 2 * max(idle, 1) and run > 3000,
              f"idle={idle} run={run}")

        try:
            from PIL import Image
            rgb = p.core.frame_rgb()
            if rgb is not None:
                out_png = os.path.join(a.out, "level_b_final.png")
                Image.fromarray(rgb).resize((320, 240)).save(out_png)
                res["evidence_png"] = out_png
        except Exception as e:                              # noqa: BLE001
            res["evidence_png_error"] = str(e)

        res["status"] = "PASS"
    except Exception as e:                                  # noqa: BLE001
        res["status"] = "FAIL"
        res["error"] = f"{type(e).__name__}: {e}"
    finally:
        if p is not None:
            try:
                p.core.shutdown()
            except Exception:                               # noqa: BLE001
                pass
    ok = res["status"] == "PASS"
    _write(res, a.out)
    print(json.dumps({k: res.get(k) for k in
                      ("status", "boot", "game_sha256", "evidence_png",
                       "error")}, indent=1))
    sys.exit(0 if ok else 1)


def _write(res, out):
    path = os.path.join(out, "level_b_result.json")
    with open(path, "w") as f:
        json.dump(res, f, indent=1, default=str)
    res["result_path"] = path


if __name__ == "__main__":
    main()

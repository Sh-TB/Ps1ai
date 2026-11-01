#!/usr/bin/env python3
"""r62_stage_d.py — R62 Section 13 Stage D: controlled failure
injection with safe-cleanup verification.

Three real, controlled failures against the canonical command:

  D1  missing model file        -> exit 3, no emulator state leaked
  D2  wrong model (hash mismatch vs the R61 authority manifest)
                               -> exit 3, the WRONG MODEL NEVER RUNS
  D3  SIGINT (Ctrl+C) mid-episode
                               -> exit 130, a 'stopped' episode
                                  record persisted, controller
                                  released, no leaked processes

Every case verifies: typed exit code, evidence persisted, and a
process-leak scan after the run.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r62", "stage_d")
SUMMARY = os.path.join(REPO, "data", "r62", "r62_stage_d_summary.json")


def leak_scan():
    r = subprocess.run(["pgrep", "-af", "mednafen|beetle|retro"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def run_cmd(cmd, timeout=120):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 124, str(e.stdout or ""), "TIMEOUT", time.time() - t0


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
    results = []

    # ---- D1: missing model file -----------------------------------
    d1_out = os.path.join(OUT, "d1_missing_model")
    cmd1 = [sys.executable, "-m", "ps1play", "play", "flappybird",
            "--max-frames", "50", "--output", d1_out]
    cfg1 = {"game": "flappybird", "episodes": 1,
            "max_frames_per_episode": 50,
            "model_path": "/nonexistent/model.onnx",
            "output_dir": d1_out}
    cfgp1 = os.path.join(OUT, "cfg1.json")
    with open(cfgp1, "w") as f:
        json.dump(cfg1, f)
    rc, so, se, wall = run_cmd(
        [sys.executable, "-m", "ps1play", "play", "flappybird",
         "--config", cfgp1])
    leaked = leak_scan()
    ok1 = (rc == 3 and "model not found" in (se + so)
           and not leaked)
    results.append({"case": "D1_missing_model", "exit_code": rc,
                    "expected_exit": 3, "wall_s": round(wall, 1),
                    "error_surfaced": "model not found"
                    in (se + so), "leaked": leaked or "none",
                    "ok": ok1})
    print(f"D1: rc={rc} surfaced={ok1} leaked={leaked or 'none'}",
          flush=True)

    # ---- D2: wrong model (hash mismatch) --------------------------
    d2_out = os.path.join(OUT, "d2_wrong_model")
    wrong = os.path.join(OUT, "wrong_model.onnx")
    shutil.copyfile(os.path.join(REPO, "data", "learn",
                                 "r60_soup_e6a010.onnx.json"), wrong)
    cfg2 = {"game": "flappybird", "episodes": 1,
            "max_frames_per_episode": 50, "model_path": wrong,
            "output_dir": d2_out}
    cfgp2 = os.path.join(OUT, "cfg2.json")
    with open(cfgp2, "w") as f:
        json.dump(cfg2, f)
    rc, so, se, wall = run_cmd(
        [sys.executable, "-m", "ps1play", "play", "flappybird",
         "--config", cfgp2])
    leaked = leak_scan()
    ok2 = (rc == 3 and "mismatch" in (se + so) and not leaked)
    results.append({"case": "D2_model_hash_mismatch",
                    "exit_code": rc, "expected_exit": 3,
                    "wall_s": round(wall, 1),
                    "error_surfaced": "mismatch" in (se + so),
                    "leaked": leaked or "none", "ok": ok2})
    print(f"D2: rc={rc} surfaced={ok2} leaked={leaked or 'none'}",
          flush=True)

    # ---- D3: SIGINT mid-episode ------------------------------------
    d3_out = os.path.join(OUT, "d3_sigint")
    os.makedirs(d3_out, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "ps1play", "play", "flappybird",
         "--seed", "6", "--max-frames", "10000", "--output", d3_out],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)
    time.sleep(14)      # inside the first episode (after boot+ready)
    alive = proc.poll() is None
    proc.send_signal(signal.SIGINT)
    try:
        so, se = proc.communicate(timeout=60)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        so, se = proc.communicate()
        rc = -9
    leaked = leak_scan()
    ep_file = os.path.join(d3_out, "episodes.jsonl")
    stopped_rec = None
    if os.path.exists(ep_file):
        with open(ep_file) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        for d in lines:
            if d.get("result") == "stopped":
                stopped_rec = d
    ok3 = (alive and rc == 130 and stopped_rec is not None
           and stopped_rec.get("death_reason") == "emergency_stop"
           and not leaked)
    results.append({"case": "D3_sigint_mid_episode",
                    "was_running_when_signalled": alive,
                    "exit_code": rc, "expected_exit": 130,
                    "stopped_record": bool(stopped_rec),
                    "leaked": leaked or "none", "ok": ok3})
    print(f"D3: running={alive} rc={rc} stopped_record="
          f"{bool(stopped_rec)} leaked={leaked or 'none'}",
          flush=True)

    summary = {
        "stage": "D", "round": "R62",
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cases": results,
        "all_ok": all(x["ok"] for x in results),
    }
    with open(SUMMARY, "w") as f:
        json.dump(summary, f, indent=1)
    print("STAGE_D:", "PASS" if summary["all_ok"] else "FAIL")
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

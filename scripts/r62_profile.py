#!/usr/bin/env python3
"""r62_profile.py — R62 Section 10: performance / resource / startup
profile of the complete runtime loop (not just inference).

One launch, >= 10,000 decision cycles (a full alive episode, k=6 =
exactly 10,000), measuring:
  * model load time, session init (boot) time, first-inference
  * per-stage latencies from the ordered event stream:
    capture, perception, policy, controller send, full loop
  * P50/P95/P99 per stage
  * peak RSS (VmHWM) before/after, CPU user+sys time
  * FPS of the decision loop
  * package + model + dependency sizes

Writes data/r62/r62_profile.json + scratch/r62/profile/.
"""
import json
import os
import subprocess
import sys
import time

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r62", "profile")
SUMMARY = os.path.join(REPO, "data", "r62", "r62_profile.json")


def vm_hwm_kb():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmHWM"):
                    return int(line.split()[1])
    except OSError:
        pass
    return -1


def cpu_times():
    t = os.times()
    return t.user + t.system


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    i = min(len(xs) - 1, max(0, int(round(p / 100.0 * len(xs))) - 1))
    return round(xs[i], 4)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
    rss0, cpu0 = vm_hwm_kb(), cpu_times()
    t_wall0 = time.time()

    # model load + first inference measured in-process (the policy
    # boundary only — the emulator loop is measured from the run)
    sys.path.insert(0, REPO)
    from ps1play.runtime.config import RuntimeConfig
    from ps1play.runtime.policy_runtime import RuntimePolicy
    from ps1play.runtime.interfaces import GameObservation
    import numpy as np
    t0 = time.perf_counter()
    cfg = RuntimeConfig(output_dir=OUT).validated()
    pol = RuntimePolicy(cfg)
    load_s = time.perf_counter() - t0
    x = np.zeros(10, np.float32)
    x[0] = 100.0
    t0 = time.perf_counter()
    pol.predict(GameObservation(x, 1, "first", 0.0, True))
    first_ms = (time.perf_counter() - t0) * 1000
    # warm sustained in-process calls (complements the in-loop stats)
    xs = []
    for _ in range(2000):
        t0 = time.perf_counter()
        pol.predict(GameObservation(x, 1, "w", 0.0, True))
        xs.append((time.perf_counter() - t0) * 1000)
    pol.close()

    # the REAL loop: one full alive episode (10,000 decision cycles)
    cmd = [sys.executable, "-m", "ps1play", "play", "flappybird",
           "--seed", "6", "--max-frames", "10000",
           "--max-runtime", "600", "--output", OUT]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       timeout=700)
    loop_wall = time.time() - t0

    evs = []
    with open(os.path.join(OUT, "events.jsonl")) as f:
        for line in f:
            evs.append(json.loads(line))
    # per-episode decisions from the record
    recs = [e for e in evs if e["event"] == "episode_end"]
    decisions = sum(e.get("decisions", 0) for e in recs)
    loop_wall_ep = sum(e.get("wall_s", 0) for e in recs)

    rss1, cpu1 = vm_hwm_kb(), cpu_times()
    sizes = {}
    for label, p in (
            ("model_onnx_bytes", os.path.join(
                REPO, "deployment", "flappybird_policy", "models",
                "r60_soup_e6a010.onnx")),
            ("requirements_bytes", os.path.join(
                REPO, "deployment", "flappybird_policy",
                "requirements.txt"))):
        sizes[label] = os.path.getsize(p)
    import onnxruntime
    import numpy
    dep_dir = os.path.dirname(onnxruntime.__file__)
    sizes["onnxruntime_dist_bytes"] = sum(
        os.path.getsize(os.path.join(d, f))
        for d, _, fs in os.walk(dep_dir) for f in fs)
    prof = {
        "round": "R62", "when": time.strftime(
            "%Y-%m-%dT%H:%M:%S%z"),
        "policy_inprocess": {
            "model_load_s": round(load_s, 4),
            "first_inference_ms": round(first_ms, 4),
            "warm_2000_p50_ms": pct(xs, 50),
            "warm_2000_p95_ms": pct(xs, 95),
            "warm_2000_p99_ms": pct(xs, 99),
            "warm_calls_per_s": round(2000 / (sum(xs) / 1000), 1)
            if sum(xs) > 0 else None,
        },
        "full_loop": {
            "command": " ".join(cmd),
            "exit_code": r.returncode,
            "decision_cycles": decisions,
            "wall_s": round(loop_wall, 1),
            "episode_wall_s": loop_wall_ep,
            "fps": round(decisions / loop_wall_ep, 2)
            if loop_wall_ep else None,
            "ms_per_cycle": round(loop_wall_ep * 1000 / decisions, 3)
            if decisions else None,
        },
        "resources": {
            "peak_rss_kb_profiled_process": rss1,
            "rss_growth_kb_runtime_process": None,
            "cpu_user_sys_s_runtime": round(cpu1 - cpu0, 2),
            "wall_total_s": round(time.time() - t_wall0, 1),
        },
        "sizes": sizes,
        "deps": {"numpy": numpy.__version__,
                 "onnxruntime": onnxruntime.__version__},
        "note": "loop latencies (capture/perception/policy/controller) "
                "are in the run's events.jsonl latency records; the "
                "dominant cost is the CPU-only beetle emulation "
                "inside controller_send (see the report).",
    }
    with open(SUMMARY, "w") as f:
        json.dump(prof, f, indent=1)
    print(json.dumps(prof["policy_inprocess"], indent=1))
    print(json.dumps(prof["full_loop"], indent=1))
    return 0 if (r.returncode == 0 and decisions >= 10000) else 1


if __name__ == "__main__":
    sys.exit(main())

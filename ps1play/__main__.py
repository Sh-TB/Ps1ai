"""ps1play.__main__ — the ONE command for autonomous gameplay (R62).

    python3 -m ps1play play flappybird [options]

Validates configuration, assets, hashes and dependencies, boots the
emulator, initializes the frozen R61 policy, and plays the game
autonomously — live status on the terminal, ordered JSONL events +
episode summaries + optional screenshots/video under the output
directory, safe shutdown on completion, Ctrl+C, or any failure.

Exit codes: 0 ok · 1 runtime · 2 config · 3 assets · 4 emulator ·
5 controller · 6 policy · 7 adapter · 8 lifecycle · 130 interrupted.

    python3 -m ps1play verify --profile final

is the automated release gate (see ps1play/release_gate.py).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from typing import Any, Dict, List

from ps1play.runtime.config import REPO, RUNTIME_VERSION, RuntimeConfig
from ps1play.runtime.errors import (AssetError, ConfigError,
                                    Ps1RuntimeError)
from ps1play.runtime.telemetry import TelemetryLog

EXIT_OK = 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python3 -m ps1play",
        description="Autonomous PS1 game-playing runtime "
                    f"(v{RUNTIME_VERSION}). The AI plays the real "
                    "game through the frozen R61 policy — one "
                    "command, no manual orchestration.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "play", help="play a game autonomously with the frozen policy")
    p.add_argument("game", help="registered game id, e.g. flappybird")
    p.add_argument("--episodes", type=int, default=1,
                   help="number of consecutive autonomous episodes "
                        "(default 1)")
    p.add_argument("--seed", type=int, default=None,
                   help="the episode seed k (the RNG-seeding start "
                        "press timing); default = deterministic ladder "
                        "6, 12, 18, ...")
    p.add_argument("--seed-start", type=int, default=None,
                   help="episode-ladder start (default 6); with "
                        "--seed-step builds k for episode i as "
                        "start + (i-1)*step")
    p.add_argument("--seed-step", type=int, default=None,
                   help="episode-ladder step (default 6)")
    p.add_argument("--headless", action="store_true", default=True,
                   help="(default) run the headless core — the only "
                        "mode this runtime supports")
    p.add_argument("--show-window", action="store_true",
                   help="NOT SUPPORTED: the libretro core runs "
                        "headless; use --record and watch the GIF")
    p.add_argument("--record", action="store_true",
                   help="record screenshots + GIF video of the "
                        "gameplay")
    p.add_argument("--screenshot", action="store_true",
                   help="episode-end screenshots only (no video)")
    p.add_argument("--max-frames", type=int, default=None,
                   help="per-episode frame budget (default 10000 = "
                        "the R59/R61 budget)")
    p.add_argument("--max-runtime", type=float, default=None,
                   help="wall-clock limit for the whole run, seconds "
                        "(default 300)")
    p.add_argument("--config", default=None,
                   help="path to a JSON config file (CLI flags "
                        "override it)")
    p.add_argument("--output", default=None,
                   help="output directory (default scratch/r62/"
                        "run_<UTC timestamp>)")
    p.add_argument("--verbose", action="store_true",
                   help="live status lines during episodes")
    p.set_defaults(func=_cmd_play)

    v = sub.add_parser(
        "verify", help="run the R62 release gate")
    v.add_argument("--profile", default="final",
                   choices=["final"],
                   help="gate profile (final = everything)")
    v.add_argument("--output", default=os.path.join(
        REPO, "reports"), help="where gate JSON/log are written")
    v.set_defaults(func=_cmd_verify)
    return ap


# ---------------------------------------------------------------- --
# config assembly
# ---------------------------------------------------------------- --

def _resolve_config(a: argparse.Namespace) -> RuntimeConfig:
    cfg = RuntimeConfig()
    if a.config:
        cfg = RuntimeConfig.from_json(a.config)
    # CLI overrides (explicit flags win over the file)
    cfg.game = a.game
    cfg.episodes = a.episodes
    if a.seed is not None:
        cfg.seed_k = a.seed
    if a.seed_start is not None:
        cfg.seed_ladder_start = a.seed_start
    if a.seed_step is not None:
        cfg.seed_ladder_step = a.seed_step
    cfg.headless = not a.show_window
    if a.show_window:
        raise ConfigError(
            "--show-window is not supported: the libretro core runs "
            "headless (in-process, no GPU/X11). To watch the gameplay "
            "use --record and open video_ep*.gif afterwards.")
    if a.record:
        cfg.record = True
        cfg.video = True
    if a.screenshot:
        cfg.screenshot = True
    if a.max_frames is not None:
        cfg.max_frames_per_episode = a.max_frames
    if a.max_runtime is not None:
        cfg.max_runtime_s = a.max_runtime
    if a.verbose:
        cfg.verbose = True
    if a.output:
        cfg.output_dir = a.output
    elif not cfg.output_dir:
        cfg.output_dir = os.path.join(
            REPO, "scratch", "r62",
            "run_" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    os.makedirs(cfg.output_dir, exist_ok=True)
    return cfg.validated()


# ---------------------------------------------------------------- --
# play
# ---------------------------------------------------------------- --

def _cmd_play(a: argparse.Namespace) -> int:
    t0 = time.time()
    try:
        cfg = _resolve_config(a)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return e.exit_code

    stop_flag: Dict[str, Any] = {"stop": False, "reason": ""}

    def _on_sigint(signum, frame):      # noqa: ANN001
        stop_flag["stop"] = True
        stop_flag["reason"] = "SIGINT (Ctrl+C)"
    prev = signal.signal(signal.SIGINT, _on_sigint)

    print(f"ps1play runtime v{RUNTIME_VERSION} — game={cfg.game} "
          f"episodes={cfg.episodes or 'unlimited'} "
          f"max_frames/ep={cfg.max_frames_per_episode} "
          f"time_budget={cfg.max_runtime_s}s")
    print(f"output: {cfg.output_dir}")
    if cfg.seed_k is not None:
        print(f"seed k={cfg.seed_k}")
    tel = None
    engine = None
    code = EXIT_OK
    try:
        tel = TelemetryLog(
            os.path.join(cfg.output_dir, "events.jsonl"),
            run_meta={"cmd": "play", "game": cfg.game,
                      "argv": sys.argv[1:]},
            echo=False)
        from ps1play.runtime.engine import RuntimeEngine
        engine = RuntimeEngine(cfg, tel, stop_flag=stop_flag)
        try:
            assets = engine.preflight()
            print("preflight OK — ISO/model/BIOS/core verified:")
            for k in ("iso_sha256", "model_sha256"):
                if k in assets:
                    print(f"  {k}: {assets[k][:16]}…")
            engine.boot(assets)
        except Ps1RuntimeError as e:
            print(f"PREFLIGHT/BOOT FAILED: {e}", file=sys.stderr)
            code = e.exit_code
            raise
        results = engine.run()
        code = _print_summary(cfg, results)
        # a user-interrupted run reports 130 (SIGINT convention)
        if any(r.get("death_reason") == "emergency_stop"
               for r in results):
            code = 130
            print("run interrupted (emergency stop) — exit 130")
        return code
    except Ps1RuntimeError as e:
        if code == EXIT_OK:
            code = e.exit_code
        print(f"RUNTIME ERROR [{type(e).__name__}]: {e}",
              file=sys.stderr)
        return code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    finally:
        signal.signal(signal.SIGINT, prev)
        if tel is not None:
            tel.emit("run_end", exit_code=code,
                     wall_s=round(time.time() - t0, 2))
        if engine is not None:
            engine.close()
        if tel is not None:
            tel.close()


def _print_summary(cfg: RuntimeConfig,
                   results: List[Dict[str, Any]]) -> int:
    print("\n" + "=" * 64)
    print(f"RUN SUMMARY — {cfg.game}")
    print("=" * 64)
    if not results:
        print("no episodes ran")
        return 1
    n_played = n_alive = 0
    pipes_sum = 0
    for r in results:
        status = r["result"]
        mark = {"alive": "ALIVE", "death": "death", "stopped":
                "stopped", "error": "ERROR"}.get(status, status)
        line = (f"ep{r['episode']:03d} k={r['seed_k']:<4d} "
                f"{mark:<8} pipes={r['pipes']:<3d} "
                f"frames={r['frames']:<5d} flaps={r['flaps']:<4d} "
                f"wall={r['wall_s']:.1f}s")
        if r.get("video"):
            line += f"\n         video: {r['video']}"
        if r.get("trace_file"):
            line += f"\n         trace: {r['trace_file']}"
        if r.get("errors"):
            line += f"\n         errors: {r['errors'][:1]}"
        print(line)
        if status in ("alive", "death", "stopped"):
            n_played += 1
        if status == "alive":
            n_alive += 1
        if status in ("alive", "death"):
            pipes_sum += r["pipes"]
    played = [r for r in results
              if r["result"] in ("alive", "death")]
    print("-" * 64)
    print(f"episodes: {len(results)} | completed: {n_played} | "
          f"alive-at-budget: {n_alive}")
    if played:
        ps = [r["pipes"] for r in played]
        print(f"pipes: mean={sum(ps) / len(ps):.2f} "
              f"min={min(ps)} max={max(ps)}")
    print(f"results: {cfg.output_dir}{os.sep}episodes.jsonl")
    print(f"events : {cfg.output_dir}{os.sep}events.jsonl")
    failed = sum(1 for r in results if r["result"] == "error")
    return 1 if failed == len(results) else EXIT_OK


# ---------------------------------------------------------------- --
# verify
# ---------------------------------------------------------------- --

def _cmd_verify(a: argparse.Namespace) -> int:
    from ps1play.release_gate import run_release_gate
    return run_release_gate(profile=a.profile, output_dir=a.output)


def main() -> int:
    ap = _build_parser()
    a = ap.parse_args()
    try:
        return int(a.func(a))
    except Ps1RuntimeError as e:
        print(f"ERROR [{type(e).__name__}]: {e}", file=sys.stderr)
        return e.exit_code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

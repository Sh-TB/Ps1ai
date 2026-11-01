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
import subprocess
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
        "play", help="play a game autonomously (frozen policy or the "
                     "game's built-in policy)")
    p.add_argument("game", help="registered game id: flappybird | "
                                "tetrade (see ps1play/runtime/registry)")
    p.add_argument("--episodes", type=int, default=1,
                   help="number of consecutive autonomous episodes "
                        "(default 1)")
    p.add_argument("--seed", type=int, default=None,
                   help="the episode seed k (flappybird: the "
                        "RNG-seeding start press timing; tetrade: "
                        "recorded for labeling only — the zero-writes "
                        "rule never seeds the game RNG); default = "
                        "deterministic ladder 6, 12, 18, ...")
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

    k = sub.add_parser(
        "knowledge", help="per-game knowledge packages (R65): list / "
                          "export / validate / install / show")
    ksub = k.add_subparsers(dest="kcmd", required=True)

    kl = ksub.add_parser(
        "list", help="list exportable + installed game packages")
    kl.add_argument("--root", default=None,
                    help="package install root (default "
                         "<repo>/packages_installed)")
    kl.set_defaults(func=_cmd_knowledge_list)

    ke = ksub.add_parser(
        "export", help="export one game's knowledge package "
                       "(<game_id>.ps1game)")
    ke.add_argument("game", help="a game with a package spec "
                                 "(flappybird | tetrade | buzzybee | "
                                 "metal_slug_x)")
    ke.add_argument("--out", default=None,
                    help="output directory (default <repo>/download)")
    ke.set_defaults(func=_cmd_knowledge_export)

    kv = ksub.add_parser(
        "validate", help="validate a .ps1game archive "
                         "(structure, schema, hashes, compatibility)")
    kv.add_argument("package", help="path to a .ps1game file")
    kv.set_defaults(func=_cmd_knowledge_validate)

    ki = ksub.add_parser(
        "install", help="validate + install a .ps1game into an "
                        "isolated per-game directory")
    ki.add_argument("package", help="path to a .ps1game file")
    ki.add_argument("--root", default=None,
                    help="install root (default "
                         "<repo>/packages_installed)")
    ki.add_argument("--force", action="store_true",
                    help="re-install the SAME game_id+version")
    ki.set_defaults(func=_cmd_knowledge_install)

    ks = ksub.add_parser(
        "show", help="show a package's manifest summary (file or "
                     "installed game id)")
    ks.add_argument("what", help="a .ps1game path or a game id")
    ks.add_argument("--root", default=None, help="install root")
    ks.set_defaults(func=_cmd_knowledge_show)

    t = sub.add_parser(
        "test", help="run a game's knowledge-package contract tests")
    t.add_argument("game", help="registered game id")
    t.add_argument("--root", default=None, help="install root")
    t.add_argument("-k", dest="kt", default=None,
                   help="extra pytest -k expression")
    t.add_argument("--list", action="store_true",
                   help="only list the test files")
    t.set_defaults(func=_cmd_test)
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
    from ps1play.runtime.registry import progress_label_for  \
        # noqa: PLC0415
    try:
        prog = progress_label_for(cfg.game)
    except Exception:
        prog = "pipes"
    print("\n" + "=" * 64)
    print(f"RUN SUMMARY — {cfg.game}")
    print("=" * 64)
    if not results:
        print("no episodes ran")
        return 1
    n_played = n_alive = 0
    prog_sum = 0
    for r in results:
        status = r["result"]
        mark = {"alive": "ALIVE", "death": "death", "stopped":
                "stopped", "error": "ERROR"}.get(status, status)
        line = (f"ep{r['episode']:03d} k={r['seed_k']:<4d} "
                f"{mark:<8} {prog}={r['pipes']:<3d} "
                f"frames={r['frames']:<5d} acts={r['actions']:<4d} "
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
            prog_sum += r["pipes"]
    played = [r for r in results
              if r["result"] in ("alive", "death")]
    print("-" * 64)
    print(f"episodes: {len(results)} | completed: {n_played} | "
          f"alive-at-budget: {n_alive}")
    if played:
        ps = [r["pipes"] for r in played]
        print(f"{prog}: mean={sum(ps) / len(ps):.2f} "
              f"min={min(ps)} max={max(ps)}")
    print(f"results: {cfg.output_dir}{os.sep}episodes.jsonl")
    print(f"events : {cfg.output_dir}{os.sep}events.jsonl")
    failed = sum(1 for r in results if r["result"] == "error")
    return 1 if failed == len(results) else EXIT_OK


# ---------------------------------------------------------------- --
# knowledge packages (R65)
# ---------------------------------------------------------------- --

def _install_root(a: argparse.Namespace) -> str:
    return a.root or os.path.join(REPO, "packages_installed")


def _export_dir(a: argparse.Namespace) -> str:
    return a.out or os.path.join(REPO, "download")


def _cmd_knowledge_list(a: argparse.Namespace) -> int:
    from ps1play.knowledge.package import (exportable_games,
                                           read_installed_manifest)
    root = _install_root(a)
    ex = exportable_games()
    print("EXPORTABLE packages (build with: knowledge export GAME):")
    for g in ex:
        inst = read_installed_manifest(root, g)
        if inst:
            p = inst["package"]
            print(f"  {g:<14} v{p['version']:<8} "
                  f"{p['maturity']:<28} (installed)")
        else:
            print(f"  {g:<14} (not installed)")
    insts = []
    if os.path.isdir(root):
        for g in sorted(os.listdir(root)):
            gp = os.path.join(root, g)
            if os.path.isdir(gp) and g not in ex:
                insts.append(g)
    if insts:
        print(f"installed (no local spec — imported packages): "
              f"{', '.join(insts)}")
    print(f"install root: {root}")
    return EXIT_OK


def _cmd_knowledge_export(a: argparse.Namespace) -> int:
    from ps1play.knowledge.package import (PackageError, export_game)
    try:
        r = export_game(a.game, _export_dir(a))
    except PackageError as e:
        print(f"EXPORT FAILED: {e}", file=sys.stderr)
        return 2
    p = r["manifest"]["package"]
    print(f"exported: {r['path']}")
    print(f"  game: {p['game_id']} v{p['version']}  "
          f"maturity: {p['maturity']}")
    print(f"  files: {len(r['manifest']['contents'])}  "
          f"bytes: {r['bytes']}")
    print(f"  sha256: {r['sha256']}")
    print(f"  sidecar: {r['path']}.sha256")
    print("  (the archive re-validated against its own manifest)")
    return EXIT_OK


def _cmd_knowledge_validate(a: argparse.Namespace) -> int:
    from ps1play.knowledge.package import (PackageError,
                                           validate_package)
    try:
        man = validate_package(a.package)
    except PackageError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 2
    p = man["package"]
    print(f"VALID: {a.package}")
    print(f"  game: {p['game_id']} v{p['version']}  "
          f"maturity: {p['maturity']}")
    print(f"  game identity: serial={man['game_identity']['serial']} "
          f"region={man['game_identity']['region']} "
          f"revision={man['game_identity']['revision']}")
    print(f"  runtime compat: {man['runtime'].get(
        'runtime_version_compat')}")
    caps = man["capabilities"]
    print(f"  autonomous play: {caps.get('autonomous_play')}")
    print(f"  files: {len(man['contents'])} (every sha256 verified)")
    return EXIT_OK


def _cmd_knowledge_install(a: argparse.Namespace) -> int:
    from ps1play.knowledge.package import (PackageError,
                                           install_package)
    try:
        r = install_package(a.package, _install_root(a),
                            force=a.force)
    except PackageError as e:
        print(f"INSTALL FAILED: {e}", file=sys.stderr)
        return 2
    print(f"installed: {r['game_id']} v{r['version']} "
          f"({r['maturity']}) -> {r['installed_to']}")
    print(f"  files: {r['files']} (no package code was executed)")
    print("next: python3 -m ps1play knowledge list | "
          "test <game> | play <game>")
    return EXIT_OK


def _cmd_knowledge_show(a: argparse.Namespace) -> int:
    import json as _json
    from ps1play.knowledge.package import (PackageError,
                                           read_installed_manifest,
                                           validate_package)
    try:
        if a.what.endswith(".ps1game") and os.path.exists(a.what):
            man = validate_package(a.what)
            src = a.what
        else:
            man = read_installed_manifest(_install_root(a), a.what)
            if man is None:
                print(f"not installed and not a .ps1game file: "
                      f"{a.what}", file=sys.stderr)
                return 2
            src = "installed"
    except PackageError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(_json.dumps({
        "source": src,
        "package": man["package"],
        "game_identity": man["game_identity"],
        "runtime": man["runtime"],
        "capabilities": man["capabilities"],
        "legal": man["legal"],
        "contents": [{"path": c["path"], "role": c["role"],
                      "bytes": c["bytes"]} for c in man["contents"]],
    }, indent=1))
    return EXIT_OK


def _cmd_test(a: argparse.Namespace) -> int:
    """Run a game's knowledge-package tests (the same files the
    package ships).  Game-specific test data and semantics stay in
    the game's own package; the generic runner never mixes them."""
    from ps1play.knowledge.package import (PackageError,
                                           read_installed_manifest,
                                           spec_for_game)
    test_files = []
    try:
        spec = spec_for_game(a.game)
        for entry in spec["files"]:
            src = entry[0]
            arc = entry[1]
            role = entry[2]
            if role != "test":
                continue
            if arc.startswith("tests/") and os.path.exists(src):
                test_files.append(src)
    except PackageError:
        spec = None
    if not test_files:
        root = _install_root(a)
        man = read_installed_manifest(root, a.game)
        if man:
            for c in man["contents"]:
                if c.get("role") == "test":
                    p = os.path.join(root, a.game,
                                     man["package"]["version"],
                                     *c["path"].split("/"))
                    if os.path.exists(p):
                        test_files.append(p)
    if a.list:
        for p in test_files:
            print(p)
        if not test_files:
            print(f"(no test files — check what this package "
                  f"documents instead)")
        return EXIT_OK
    if not test_files:
        caps = (spec or {}).get("capabilities", {})
        print(f"{a.game}: this package ships no automated test "
              f"files (maturity "
              f"{(spec or {}).get('maturity', '?')}).")
        for d in caps.get("diagnostics", []) or []:
            print(f"  diagnostic: {d}")
        return EXIT_OK
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, "-m", "pytest", *sorted(test_files),
           "-q", "-p", "no:cacheprovider"]
    if a.kt:
        cmd += ["-k", a.kt]
    print("running:", " ".join(cmd[2:]))
    rc = subprocess.call(cmd, env=env, cwd=REPO)
    return rc if rc in (0, 1) else 1


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

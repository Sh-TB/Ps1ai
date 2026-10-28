#!/usr/bin/env python3
"""ps1play CLI — the same API as PS1Play, for humans and any agent shell.

All outputs are compact JSON (token-minimal for LLM agents).
Examples:
  ps1play.py info --game "Metal Slug X (USA).cue"
  ps1play.py boot-run          # boot script of the plugin
  ps1play.py observe
  ps1play.py discover --buttons RIGHT
  ps1play.py play --frames 3000
  ps1play.py save stage1 | load stage1 | resume
  ps1play.py report
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # repo root (ps1play)
sys.path.insert(0, _HERE)                            # scripts (helpers)

# knowledge-surface delegation (Issue #10 addendum): capsule/cache/intake
# subcommands live in ps1play_knowledge.py; this CLI stays the gameplay
# surface and forwards the knowledge commands so the proposed
# `ps1play_cli.py intake-game ...` interface works.
_K = {"capsule-validate", "capsule-query", "capsule-build",
      "cache-stat", "intake-game"}
if len(sys.argv) > 1 and sys.argv[1] in _K:
    import ps1play_knowledge
    sys.exit(ps1play_knowledge.main(sys.argv[1:]))

from ps1play.api import PS1Play  # noqa: E402

DEFAULT_GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"


def build(p):
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info")
    s = sub.add_parser("boot-run"); s.add_argument("--quiet", action="store_true")
    sub.add_parser("observe")
    s = sub.add_parser("discover"); s.add_argument("--buttons", default="RIGHT")
    s.add_argument("--no-echo", action="store_true")
    s = sub.add_parser("discover-progress"); s.add_argument("--frames", type=int, default=180)
    s = sub.add_parser("diff"); s.add_argument("--frames", type=int, default=45)
    s.add_argument("--buttons", default=None)
    s = sub.add_parser("play"); s.add_argument("--frames", type=int, default=1800)
    s.add_argument("--chunk", type=int, default=60)
    s.add_argument("--checkpoint", type=int, default=1800)
    s = sub.add_parser("save"); s.add_argument("name")
    s = sub.add_parser("load"); s.add_argument("name")
    sub.add_parser("resume")
    sub.add_parser("profile")
    sub.add_parser("report")
    sub.add_parser("states")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--core", default=None)
    build(ap)
    args = ap.parse_args()
    kw = {}
    if args.core:
        kw["core"] = args.core
    p = PS1Play(args.game, **kw)

    if args.cmd == "info":
        print(json.dumps({"game": args.game, "core": p.core_path}, indent=1))
        return
    p.boot()
    if args.cmd == "boot-run":
        print(json.dumps(p.run_steps(p.plugin.boot_script())))
    elif args.cmd == "observe":
        print(json.dumps(p.observe()))
    elif args.cmd == "discover":
        print(json.dumps(p.discover(args.buttons, echo=not args.no_echo),
                         indent=1, default=str))
        print(json.dumps(p.save_profile()))
    elif args.cmd == "discover-progress":
        print(json.dumps(p.discover_progress(args.frames), default=str))
        print(json.dumps(p.save_profile()))
    elif args.cmd == "diff":
        print(json.dumps(p.diff_now(args.frames, args.buttons), default=str))
    elif args.cmd == "play":
        print(json.dumps(p.play(args.frames, chunk=args.chunk,
                                checkpoint_every=args.checkpoint)))
    elif args.cmd == "save":
        print(json.dumps(p.save_state(args.name)))
    elif args.cmd == "load":
        print(json.dumps(p.load_state(args.name)))
    elif args.cmd == "resume":
        print(json.dumps(p.resume()))
    elif args.cmd == "states":
        print(json.dumps(p.states.list(), indent=1))
    elif args.cmd == "profile":
        print(json.dumps(p.profile, indent=1, default=str))
    elif args.cmd == "report":
        print(json.dumps(p.report(), indent=1, default=str))
    p.core.shutdown()


if __name__ == "__main__":
    main()

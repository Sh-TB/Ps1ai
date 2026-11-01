"""R62 CLI + fault-injection tests (Section 6 + Section 9).

The one-command UX contract: argument validation, exit codes,
config-file handling, the --show-window honesty error, and the
documented behaviors that can be tested without a full emulator run.
"""
import json
import os
import subprocess
import sys

REPO = "/home/z/my-project/ps1ai"


def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "ps1play", *args], cwd=REPO,
        capture_output=True, text=True, timeout=120)


class TestCliSurface:
    def test_help_exits_zero(self):
        r = _cli("--help")
        assert r.returncode == 0
        assert "play" in r.stdout and "verify" in r.stdout

    def test_play_help_documents_all_mission_options(self):
        r = _cli("play", "--help")
        assert r.returncode == 0
        for opt in ("--episodes", "--seed", "--headless",
                    "--show-window", "--record", "--screenshot",
                    "--max-frames", "--max-runtime", "--config",
                    "--output", "--verbose"):
            assert opt in r.stdout, opt

    def test_unknown_game_rejected_exit_2(self):
        r = _cli("play", "doom", "--output", "/tmp/r62_cli_x")
        assert r.returncode == 2
        assert "unknown game" in (r.stderr + r.stdout).lower()

    def test_show_window_honest_error(self):
        r = _cli("play", "flappybird", "--show-window",
                 "--output", "/tmp/r62_cli_x")
        assert r.returncode == 2
        assert "not supported" in (r.stderr + r.stdout).lower()
        assert "--record" in (r.stderr + r.stdout)

    def test_unbounded_run_rejected(self):
        # episodes=0 with the fixed restart policy must never start
        r = _cli("play", "flappybird", "--episodes", "0",
                 "--output", "/tmp/r62_cli_x")
        assert r.returncode == 2

    def test_bad_config_file_exit_2(self, tmp_path):
        p = tmp_path / "cfg.json"
        p.write_text("{broken json")
        r = _cli("play", "flappybird", "--config", str(p),
                 "--output", "/tmp/r62_cli_x")
        assert r.returncode == 2
        assert "json" in (r.stderr + r.stdout).lower()

    def test_config_file_with_output_dir(self, tmp_path):
        out = tmp_path / "run"
        cfg = {"game": "flappybird", "episodes": 1,
               "max_frames_per_episode": 10,
               "max_runtime_s": 30,
               "output_dir": str(out)}
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps(cfg))
        # a tiny episode budget: the run boots, plays 10 frames, stops
        r = _cli("play", "flappybird", "--config", str(p))
        # emulator present on dev machines -> a real (tiny) run works
        iso = "/home/z/my-project/emu/games_homebrew/flappybird.cue"
        if not os.path.exists(iso):
            assert r.returncode in (3,)   # asset error, honest
            return
        assert r.returncode == 0, r.stderr[-400:]
        assert (out / "episodes.jsonl").exists()
        assert (out / "events.jsonl").exists()
        assert (out / "runtime_manifest.json").exists()
        rec = json.loads((out / "episodes.jsonl").read_text().strip())
        assert rec["frames"] == 10 and rec["result"] == "alive"


class TestFaultInjectionOffline:
    def test_missing_iso_exit_3(self):
        r = _cli("play", "flappybird", "--output", "/tmp/r62_cli_y",
                 "--max-frames", "10")
        assert r.returncode in (0, 3)   # 0 when assets exist, else 3
        iso = "/home/z/my-project/emu/games_homebrew/flappybird.cue"
        assert (r.returncode == 0) == os.path.exists(iso)

    def test_exit_code_vocabulary(self):
        from ps1play.runtime.errors import (AssetError, ConfigError,
                                            ControllerError,
                                            EmulatorError,
                                            LifecycleError,
                                            Ps1RuntimeError,
                                            RuntimePolicyError)
        codes = {AssetError: 3, ConfigError: 2, EmulatorError: 4,
                 ControllerError: 5, RuntimePolicyError: 6,
                 LifecycleError: 8, Ps1RuntimeError: 1}
        for cls, want in codes.items():
            assert cls("x").exit_code == want

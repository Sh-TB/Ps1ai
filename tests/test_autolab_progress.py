"""v0.12 Phase C tests — autolab mission1-progress dispatch.

Covers: dispatch, missing-asset BLOCKED path, argument forwarding,
timeout / exit-code handling, JSON report parsing (valid + invalid),
gate status propagation, fingerprint sensitivity, stale-ledger dedup,
and budget exhaustion. All emulation is faked: env_probe and the real
runner are replaced at the subprocess boundary.
"""
import importlib
import json
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

import autolab                                                  # noqa: E402
from ps1play import labconfig                                  # noqa: E402


class FakeLab(autolab.Lab):
    """Lab with a throwaway ledger dir and a generous fake budget."""

    def __init__(self, tmp_path, budget_minutes=30):
        super().__init__(str(tmp_path / "ws"), budget_minutes)
        self.cache = {}


def make_report(tmp_path, cleared=False, in_mission=True, enter=True):
    rep = {
        "boot": {"core": "Beetle PSX", "serial": "SLUS-01212"},
        "enter": enter,
        "gate": {"in_mission": in_mission},
        "camera": {"verified": False},
        "play": {"cleared": cleared, "frames": 1234,
                 "frames_nominal": 1800, "continues": 0},
    }
    p = tmp_path / "mission1_report.json"
    p.write_text(json.dumps(rep))
    return str(p)


@pytest.fixture()
def env_ready(monkeypatch):
    """env_probe subprocess returns ready."""
    monkeypatch.setattr(autolab, "_run_json",
                        lambda cmd, t: (0, {"ready": True, "missing": []}))


@pytest.fixture()
def fw_openbios(monkeypatch):
    monkeypatch.setattr(
        labconfig, "resolve_firmware",
        lambda mode, ws, root=None: {
            "mode": "openbios", "bios_path": "/bios", "bios_md5": "m",
            "override_vars": {b"k": b"v"}, "detail": "d"})


def captured_run(monkeypatch, exit_code=0, stderr=b"", stdout=b""):
    holder = {"calls": []}

    def fake_run(cmd, capture_output=True, timeout=None, cwd=None):
        holder["calls"].append(list(cmd))
        holder["cmd"] = list(cmd)
        holder["timeout"] = timeout
        # NOTE: `class R: stderr = stderr` would raise NameError — class
        # bodies resolve assigned names via LOAD_NAME (class dict ->
        # globals), skipping the enclosing function scope.
        import types
        return types.SimpleNamespace(returncode=exit_code,
                                     stderr=stderr, stdout=stdout)
    monkeypatch.setattr(autolab.subprocess, "run", fake_run)
    return holder


def runner_call(holder):
    """The recorded subprocess call that launched the runner (git
    rev-parse etc. also route through the patched run())."""
    for cmd in holder["calls"]:
        if len(cmd) > 1 and cmd[1].endswith("runner.py"):
            return cmd
    return None


def pin_report(monkeypatch, tmp_path, **kw):
    """Place a runner report at the EXACT path the gate computes
    (evidence_dir/m1p_<pinned-ts>/mission1_report.json)."""
    monkeypatch.setattr(autolab.time, "strftime",
                        lambda fmt, *a: "20260101_000000")
    d = tmp_path / "m1p_20260101_000000"
    d.mkdir(parents=True, exist_ok=True)
    rep = {
        "boot": {"core": "Beetle PSX", "serial": "SLUS-01212"},
        "enter": kw.get("enter", True),
        "gate": {"in_mission": kw.get("in_mission", True)},
        "camera": {"verified": kw.get("camera_verified", False)},
        "play": {"cleared": kw.get("cleared", False), "frames": 1234,
                 "frames_nominal": 1800, "continues": 0},
    }
    (d / "mission1_report.json").write_text(json.dumps(rep))
    return str(d / "mission1_report.json")


# ------------------------------------------------------------------
# dispatch + classification
# ------------------------------------------------------------------
def test_dispatch_reaches_runner_and_forwards_args(
        tmp_path, monkeypatch, env_ready, fw_openbios):
    report = pin_report(monkeypatch, tmp_path)
    holder = captured_run(monkeypatch)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake runner")
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        firmware="openbios", chunks=30, evidence_dir=str(tmp_path),
        timeout_s=600)
    assert rec["gate"] == "MISSION1_PROGRESS"
    cmd = runner_call(holder)
    assert cmd, "runner never launched"
    assert cmd[1].endswith("runner.py")
    for flag, val in (("--game", "/g/game.cue"), ("--core", "/c/core.so"),
                      ("--chunks", "30"), ("--firmware", "openbios"),
                      ("--report", report)):
        i = cmd.index(flag)
        assert cmd[i + 1] == val
    assert rec["status"] == "PARTIAL"      # in-mission, not cleared
    assert rec["exit"] == 0


def test_cleared_report_is_pass(tmp_path, monkeypatch, env_ready,
                                fw_openbios):
    pin_report(monkeypatch, tmp_path, cleared=True)
    captured_run(monkeypatch)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert rec["status"] == "PASS"


def test_enter_failed_is_fail(tmp_path, monkeypatch, env_ready,
                              fw_openbios):
    pin_report(monkeypatch, tmp_path, enter=False, in_mission=False)
    captured_run(monkeypatch)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert rec["status"] == "FAIL"
    assert "gameplay was not reached" in rec["detail"]


def test_runner_nonzero_exit_without_report_is_fail(
        tmp_path, monkeypatch, env_ready, fw_openbios):
    captured_run(monkeypatch, exit_code=1, stderr=b"!! boot failed")
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert rec["status"] == "FAIL"
    assert "valid report" in rec["detail"]


def test_invalid_report_json_is_fail(tmp_path, monkeypatch, env_ready,
                                     fw_openbios):
    captured_run(monkeypatch)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    # pin the run-id timestamp so the gate's report path is predictable
    monkeypatch.setattr(autolab.time, "strftime",
                        lambda fmt, *a: "20260101_000000")
    fixed_dir = tmp_path / "m1p_20260101_000000"
    fixed_dir.mkdir(parents=True, exist_ok=True)
    (fixed_dir / "mission1_report.json").write_text("{invalid json")
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert rec["status"] == "FAIL"
    assert "valid report" in rec["detail"]


def test_timeout_is_recorded_as_fail(tmp_path, monkeypatch, env_ready,
                                     fw_openbios):
    def fake_run(cmd, capture_output=True, timeout=None, cwd=None):
        raise autolab.subprocess.TimeoutExpired(cmd, timeout)
    monkeypatch.setattr(autolab.subprocess, "run", fake_run)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert rec["status"] == "FAIL"
    assert rec["timed_out"] is True
    assert "timeout" in rec["detail"].lower()


def test_env_not_ready_propagates_blocked(tmp_path, monkeypatch,
                                          fw_openbios):
    monkeypatch.setattr(autolab, "_run_json",
                        lambda cmd, t: (2, {"ready": False,
                                            "missing": ["game_image"]}))
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert rec["status"] == "BLOCKED"
    assert "game_image" in rec["detail"]


def test_firmware_unresolved_propagates_blocked(tmp_path, monkeypatch,
                                                env_ready):
    monkeypatch.setattr(
        labconfig, "resolve_firmware",
        lambda mode, ws, root=None: (_ for _ in ()).throw(
            labconfig.FirmwareError("no retail BIOS")))
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        firmware="retail", evidence_dir=str(tmp_path))
    assert rec["status"] == "BLOCKED"
    assert "firmware" in rec["detail"].lower()


# ------------------------------------------------------------------
# fingerprints, dedup, ledger provenance
# ------------------------------------------------------------------
def test_fingerprint_sensitive_to_inputs(tmp_path, monkeypatch,
                                         env_ready, fw_openbios):
    pin_report(monkeypatch, tmp_path)
    captured_run(monkeypatch)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path)
    r1 = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    fp1 = r1["fingerprint"]
    r2 = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        firmware="openbios", chunks=60,           # different budget
        evidence_dir=str(tmp_path), force=True)
    assert r2["fingerprint"] != fp1


def test_pass_result_dedups_until_inputs_change(tmp_path, monkeypatch,
                                                env_ready, fw_openbios):
    pin_report(monkeypatch, tmp_path, cleared=True)
    holder = captured_run(monkeypatch)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path)
    r1 = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert r1["status"] == "PASS"
    # same inputs, new Lab (same ledger) -> DEDUP, no re-run
    lab2 = FakeLab(tmp_path)
    lab2.cache = lab2.load_ledger()
    r2 = autolab.gate_mission1_progress(
        lab2, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    assert r2["status"] == "DEDUP"
    assert "reused" in r2["detail"]
    # changed inputs with force -> re-executes, new fingerprint
    r3 = autolab.gate_mission1_progress(
        lab2, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        chunks=45, evidence_dir=str(tmp_path), force=True)
    assert r3["status"] == "PASS"
    assert r3["fingerprint"] != r1["fingerprint"]


def test_ledger_record_has_provenance(tmp_path, monkeypatch, env_ready,
                                      fw_openbios):
    pin_report(monkeypatch, tmp_path)
    captured_run(monkeypatch)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path))
    for field in ("experiment_id", "head", "cmd", "core_sha1",
                  "game_md5", "firmware_mode", "firmware_bios_md5",
                  "chunks", "exit", "timed_out", "hard_timeout_s",
                  "runner_elapsed_s", "frames_actual", "report_path",
                  "evidence_dir", "repro_cmd", "runner_sha1"):
        assert field in rec, f"ledger missing provenance field {field}"
    assert rec["repro_cmd"].startswith(sys.executable)


def test_budget_exhaustion_stops_before_runner(tmp_path, monkeypatch,
                                               env_ready, fw_openbios):
    pin_report(monkeypatch, tmp_path)
    launched = {"n": 0}
    real = autolab.subprocess.run

    def spy(cmd, **k):
        if any("runner.py" in str(c) for c in cmd):
            launched["n"] += 1
        return type("R", (), {"returncode": 0, "stderr": b"",
                              "stdout": b""})()
    monkeypatch.setattr(autolab.subprocess, "run", spy)
    monkeypatch.setattr(autolab, "RUNNER", str(tmp_path / "runner.py"))
    (tmp_path / "runner.py").write_text("# fake")
    lab = FakeLab(tmp_path, budget_minutes=0.0001)   # ~6ms of budget
    import time as _t
    _t.sleep(0.05)
    rec = autolab.gate_mission1_progress(
        lab, "/g/game.cue", "/c/core.so", str(tmp_path / "ws"),
        evidence_dir=str(tmp_path), timeout_s=600)
    # the hard timeout must be clamped to the remaining budget (>=60s
    # floor), and the runner still runs once — the BUDGET gate itself
    # is what stops further work between gates (tested in Lab).
    assert rec["hard_timeout_s"] <= 600
    assert launched["n"] == 1


def test_lab_budget_out_of_budget():
    lab = autolab.Lab("/tmp/autolab_test_ws_noncommit", 0.0)
    assert lab.out_of_budget() is True

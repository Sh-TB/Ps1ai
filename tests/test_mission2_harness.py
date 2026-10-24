"""Mission 2 harness tests (Issue #9 §3-4): decision log, scorecard,
run comparison, tool value, repeatability — offline, deterministic."""
import json
import os

import pytest

from ps1play.experiments import (
    DecisionLog, compare_runs, repeatability, score_run, tool_value,
    CONFIRMED, INFERRED, UNKNOWN,
)


@pytest.fixture
def tmp_run(tmp_path):
    def make(run_id, plan):
        log = DecisionLog(tmp_path, run_id, track=plan.get("track", "A"),
                          commit="deadbeef", plugin="test", game="testgame",
                          emulator="beetle", checkpoint_id="ck1")
        for i, step in enumerate(plan["steps"]):
            log.decision(
                chunk=i, game_frame=i * 60,
                observation=step.get("obs",
                                     {"px": {"value": 100 + i, "provenance": CONFIRMED}}),
                candidates=step.get("cands",
                                    [{"action": "advance", "rejected": False,
                                      "why": "default"}]),
                selected=step.get("sel", {"action": "advance",
                                          "buttons": ["RIGHT"], "frames": 60,
                                          "expected": "move forward"}),
                actual=step.get("actual", {"post_state": {"px": 100 + i + 10},
                                           "prediction_correct": True}),
                objective=step.get("obj", {}),
            )
        log.note("boot", serial="TEST-000")
        return log.write_summary()
    return make


def test_decision_log_roundtrip(tmp_path):
    log = DecisionLog(tmp_path, "r1", track="A", commit="c0ffee", plugin="p",
                      game="g", emulator="beetle", checkpoint_id="ck")
    log.decision(0, 0, {"px": {"value": 1.0, "provenance": CONFIRMED}},
                 [{"action": "advance", "rejected": False, "why": "safe"}],
                 {"action": "advance", "buttons": ["RIGHT"], "frames": 60,
                  "expected": "px+10"},
                 actual={"post_state": {"px": 11.0}, "prediction_correct": True},
                 objective={"progress": 11.0, "confidence": CONFIRMED})
    log.note("checkpoint", name="ck")
    header, rows = None, []
    with open(log.path) as f:
        for line in f:
            d = json.loads(line)
            if "header" in d:
                header = d["header"]
            else:
                rows.append(d)
    assert header["run_id"] == "r1"
    assert header["track"] == "A"
    assert len(rows) == 2
    assert rows[0]["selected"]["buttons"] == ["RIGHT"]
    assert log.counters["decisions"] == 1
    assert log.counters["prediction_correct"] == 1


def test_counters_deaths_damage_stall(tmp_path):
    log = DecisionLog(tmp_path, "r2", track="C", commit="x", plugin="p",
                      game="g", emulator="beetle")
    log.decision(0, 0, {}, [], {"action": "a", "frames": 60},
                 actual={"death": True, "damage": 291, "stall": False,
                         "prediction_correct": False})
    log.decision(1, 60, {}, [], {"action": "recover", "frames": 60},
                 actual={"recovery": "checkpoint_restore", "restored": True})
    assert log.counters["deaths"] == 1
    assert log.counters["damage_events"] == 1
    assert log.counters["recoveries"] == 1
    assert log.counters["prediction_wrong"] == 1


def test_score_run_primary(tmp_path):
    log = DecisionLog(tmp_path, "r3", track="A", commit="x", plugin="p",
                      game="g", emulator="beetle")
    for i in range(10):
        log.decision(i, i * 60, {"px": {"value": i * 10.0, "provenance": CONFIRMED}},
                     [], {"action": "advance", "frames": 60},
                     actual={"post_state": {"px": i * 10.0 + 10},
                             "prediction_correct": True})
    # inject 2 damage + 1 death + 1 stall
    log.decision(10, 600, {}, [], {"action": "advance", "frames": 60},
                 actual={"post_state": {"px": 110}, "damage": 25, "stall": True,
                         "prediction_correct": False})
    log.decision(11, 660, {}, [], {"action": "hop", "frames": 60},
                 actual={"post_state": {"px": 110}, "death": True,
                         "prediction_correct": False})
    log.write_summary()
    s = score_run(log.path)
    assert s["counters"]["deaths"] == 1
    assert s["counters"]["damage"] == 1
    assert s["counters"]["stalls"] == 1
    assert s["primary"]["verified_progress"] == 110
    assert s["primary"]["progress_provenance"] == CONFIRMED
    assert 0 < s["primary"]["decision_quality"] < 1
    assert s["primary"]["survival_events_per_100_decisions"] > 0


def test_compare_runs_first_divergence(tmp_path):
    common = {"obs": {"px": {"value": 100.0, "provenance": CONFIRMED}}}
    la = DecisionLog(tmp_path, "ra", track="A", commit="x", plugin="p",
                     game="g", emulator="beetle")
    lb = DecisionLog(tmp_path, "rb", track="C", commit="x", plugin="p",
                     game="g", emulator="beetle")
    for i in range(6):
        act = "advance"
        px = 100 + i * 10
        la.decision(i, i * 60, common, [], {"action": act, "frames": 60},
                    actual={"post_state": {"px": px}, "prediction_correct": True})
    for i in range(6):
        act = "advance"
        px = 100 + i * 10
        actual = {"post_state": {"px": px}, "prediction_correct": True}
        if i == 3:
            act, actual = "stop_kill", {"post_state": {"px": 130},
                                        "prediction_correct": True}
        lb.decision(i, i * 60, common, [], {"action": act, "frames": 60},
                    actual=actual)
    res = compare_runs(la.path, lb.path)
    assert res["first_divergent_chunk"] == 3
    # B reaches 140 (its chunk-5 px 100+50) vs A 150 — no improvement
    assert res["objective_improved_b_over_a"] is False


def test_tool_value_and_repeatability(tmp_path):
    tv = tool_value(100.0, 30.0, 20.0)
    assert tv["net_tool_value_s"] == 50.0
    paths = []
    for k in range(3):
        log = DecisionLog(tmp_path, f"rep{k}", track="A", commit="x",
                          plugin="p", game="g", emulator="beetle")
        for i in range(5):
            log.decision(i, i * 60, {}, [], {"action": "advance", "frames": 60},
                         actual={"post_state": {"px": 50.0}})
        log.write_summary()
        paths.append(log.path)
    r = repeatability(paths)
    assert r["repeatable"] is True
    assert r["runs"] == 3


def test_unknown_provenance_never_confirmed(tmp_path):
    log = DecisionLog(tmp_path, "u1", track="A", commit="x", plugin="p",
                      game="g", emulator="beetle")
    log.decision(0, 0, {"enemy_kind": {"value": "soldier",
                                       "provenance": INFERRED},
                        "threat": {"value": None, "provenance": UNKNOWN}},
                 [], {"action": "observe", "frames": 60})
    s = score_run(log.path)
    assert s["counters"]["decisions"] == 1
    assert s["primary"]["verified_progress"] is None  # no px in actual

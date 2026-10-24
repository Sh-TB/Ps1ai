"""Mission 2 scorecard (Issue #9 §4) — measure gameplay, not activity.

Primary outcomes (per §4): verified objective progress, completion rate,
survival, stall rate, recovery quality, decision quality, repeatability,
generalization. Efficiency outcomes: wall-clock, decisions, failed
experiments. Tool value: net = baseline_cost − assisted_cost − setup_cost.

No single misleading composite score; every number is independently
checkable from the decision logs.
"""
from __future__ import annotations

from .decision_log import load_decisions

TRACKS = {"A": "manual", "B": "assisted", "C": "algorithm", "D": "combined"}


def _dist_progress(rows):
    """Furthest verified px progress (MSX convention) as max over runs of
    max px observed with CONFIRMED provenance."""
    best = None
    for r in rows:
        px = (r.get("actual") or {}).get("post_state", {}).get("px")
        if px is None:
            continue
        if best is None or px > best:
            best = px
    return best


def score_run(path, objective_key="px"):
    """Score one decision log. objective_key picks the objective field."""
    header, rows = load_decisions(path)
    counters = {
        "deaths": sum(1 for r in rows if (r.get("actual") or {}).get("death")),
        "damage": sum(1 for r in rows if (r.get("actual") or {}).get("damage")),
        "stalls": sum(1 for r in rows if (r.get("actual") or {}).get("stall")),
        "recoveries": sum(1 for r in rows
                          if (r.get("actual") or {}).get("recovery")),
        "decisions": len(rows),
        "pred_ok": sum(1 for r in rows
                       if (r.get("actual") or {}).get("prediction_correct") is True),
        "pred_bad": sum(1 for r in rows
                        if (r.get("actual") or {}).get("prediction_correct") is False),
    }
    deaths = counters["deaths"]
    n = max(counters["decisions"], 1)
    # decision quality: fraction of selected actions achieving their purpose
    decision_quality = (counters["pred_ok"] /
                        max(counters["pred_ok"] + counters["pred_bad"], 1))
    stall_rate = counters["stalls"] / n
    # recovery quality: recoveries / recoverable failures (deaths+damage)
    recoverable = counters["deaths"] + counters["damage"]
    recovery_quality = (counters["recoveries"] / recoverable
                        if recoverable else None)
    # survival: damage+death events per 100 decisions
    survival = 100.0 * (deaths + counters["damage"]) / n
    # verified objective progress: max over actual post-state of the key;
    # provenance carries forward from the last observation that declared it
    # (a post-state read without a fresh observation inherits the previous
    # provenance instead of silently dropping the claim's evidence level)
    progress, progress_conf = None, None
    for r in rows:
        st = (r.get("actual") or {}).get("post_state") or {}
        if objective_key in st:
            v = st[objective_key]
            prov = ((r.get("observation") or {})
                    .get(objective_key, {})
                    .get("provenance"))
            if prov is not None:
                progress_conf = prov
            if progress is None or v > progress:
                progress = v
    return {
        "header": header,
        "counters": counters,
        "primary": {
            "verified_progress": progress,
            "progress_provenance": progress_conf,
            "survival_events_per_100_decisions": round(survival, 2),
            "stall_rate": round(stall_rate, 3),
            "recovery_quality": (round(recovery_quality, 3)
                                 if recovery_quality is not None else None),
            "decision_quality": round(decision_quality, 3),
        },
    }


def compare_runs(path_a, path_b, objective_key="px"):
    """§3: same-checkpoint comparison + first decision divergence.

    Returns both scorecards, the first chunk where the two runs' selected
    actions differ, and whether the divergence improved the objective.
    """
    sa, sb = score_run(path_a, objective_key), score_run(path_b, objective_key)
    _, rows_a = load_decisions(path_a)
    _, rows_b = load_decisions(path_b)
    first = None
    for ra, rb in zip(rows_a, rows_b):
        sa_act = (ra.get("selected") or {}).get("action")
        sb_act = (rb.get("selected") or {}).get("action")
        if sa_act != sb_act:
            first = ra.get("chunk")
            break
    pa, pb = sa["primary"]["verified_progress"], sb["primary"]["verified_progress"]
    improved = None
    if pa is not None and pb is not None:
        improved = pb > pa
    return {
        "run_a": {"path": path_a, "score": sa},
        "run_b": {"path": path_b, "score": sb},
        "first_divergent_chunk": first,
        "objective_improved_b_over_a": improved,
    }


def tool_value(baseline_cost_s, assisted_cost_s, setup_cost_s):
    """§4: Net tool value = baseline cost − assisted cost − setup cost."""
    return {
        "baseline_cost_s": baseline_cost_s,
        "assisted_cost_s": assisted_cost_s,
        "setup_cost_s": setup_cost_s,
        "net_tool_value_s": baseline_cost_s - assisted_cost_s - setup_cost_s,
    }


def repeatability(paths, objective_key="px"):
    """Repeatability: same strategy from equivalent states — share of runs
    reaching the same verified progress outcome."""
    scores = [score_run(p, objective_key) for p in paths]
    progs = [s["primary"]["verified_progress"] for s in scores]
    distinct = len({p for p in progs})
    return {
        "runs": len(paths),
        "distinct_outcomes": distinct,
        "repeatable": distinct == 1,
        "progress_values": progs,
    }

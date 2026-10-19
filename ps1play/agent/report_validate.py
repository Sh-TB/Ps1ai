"""report_validate.py — self-consistency checks for mission reports.

The v0.5 report shipped internally contradictory data:
  play.score_start == play.score_end == 200 while telemetry rows record
  scores of 96..252; `kills_est` counted score jumps though 18 continues
  reset the score; telemetry "bombs" rose 0 -> 30 although grenades can
  only decrement the counter (re-anchors latched onto wrong words).

validate_report() turns every such contradiction into a named finding.
`run_mission1_legit.py` refuses to write a report that fails validation
(its own freshly built report), and the regression test proves the
validator FAILS on the original v4 report fixture and PASSES on a
consistent one.
"""
import math


def _telemetry_scores(report):
    tel = report.get("telemetry") or []
    return [r.get("score") for r in tel if r.get("score") is not None]


def validate_report(report):
    """Return a list of findings; [] means self-consistent.

    Each finding: {"code", "detail"}. Codes are stable strings so tests
    and tooling can match them.
    """
    f = []
    play = report.get("play") or {}
    s_start = play.get("score_start")
    s_end = play.get("score_end")
    scores = _telemetry_scores(report)

    # --- score consistency -------------------------------------------------
    # The v0.5 bug shipped score_start == score_end == 200 while telemetry
    # visited 40..252 with 18 score-resetting continues unaccounted.
    # start==end is only consistent if every excursion beyond the
    # endpoints is explained by a REPORTED reset.
    if scores and s_start is not None and s_end is not None:
        if s_start == s_end and (min(scores) < min(s_start, s_end)
                                 or max(scores) > max(s_start, s_end)) \
                and not play.get("score_resets"):
            f.append({
                "code": "SCORE_RANGE_CONTRADICTION",
                "detail": f"score_start==score_end=={s_start} but "
                          f"telemetry visited [{min(scores)}, "
                          f"{max(scores)}]; score resets were not "
                          f"accounted for (v0.5 continue bug)"})
    # --- kill accounting ----------------------------------------------------
    kills = play.get("kills_est")
    if kills is not None:
        if kills and not report.get("kill_evidence") \
                and report.get("mode") == "legit-inputs-only":
            f.append({
                "code": "KILLS_NOT_EVIDENCED",
                "detail": f"kills_est={kills} reported without "
                          f"kill_evidence; score deltas alone are not "
                          f"verified kills"})
    # verified kills must be backed by VERIFIED kill events in the log
    kv = play.get("kills_verified", 0) or 0
    if kv:
        ev_counts = (report.get("events") or {}).get("counts") or {}
        backed = ev_counts.get("ENEMY_KILL_VERIFIED", {}).get("VERIFIED", 0)
        if backed < kv:
            f.append({
                "code": "KILLS_VERIFIED_UNBACKED",
                "detail": f"play.kills_verified={kv} but the event log "
                          f"holds {backed} VERIFIED kill events"})

    # --- observation plausibility -------------------------------------------
    bombs = [r.get("bombs") for r in (report.get("telemetry") or [])
             if isinstance(r.get("bombs"), int)]
    if bombs and max(bombs) > 40:
        f.append({
            "code": "BOMBS_OUT_OF_RANGE",
            "detail": f"bombs reached {max(bombs)}; plausible range is "
                      f"0..40 — anchor invalid at some point"})
    if len(bombs) >= 2:
        for a, b in zip(bombs, bombs[1:]):
            if b - a > 12:
                f.append({
                    "code": "BOMBS_IMPLAUSIBLE_JUMP",
                    "detail": f"bombs jumped {a}->{b} between telemetry "
                              f"rows; grenades only decrement — anchor "
                              f"likely re-latched to a different field"})
                break

    # --- camera/progress honesty --------------------------------------------
    cam = report.get("camera") or {}
    if cam and not cam.get("verified"):
        # allowed, but the report must not claim progress from it
        prog = play.get("progress_claim") or play.get("distance_pct")
        if prog:
            f.append({
                "code": "PROGRESS_FROM_UNVERIFIED_SIGNAL",
                "detail": f"camera signal verified=false yet report "
                          f"claims progress={prog}"})

    # --- cleared honesty ------------------------------------------------------
    if play.get("cleared") or report.get("mission_clear"):
        mc = report.get("mission_clear") or {}
        verified = mc.get("verified", play.get("cleared"))
        if not mc.get("corroboration") and verified:
            f.append({
                "code": "CLEAR_NOT_VERIFIED",
                "detail": "mission clear claimed without independent "
                          "corroboration"})
    # NaN / Infinity hygiene
    def _scan(o, path="report"):
        if isinstance(o, float) and not math.isfinite(o):
            f.append({"code": "NON_FINITE_NUMBER",
                      "detail": f"{path} contains {o}"})
        elif isinstance(o, dict):
            for k, v in o.items():
                _scan(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _scan(v, f"{path}[{i}]")
    _scan(report)
    return f


def assert_consistent(report):
    """Raise ValueError listing all findings (used before writing)."""
    findings = validate_report(report)
    if findings:
        raise ValueError("report self-consistency failed: " +
                         "; ".join(f"[{x['code']}] {x['detail']}"
                                   for x in findings))
    return True

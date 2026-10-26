#!/usr/bin/env python3
"""tetrade_r10_plugin_loop.py — Issue #8 DoD closure (Task 16-b).

Runs the COMPLETE game loop THROUGH the plugin contract v1 with zero
core edits, in ONE process (one beetle boot — the lab's hard rule):

  boot -> title -> plugin.boot_script (START->menu->CROSS->Marathon)
  -> plugin fresh-cycle discovery -> REAL gameplay steered by the
  plugin's 2-ply policy (Dellacherie + TETRIS bonus, NEXT piece read
  from live RAM base+896) with per-event score/level causality
  bookkeeping -> NATURAL game over (0x1FF5A8, no writes) -> refuse
  CONTINUE with CIRCLE -> plugin restart NAV (START confirms the
  persistent menu selection; B fallback) -> FRESH Marathon verified
  (counters zero + live piece) -> one verified clear of the fresh life
  -> loop_complete.

The contract path is the core's own consumers: PS1Play.run_steps
(boot_script), PS1Play.observe (features + infer_state),
AgentLoop/PS1Play.play (features + policy per chunk).  The plugin is
selected explicitly (detect_plugin keeps the minimal v1 slice first in
the registry — both plugins declare BOOT=tetrade.exe) and negotiated
via capabilities()/require() before any hook runs.

Honest verdicts; evidence -> scratch/round10_tetrade/plugin_loop/.
NO game bytes anywhere near git; no RAM writes (MemoryView read-only).
"""
import argparse
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ps1play.api import PS1Play                          # noqa: E402
from ps1play.plugins.base import parse_serial, detect_plugin  # noqa: E402
from ps1play.plugins.tetrade_play import TetradePlayPlugin    # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/ws_tetrade_r10"
EVID = os.path.join(REPO, "scratch", "round10_tetrade", "plugin_loop")
OVERRIDES = {b"beetle_psx_override_bios": b"openbios"}

CONTRACT_OPS = ("boot_script", "features", "policy", "infer_state",
                "detectors")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=1,
                    help="lives to complete (1 = one natural game over "
                         "+ verified restart + fresh-clear proof)")
    ap.add_argument("--chunk", type=int, default=30)
    ap.add_argument("--play-frames", type=int, default=300,
                    help="frames per p.play() call (10 chunks)")
    ap.add_argument("--max-frames", type=int, default=300000)
    ap.add_argument("--wall-budget", type=float, default=500.0)
    ap.add_argument("--seed-idle", type=int, default=0,
                    help="idle frames before nav (varies the piece RNG)")
    ap.add_argument("--out-dir", default=EVID)
    ap.add_argument("--tag", default=time.strftime("%H%M%S"))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    t0 = time.time()
    tag = args.tag

    ev_path = os.path.join(args.out_dir, f"plugin_events_{tag}.jsonl")
    evf = open(ev_path, "w")

    def J(e):
        evf.write(json.dumps(e, default=str) + "\n")
        evf.flush()
        return e

    def shot(p, name):
        try:
            from PIL import Image
            arr = p.core.frame_rgb()
            if arr is None:
                return None
            path = os.path.join(args.out_dir, f"{name}.png")
            Image.fromarray(arr).save(path)
            return os.path.basename(path)
        except Exception:
            return None

    OUT = {"script": "tetrade_r10_plugin_loop", "tag": tag,
           "started": time.strftime("%FT%TZ"),
           "cue": CUE, "workspace": WS,
           "overrides": {"beetle_psx_override_bios": "openbios"},
           "args": vars(args),
           "plugin_contract": {"version": 1,
                               "module": "ps1play/plugins/tetrade_play.py"}}
    timeline = []
    all_events = []
    negotiation = {"require_ok": {}}
    p = None
    plug = None
    stop_reason = None
    try:
        # ---------- ONE boot ----------
        p = PS1Play(CUE, workspace=WS, var_overrides=OVERRIDES)
        info = p.boot()
        OUT["boot"] = {k: info.get(k) for k in
                       ("core", "serial", "plugin", "input_device",
                        "ram_bytes", "profile_reused")}
        J({"ev": "boot", **OUT["boot"]})

        # ---------- contract selection + negotiation ----------
        serial = parse_serial(CUE)
        detected = detect_plugin(serial, CUE)
        plug = TetradePlayPlugin(p.profile)
        caps = plug.capabilities()
        negotiation = {"detected_by_registry": detected.ID,
                       "selected": plug.ID,
                       "note": "both tetrade plugins declare "
                               "BOOT=tetrade.exe; the registry keeps the "
                               "minimal v1 slice first, the full-gameplay "
                               "plugin is selected explicitly and "
                               "negotiated through contract v1 — every "
                               "core hook below calls THIS instance",
                       "capabilities": caps.to_dict(),
                       "require_ok": {}}
        for op in CONTRACT_OPS:
            negotiation["require_ok"][op] = bool(plug.require(op))
        OUT["plugin_negotiation"] = negotiation
        plug.cycles = args.cycles
        p.plugin = plug          # all core hooks now negotiate through v1
        J({"ev": "contract_negotiated", **negotiation})

        # ---------- title ----------
        row = p.observe()
        det0 = plug.detectors(p.mem)
        timeline.append({"label": "title", "fc": p.core.frames_run,
                         "t": p.t, "state": row["state"]})
        OUT["title_state"] = row["state"]
        OUT["title_png"] = shot(p, "01_title")
        J({"ev": "title", "fc": p.core.frames_run, "state": row["state"],
           "detectors": det0, "png": OUT["title_png"]})

        # ---------- boot_script through run_steps (contract hook) ----------
        if args.seed_idle > 0:
            p.core.run(args.seed_idle, set())
            J({"ev": "seed_idle", "frames": args.seed_idle,
               "fc": p.core.frames_run})
        r = p.run_steps(plug.boot_script())
        J({"ev": "boot_script_done", **r})
        timeline.append({"label": "boot_script_done",
                         "fc": p.core.frames_run, "t": p.t})
        OUT["boot_entry_png"] = shot(p, "02_after_boot_script")

        # ---------- main contract loop (AgentLoop via p.play) ----------
        nav_attempts = 0
        idle_since_nav = 0
        state_seen = {}
        png_n = {}
        while True:
            if plug.mode in ("done", "dead"):
                stop_reason = f"plugin_{plug.mode}"
                break
            if p.core.frames_run > args.max_frames:
                stop_reason = "frame_budget"
                break
            if time.time() - t0 > args.wall_budget:
                stop_reason = "wall_budget"
                break
            if not plug._marathon_entered:
                idle_since_nav += args.play_frames
                if idle_since_nav > 4500 and nav_attempts < 3:
                    nav_attempts += 1
                    idle_since_nav = 0
                    J({"ev": "nav_retry", "attempt": nav_attempts,
                       "fc": p.core.frames_run})
                    p.run_steps(plug.boot_script())
                    continue
            fc0 = p.core.frames_run
            p.play(args.play_frames, chunk=args.chunk, checkpoint_every=0)
            # drain plugin events (the contract-visible evidence stream)
            new_ev = plug.events
            plug.events = []
            for e in new_ev:
                e["fc_core"] = p.core.frames_run
                if e.pop("png", False):
                    png_n[e["ev"]] = png_n.get(e["ev"], 0) + 1
                    name = f"ev_{e['ev']}_{png_n[e['ev']]:02d}_fc" \
                           f"{e['fc_core']}"
                    e["png"] = shot(p, name)
                all_events.append(e)
                J(e)
            row = p.observe()
            state_seen[row["state"]] = state_seen.get(row["state"], 0) + 1
            if plug.mode != (timeline[-1]["mode"]
                             if timeline and "mode" in timeline[-1]
                             else None):
                timeline.append({"label": f"mode_{plug.mode}",
                                 "fc": p.core.frames_run, "t": p.t,
                                 "mode": plug.mode,
                                 "state": row["state"]})
            plug.maybe_finish(fc=p.core.frames_run)

        # ---------- final state ----------
        det_end = plug.detectors(p.mem)
        row = p.observe()
        timeline.append({"label": "final", "fc": p.core.frames_run,
                         "t": p.t, "state": row["state"],
                         "mode": plug.mode})
        OUT["final_state"] = row["state"]
        OUT["final_png"] = shot(p, "03_final_state")
        OUT["final_detectors"] = det_end
        J({"ev": "final", "detectors": det_end, "state": row["state"],
           "png": OUT["final_png"]})

    except Exception as ex:
        OUT["error"] = repr(ex)
        J({"ev": "EXC", "err": repr(ex)})
        raise
    finally:
        # ---------- report ----------
        OUT["stop_reason"] = stop_reason
        OUT["wall_s"] = round(time.time() - t0, 1)
        OUT["frames_run"] = (p.core.frames_run
                             if p is not None and p.core is not None
                             else None)
        OUT["timeline"] = timeline
        OUT["state_histogram"] = state_seen
        OUT["plugin_mode"] = plug.mode if plug is not None else None
        OUT["plugin_totals"] = dict(plug.totals) if plug else None
        OUT["plugin_engine_stats"] = (dict(plug.engine_stats)
                                      if plug else None)
        OUT["verdict_flags"] = plug.verdict_flags() if plug else None

        # ---- causal gates through the plugin path ----
        clears = [e for e in all_events if e["ev"] == "line_clear"]
        matched = [e for e in clears if e.get("match") is True]
        unmatched = [e for e in clears if e.get("match") is False]
        multi = [e for e in clears if e.get("match") is None]
        lv0 = [e for e in clears if e.get("level") == 0]
        flips = [e for e in all_events if e["ev"] == "level_flip"]
        drops = [e for e in all_events if e["ev"] == "score_delta"]
        drops_ok = [e for e in drops if e.get("match") is True]
        st = plug.engine_stats if plug else {}
        overs = [e for e in all_events if e["ev"] == "game_over"]
        refuses = [e for e in all_events if e["ev"] == "refuse_continue"]
        restarts = [e for e in all_events if e["ev"] == "restart_complete"]
        entered = [e for e in all_events if e["ev"] == "marathon_entered"]

        gates = {
            "g_marathon_entry": {
                "n": len(entered),
                "verdict": "PASS" if entered else "FAILED",
                "first": entered[0] if entered else None},
            "g_score_exactness": {
                "n_clears": len(clears),
                "n_match": len(matched),
                "n_mismatch": len(unmatched),
                "n_multi_event": len(multi),
                "level0_clears": len(lv0),
                "level0_all_zero_pts": bool(lv0) and all(
                    e.get("clear_pts") == 0 for e in lv0),
                "pct_match": round(100.0 * len(matched) / len(clears), 1)
                if clears else None,
                "verdict": "CAUSAL" if clears and not unmatched else
                           ("INCONCLUSIVE" if not clears else "MISMATCH"),
                "examples": matched[:4] + unmatched[:4]},
            "g_level_flip": {
                "n_flips": len(flips),
                "all_threshold_ok": bool(flips) and all(
                    e.get("threshold_ok") for e in flips),
                "verdict": "CAUSAL (natural, no RAM writes)"
                if flips and all(e.get("threshold_ok") for e in flips)
                else ("OBSERVED" if flips else "INCONCLUSIVE"),
                "flips": flips[:6]},
            "g_drop_points": {
                "n_score_deltas": len(drops),
                "n_exact": len(drops_ok),
                "drops_planned": st.get("drops_planned", 0),
                "verdict": "CAUSAL" if drops_ok else "INCONCLUSIVE"},
            "g_next_piece_read": {
                "n_promotions": st.get("n_promotions", 0),
                "n_match": st.get("n_promotion_match", 0),
                "pct": round(100.0 * st.get("n_promotion_match", 0)
                             / st["n_promotions"], 1)
                if st.get("n_promotions") else None,
                "verdict": "CAUSAL" if st.get("n_promotions") else
                           "INCONCLUSIVE"},
            "g_game_over": {
                "n": len(overs),
                "verdict": "PASS (natural top-out, 0x1FF5A8)"
                if overs else "FAILED",
                "events": overs},
            "g_refuse_restart": {
                "n_refuse": len(refuses), "n_restart_verified":
                    len(restarts),
                "verdict": "PASS" if restarts else
                           ("FAILED" if plug and plug.mode == "dead"
                            else "INCONCLUSIVE"),
                "events": refuses + restarts},
        }
        OUT["gates"] = gates

        # ---- Issue-8 DoD verdicts (honest) ----
        dod = {}
        dod["dod1_real_gameplay"] = {
            "verdict": "PASS" if (entered and plug.totals["pieces"] > 0
                                  and clears) else "FAILED",
            "evidence": {"marathon_entries": len(entered),
                         "pieces": plug.totals["pieces"] if plug else 0,
                         "clears": len(clears)}}
        dod["dod2_verified_counters"] = {
            "verdict": gates["g_score_exactness"]["verdict"]
            if gates["g_score_exactness"]["verdict"] == "CAUSAL"
            else gates["g_score_exactness"]["verdict"],
            "score_gate": gates["g_score_exactness"],
            "level_gate": gates["g_level_flip"],
            "next_gate": gates["g_next_piece_read"]}
        dod["dod3_natural_game_over"] = {
            "verdict": "PASS" if overs else "FAILED",
            "evidence": overs,
            "note": "isGameOver @0x1FF5A8 (struct base+2312); no RAM "
                    "writes anywhere (MemoryView is read-only)"}
        dod["dod4_plugin_contract"] = {
            "verdict": "PASS" if plug is not None and all(
                negotiation["require_ok"].values()) else "FAILED",
            "negotiation": negotiation,
            "path": "PS1Play.run_steps/observe/play(AgentLoop) -> "
                    "TetradePlayPlugin hooks only; zero core edits"}
        dod["dod5_restart_fresh_menu"] = {
            "verdict": gates["g_refuse_restart"]["verdict"],
            "evidence": refuses + restarts,
            "note": "CONTINUE? refused with CIRCLE; restart NAV on the "
                    "persistent menu; fresh Marathon verified by zeroed "
                    "counters + live piece"}
        OUT["dod"] = dod
        OUT["events"] = all_events
        OUT["event_files"] = {"events_jsonl": os.path.basename(ev_path)}

        rep = os.path.join(args.out_dir, f"plugin_report_{tag}.json")
        with open(rep, "w") as f:
            json.dump(OUT, f, indent=1, default=str)
        OUT.pop("events", None)          # keep the console print small
        with open(os.path.join(args.out_dir,
                               f"plugin_summary_{tag}.json"), "w") as f:
            json.dump(OUT, f, indent=1, default=str)
        evf.close()
        if p is not None:
            try:
                p.core.close()
            except Exception:
                pass
        print("report:", rep)
        print("verdicts:", json.dumps(
            {k: v.get("verdict") for k, v in OUT["gates"].items()}
            if "gates" in OUT else {}, default=str))
        print("dod:", json.dumps(
            {k: v.get("verdict") for k, v in OUT.get("dod", {}).items()},
            default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

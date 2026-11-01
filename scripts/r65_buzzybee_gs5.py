#!/usr/bin/env python3
"""r65_buzzybee_gs5.py — characterize the undocumented gs=5 state.

The acceptance run found: score reaches exactly 1000 and gameState
transitions 1 -> 5 (the capsule's 'score cap 1000 residual' UNKNOWN).
This probe plays to the transition, then keeps stepping and records
score / gs / hp / wasp x,y / bee y for 900 more frames — defining
whether play continues in gs=5 (score climbs, wasp attacks) or the
game is inert.  Read-only; legal input only.
"""
import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.runtime.config import RuntimeConfig          # noqa: E402
from ps1play.runtime.telemetry import TelemetryLog        # noqa: E402
from ps1play.runtime.registry import (                    # noqa: E402
    adapter_for_game, policy_for_game)
from ps1play.runtime.controller import SafetyController   # noqa: E402
from ps1play.runtime.session import EnvSession, preflight, resolve_iso

OUT = "/home/z/my-project/ps1ai/data/r65"


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = RuntimeConfig(game="buzzybee", episodes=1, seed_k=6,
                        max_frames_per_episode=4000,
                        max_runtime_s=900.0,
                        output_dir="/tmp/r65_bgs5")
    cfg.validated()
    tel = TelemetryLog(os.path.join(cfg.output_dir, "events.jsonl"),
                       run_meta={"cmd": "r65_buzzybee_gs5"}, echo=False)
    assets = preflight(cfg, iso_path=resolve_iso(cfg),
                       require_model=False)
    session = EnvSession.boot_new(cfg, deadline_s=cfg.boot_timeout_s,
                                  telemetry=tel)
    adapter = adapter_for_game("buzzybee", session.env, telemetry=tel)
    policy = policy_for_game(cfg, telemetry=tel)
    controller = SafetyController(adapter, session, telemetry=tel)
    adapter.wait_ready(cfg.ready_timeout_s)
    adapter.start_episode(6)
    src = session.frames()
    policy.reset()
    frame = src.latest(require_fresh=False)
    rows = []
    hit5_frame = None
    for step in range(4000):
        obs = adapter.observe(frame)
        if not obs.valid:
            break
        dec = policy.predict(obs)
        adapter.note_action(dec, obs)
        controller.apply(dec, frame)
        nf = src.latest(require_fresh=True)
        post = adapter.post_advance(nf)
        v = obs.values
        if post["gs"] == 5 and hit5_frame is None:
            hit5_frame = step
        if hit5_frame is not None and (step % 15 == 0 or
                                       step - hit5_frame < 60):
            rows.append({"step": int(step), "since5":
                         int(step - hit5_frame),
                         "gs": post["gs"], "hp": post["hp"],
                         "score": post["score"],
                         "ex": float(v[2]), "ey": float(v[3]),
                         "evy": float(v[4]), "by": float(v[0]),
                         "mode": dec.diagnostics.get("mode")})
        if post["terminal"] and post["gs"] not in (1, 5):
            rows.append({"step": int(step), "gs": post["gs"],
                         "hp": post["hp"], "score": post["score"],
                         "terminal": True})
            break
        if hit5_frame is not None and step - hit5_frame > 900:
            break
        frame = nf
    out = {"tag": "r65_buzzybee_gs5", "hit5_frame": hit5_frame,
           "rows": rows}
    json.dump(out, open(os.path.join(OUT, "r65_buzzybee_gs5.json"),
                        "w"), indent=1)
    s5 = [r for r in rows if r.get("since5", 0) >= 0]
    print(f"gs=5 entered at step {hit5_frame}")
    for r in rows[:6] + rows[-6:]:
        print("  ", {k: r.get(k) for k in
                     ("step", "since5", "gs", "hp", "score", "ex",
                      "mode")})
    # summary verdict
    scores = {r["score"] for r in rows}
    exs = [r.get("ex") for r in rows if "ex" in r]
    print("score range in window:", min(scores), "-", max(scores),
          "| wasp x range:", min(exs) if exs else None,
          "-", max(exs) if exs else None)
    session.close()
    tel.close()


if __name__ == "__main__":
    main()

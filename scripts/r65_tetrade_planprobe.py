#!/usr/bin/env python3
"""r65_tetrade_planprobe.py — plan-vs-realized placement probe.

Runs one episode with the product policy and, at every new piece,
records (a) the plan the policy was executing (target rot/x), (b) the
REALIZED landing state (the struct's type/x/rot/y at the moment the
NEXT piece spawns, i.e. where the previous piece actually ended), and
(c) the column delta plan-vs-realized.  Read-only diagnosis.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.runtime.config import RuntimeConfig          # noqa: E402
from ps1play.runtime.telemetry import TelemetryLog        # noqa: E402
from ps1play.runtime.registry import policy_for_game      # noqa: E402
from ps1play.runtime.controller import SafetyController   # noqa: E402
from ps1play.runtime.session import (EnvSession, preflight,  # noqa: E402
                                     resolve_iso)
from ps1play.adapters.tetrade.adapter import (TetradeAdapter,  # noqa: E402
                                              O_TYPE, O_X, O_Y, O_ROT)

OUT = "/home/z/my-project/ps1ai/data/r65"


class ProbeAdapter(TetradeAdapter):
    def __init__(self, env, telemetry=None):
        super().__init__(env, telemetry=telemetry)
        self.rows = []
        self._last_type = -1
        self._pending = None   # plan awaiting realization

    def _struct(self):
        a = self._snapshot().view("<i4")
        b = self._base // 4
        return {"type": int(a[(b + O_TYPE) // 4]),
                "x": int(a[(b + O_X) // 4]),
                "y": int(a[(b + O_Y) // 4]),
                "rot": int(a[(b + O_ROT) // 4])}

    def observe(self, frame):
        obs = super().observe(frame)
        if not obs.valid:
            return obs
        v = obs.values
        t = int(v[200:207].argmax()) + 1 if v[200:207].sum() else 0
        if t and t != self._last_type:
            self._last_type = t
            st = self._struct()
            if self._pending is not None:
                p = self._pending
                self.rows.append({
                    "spawn_type": t,
                    "plan": {"piece": p["piece"], "rot": p["rot"],
                             "x": p["x"], "moves": p["moves"],
                             "rots": p["rots"], "fused": p["fused"],
                             "phase": p["phase"]},
                    "realized": {"type": st["type"], "x": st["x"],
                                 "rot": st["rot"], "y": st["y"]},
                    "dx": st["x"] - p["x"], "drot": st["rot"] - p["rot"],
                })
            self._pending = {"piece": len(self.rows), "piece_type": t,
                             "rot": None, "x": None, "moves": 0,
                             "rots": 0, "fused": False, "phase": "?"}
            self._cur = self._pending
        return obs

    def note_action(self, decision, observation):
        super().note_action(decision, observation)
        if self._cur is None:
            return
        plan = getattr(self, "_plan", None)
        if plan:
            self._cur["rot"] = plan.get("rot")
            self._cur["x"] = plan.get("x")
            self._cur["phase"] = str(plan.get("phase"))
        self._cur["moves"] = self._moves_this_plan
        self._cur["rots"] = self._rots_this_plan
        self._cur["fused"] = bool(self._fuse_hit)


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = RuntimeConfig(game="tetrade", episodes=1, seed_k=343,
                        max_frames_per_episode=10000,
                        max_runtime_s=600.0,
                        output_dir="/tmp/r65_tplan")
    cfg.validated()
    tel = TelemetryLog(os.path.join(cfg.output_dir, "events.jsonl"),
                       run_meta={"cmd": "r65_tplan"}, echo=False)
    assets = preflight(cfg, iso_path=resolve_iso(cfg),
                       require_model=False)
    session = EnvSession.boot_new(cfg, deadline_s=cfg.boot_timeout_s,
                                  telemetry=tel)
    adapter = ProbeAdapter(session.env, telemetry=tel)
    policy = policy_for_game(cfg, telemetry=tel)
    controller = SafetyController(adapter, session, telemetry=tel)
    adapter.wait_ready(cfg.ready_timeout_s)
    adapter.start_episode(343)
    src = session.frames()
    policy.reset()
    frame = src.latest(require_fresh=False)
    result = "alive"
    for step in range(cfg.max_frames_per_episode):
        obs = adapter.observe(frame)
        if not obs.valid:
            result = "error"
            break
        dec = policy.predict(obs)
        adapter.note_action(dec, obs)
        controller.apply(dec, frame)
        nf = src.latest(require_fresh=True)
        post = adapter.post_advance(nf)
        if post.get("terminal"):
            result = "death"
            break
        frame = nf
    out = {"tag": "r65_tetrade_planprobe", "result": result,
           "pieces": len(adapter.rows), "rows": adapter.rows}
    json.dump(out, open(os.path.join(OUT,
                                     "r65_tetrade_planprobe.json"),
                        "w"), indent=1)
    print("result:", result, "pieces:", len(adapter.rows))
    bad_dx = sum(1 for r in adapter.rows if r["dx"] != 0)
    bad_rot = sum(1 for r in adapter.rows if r["drot"] % 4 != 0)
    print(f"placements with dx!=0: {bad_dx}/{len(adapter.rows)}  "
          f"drot!=0: {bad_rot}/{len(adapter.rows)}")
    for r in adapter.rows[:14]:
        p, rl = r["plan"], r["realized"]
        print(" piece%2d plan(rot=%s x=%s ph=%s mv=%s rt=%s fz=%s) "
              "-> real(t=%d rot=%d x=%d y=%d) dx=%d drot=%d"
              % (r["spawn_type"] if False else 0,
                 p["rot"], p["x"], p["phase"], p["moves"], p["rots"],
                 p["fused"], rl["type"], rl["rot"], rl["x"], rl["y"],
                 r["dx"], r["drot"]))
    session.close()
    tel.close()


if __name__ == "__main__":
    main()

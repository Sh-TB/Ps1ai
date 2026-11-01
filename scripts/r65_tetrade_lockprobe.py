#!/usr/bin/env python3
"""r65_tetrade_lockprobe.py — the DECISIVE placement-correctness probe.

At the frame where the policy chooses HARD_DROP, record the live board,
piece type and the plan's (r_t, x_t) + predicted landing cells.  At the
next piece spawn, diff the locked board against the pre-drop board to
recover the ACTUAL locked cells (after removing full rows the game
cleared).  Compare predicted vs actual: cells-matched, column offsets,
and where the mismatches sit.  Read-only.
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
from ps1play.adapters.tetrade import policy as P          # noqa: E402

OUT = "/home/z/my-project/ps1ai/data/r65"


class LockProbe(TetradeAdapter):
    def __init__(self, env, telemetry=None):
        super().__init__(env, telemetry=telemetry)
        self.events = []
        self._last_type = -1
        self._predrop = None
        self._lockcap = None   # frames to wait, then snapshot the struct

    def _struct(self):
        a = self._snapshot().view("<i4")
        b = self._base // 4
        return {"type": int(a[(b + O_TYPE) // 4]),
                "x": int(a[(b + O_X) // 4]),
                "y": int(a[(b + O_Y) // 4]),
                "rot": int(a[(b + O_ROT) // 4])}

    def note_action(self, decision, observation):
        super().note_action(decision, observation)
        if decision.action != "HARD_DROP" or self._predrop is not None:
            return
        self._lockcap = 2   # snapshot the struct 2 frames after the drop
        st = self._read_state()
        pol = self.policy_ref
        plan = getattr(pol, "_plan", None) or {}
        self._predrop = {
            "board": (st["board"] > 0).astype(int).copy(),
            "ptype": int(st["type"]), "px": int(st["x"]),
            "prot": int(st["rot"]), "py": int(st["y"]),
            "plan": {"r_t": plan.get("r_t"), "x_t": plan.get("x_t"),
                     "forced": plan.get("forced"),
                     "frames": plan.get("frames")},
        }
        # predicted landing cells for the planned placement
        r_t, x_t = plan.get("r_t"), plan.get("x_t")
        if r_t is not None and 1 <= self._predrop["ptype"] <= 7:
            shape = P.rot_shape(self._predrop["ptype"], int(r_t) % 4)
            y = P.drop_y(self._predrop["board"], shape, int(x_t))
            self._predrop["pred_y"] = int(y)
            self._predrop["pred_cells"] = sorted(
                [int(y + dr), int(x_t + dc)]
                for dr, dc in P.cells(shape)) if y is not None and y >= 0 \
                else None

    def observe(self, frame):
        obs = super().observe(frame)
        if not obs.valid:
            return obs
        if self._lockcap is not None:
            self._lockcap -= 1
            if self._lockcap <= 0 and self._predrop is not None:
                self._predrop["at_lock"] = self._struct()
                self._lockcap = None
        v = obs.values
        t = int(v[200:207].argmax()) + 1 if v[200:207].sum() else 0
        if t and t != self._last_type and self._predrop is not None:
            self._last_type = t
            st = self._read_state()
            after = (st["board"] > 0).astype(int)
            before = self._predrop["board"]
            added = after & ~before
            # undo full rows (a clear removes rows from the whole board;
            # only compare when no clear happened — the clean signal)
            nfull = int((after.all(axis=1)).sum())
            ev = {"predrop": {k: v2 for k, v2 in self._predrop.items()
                              if k != "board"},
                  "added_cells": sorted([int(r), int(c)]
                                        for r, c in zip(*added.nonzero()))
                  if added.any() else [],
                  "full_rows_at_lock": nfull,
                  "pre_max_height": int(max((before.any(axis=1)
                                             .nonzero()[0].tolist()
                                             + [20]))
                                         if before.any() else 0)}
            pc = ev["predrop"].get("pred_cells")
            if pc and not nfull:
                ev["pred_cells"] = pc
                got = set(map(tuple, ev["added_cells"]))
                pred = set(map(tuple, pc))
                ev["matched"] = len(got & pred)
                ev["pred_n"] = len(pred)
                ev["got_n"] = len(got)
                ev["missing"] = sorted(pred - got)
                ev["extra"] = sorted(got - pred)
            self.events.append(ev)
            self._predrop = None
        if t != self._last_type:
            self._last_type = t
        return obs


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = RuntimeConfig(game="tetrade", episodes=1, seed_k=343,
                        max_frames_per_episode=10000,
                        max_runtime_s=600.0,
                        output_dir="/tmp/r65_tlock")
    cfg.validated()
    tel = TelemetryLog(os.path.join(cfg.output_dir, "events.jsonl"),
                       run_meta={"cmd": "r65_tlock"}, echo=False)
    assets = preflight(cfg, iso_path=resolve_iso(cfg),
                       require_model=False)
    session = EnvSession.boot_new(cfg, deadline_s=cfg.boot_timeout_s,
                                  telemetry=tel)
    adapter = LockProbe(session.env, telemetry=tel)
    policy = policy_for_game(cfg, telemetry=tel)
    adapter.policy_ref = policy
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
    clean = [e for e in adapter.events
             if "matched" in e and e["full_rows_at_lock"] == 0]
    fullm = sum(e["matched"] for e in clean)
    fullp = sum(e["pred_n"] for e in clean)
    perfect = sum(1 for e in clean
                  if e["matched"] == e["pred_n"] == e["got_n"])
    dxs = []
    for e in clean:
        if e["extra"] and e["missing"]:
            dxs += [c2 - c1 for (_r1, c1) in e["missing"]
                    for (_r2, c2) in e["extra"]]
    from collections import Counter
    json.dump({"tag": "r65_tetrade_lockprobe", "result": result,
               "drops_recorded": len(adapter.events),
               "clean_comparisons": len(clean),
               "perfect_placements": perfect,
               "cell_match_rate": round(fullm / max(1, fullp), 3),
               "delta_col_histogram": dict(Counter(dxs)),
               "events": adapter.events},
              open(os.path.join(OUT, "r65_tetrade_lockprobe.json"),
                   "w"), indent=1)
    print(f"result={result} drops={len(adapter.events)} "
          f"clean={len(clean)} perfect={perfect} "
          f"cell_match={fullm}/{fullp}={fullm/max(1,fullp):.3f}")
    print("delta-col histogram (actual - predicted):",
          dict(Counter(dxs)))
    session.close()
    tel.close()


if __name__ == "__main__":
    main()

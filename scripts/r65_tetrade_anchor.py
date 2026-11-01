#!/usr/bin/env python3
"""r65_tetrade_anchor.py — measure the game's TRUE piece-column anchor.

For every (piece type, rotation) the game offers, steer a piece to a
known struct x (mid-board), hard-drop it, and read the columns of the
newly locked cells.  The measured leftmost column per (t, r, x) is the
ground truth the policy's cell model must match.  Legal inputs only
(ROT_CW / MOVE_L / MOVE_R / HARD_DROP), read-only RAM, zero writes.
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.runtime.config import RuntimeConfig          # noqa: E402
from ps1play.runtime.telemetry import TelemetryLog        # noqa: E402
from ps1play.runtime.registry import policy_for_game      # noqa: E402
from ps1play.runtime.controller import SafetyController   # noqa: E402
from ps1play.runtime.session import (EnvSession, preflight,  # noqa: E402
                                     resolve_iso)
from ps1play.adapters.tetrade.adapter import TetradeAdapter  # noqa: E402
from ps1play.adapters.tetrade import policy as P          # noqa: E402

OUT = "/home/z/my-project/ps1ai/data/r65"
TARGET_XS = [3, 5, 1, 6, 2, 4, 7]   # cycle: keep the stack flat
MAX_FRAMES = 12000


def norm_cells(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    r0, c0 = min(rs), min(cs)
    return sorted((r - r0, c - c0) for r, c in cells), c0


class AnchorProbe(TetradeAdapter):
    def __init__(self, env, telemetry=None):
        super().__init__(env, telemetry=telemetry)
        self.measure = {}       # (t, r) -> list of (x_drop, leftmost_col)
        self.events = []
        self._last_type = -1
        self._plan_combo = None
        self._predrop = None
        self.dbg = {"drops": 0, "spawns": 0, "dirty": 0}

    def _struct(self):
        a = self._snapshot().view("<i4")
        b = self._base          # BYTE offset (adapter convention)
        return {"type": int(a[(b + 800) // 4]),
                "x": int(a[(b + 868) // 4]),
                "y": int(a[(b + 872) // 4]),
                "rot": int(a[(b + 880) // 4])}

    def note_action(self, decision, observation):
        super().note_action(decision, observation)
        if decision.action != "HARD_DROP" or self._predrop is not None:
            return
        self.dbg["drops"] += 1
        st = self._struct()
        self._predrop = {"board": (st["board"] if False else
                                   self._board_now()),
                         "x": st["x"], "rot": st["rot"],
                         "type": st["type"]}

    def _board_now(self):
        a = self._snapshot().view("<i4")
        b4 = self._base // 4
        return (a[b4:b4 + 200].reshape(20, 10) > 0).astype(int).copy()

    def observe(self, frame):
        obs = super().observe(frame)
        if not obs.valid:
            return obs
        v = obs.values
        t = int(v[200:207].argmax()) + 1 if v[200:207].sum() else 0
        if t and t != self._last_type:
            self._last_type = t
            self.dbg["spawns"] += 1
            if self._predrop is not None:
                after = self._board_now()
                added = after & ~self._predrop["board"]
                nfull = int(after.all(axis=1).sum())
                cells = sorted([int(r), int(c)]
                               for r, c in zip(*added.nonzero()))
                if cells and nfull == 0:
                    _n, left = norm_cells(cells)
                    key = (self._predrop["type"], self._predrop["rot"])
                    self.measure.setdefault(key, []).append(
                        (self._predrop["x"], left, cells))
                else:
                    self.dbg["dirty"] += 1
                self._predrop = None
            # plan this piece's combo: prefer unmeasured rotations of
            # this type; the symmetric O rots 2/3 and I rots 2/3 are
            # LAST (their columns repeat rot 0/1 by shape symmetry)
            def _prio(rr, tt):
                if tt == 2 and rr >= 2:
                    return 2          # O: r2==r0, r3==r1 columns
                if tt == 1 and rr >= 2:
                    return 2          # I: r2==r0, r3==r1 columns
                return 0
            todo = sorted((rr for rr in range(4)
                           if (t, rr) not in self.measure),
                          key=lambda rr: _prio(rr, t))
            self._plan_combo = ((t, todo[0]) if todo else None)
            self._phase = "ROT" if self._plan_combo else "IDLE"
        return obs


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = RuntimeConfig(game="tetrade", episodes=1, seed_k=343,
                        max_frames_per_episode=MAX_FRAMES,
                        max_runtime_s=900.0,
                        output_dir="/tmp/r65_tanchor")
    cfg.validated()
    tel = TelemetryLog(os.path.join(cfg.output_dir, "events.jsonl"),
                       run_meta={"cmd": "r65_tanchor"}, echo=False)
    assets = preflight(cfg, iso_path=resolve_iso(cfg),
                       require_model=False)
    session = EnvSession.boot_new(cfg, deadline_s=cfg.boot_timeout_s,
                                  telemetry=tel)
    adapter = AnchorProbe(session.env, telemetry=tel)
    controller = SafetyController(adapter, session, telemetry=tel)
    adapter.wait_ready(cfg.ready_timeout_s)
    src = session.frames()
    frame = src.latest(require_fresh=False)
    result = "alive"
    cooldown = 0
    ep_no = 0
    seed_ladder = 343
    k = seed_ladder
    for step in range(MAX_FRAMES):
        obs = adapter.observe(frame)
        if not obs.valid:
            result = "error"
            break
        v = obs.values
        combo = adapter._plan_combo
        if combo is None and len(adapter.measure) >= 28:
            result = "measured_all"
            break
        if cooldown > 0:
            cooldown -= 1
            action = "IDLE"
        else:
            b = (v[:200].reshape(20, 10) > 0.5)
            hts = [20 - int(b[:, c].argmax()) if b[:, c].any()
                   else 0 for c in range(10)]
            st = adapter._struct()
            if max(hts) >= 12:
                # stack too high: hard-drop this piece flat and let the
                # game end; the restart flow gives a fresh board
                action = "HARD_DROP"
                cooldown = 15
            elif combo is None:
                action = "HARD_DROP"   # nothing to measure from this t
                cooldown = 15
            elif adapter._phase == "ROT":
                if st["rot"] != combo[1]:
                    action = "ROT_CW"
                    cooldown = 6
                else:
                    adapter._phase = "MOVE"
                    action = "IDLE"
            elif adapter._phase == "MOVE":
                # the lowest column NEAREST the piece (fewer taps,
                # flatter stack)
                x0 = st["x"]
                tx = min(range(10), key=lambda c: (hts[c], abs(c - x0)))
                if st["x"] != tx:
                    action = "MOVE_R" if st["x"] < tx else "MOVE_L"
                    cooldown = 11
                else:
                    adapter._phase = "DROP"
                    action = "IDLE"
            else:
                action = "HARD_DROP"
                cooldown = 15
        action = P.Policy.legal_actions(adapter) if False else action
        from ps1play.runtime.interfaces import ActionDecision  # noqa: E402
        dec = ActionDecision(action=action, logits=None,
                             frame_seq=frame.seq, policy_name="anchor",
                             policy_sha256="probe", latency_ms=0.0)
        adapter.note_action(dec, obs)
        controller.apply(dec, frame)
        nf = src.latest(require_fresh=True)
        post = adapter.post_advance(nf)
        if post.get("terminal"):
            # legal restart: refuse the continue, re-enter Marathon,
            # keep measuring (the R64-tested restart flow)
            ep_no += 1
            k = seed_ladder + ep_no * 6
            adapter.start_episode(k)
            frame = src.latest(require_fresh=False)
            cooldown = 30
            continue
        frame = nf
        if step % 300 == 0:
            st = adapter._struct() if adapter._base else {}
            print(f"  step={step} t={st.get('type')} rot={st.get('rot')} "
                  f"x={st.get('x')} phase={getattr(adapter,'_phase','?')} "
                  f"cool={cooldown} combo={adapter._plan_combo} "
                  f"dbg={adapter.dbg} measured={len(adapter.measure)}",
                  flush=True)
    # analysis: measured leftmost vs the policy model's prediction
    model = {}
    for (t, r), obs_list in sorted(adapter.measure.items()):
        shape = P.rot_shape(t, r)
        pc = P.cells(shape)
        pol_left_off = min(dc for _, dc in pc)
        for x, left, cells in obs_list:
            pred_left = x + pol_left_off
            model.setdefault((t, r), []).append(
                {"x": x, "left_actual": left, "left_pred": pred_left,
                 "delta": left - pred_left})
    deltas = defaultdict(list)
    for (t, r), rows in model.items():
        deltas[(t, r)] = sorted({row["delta"] for row in rows})
    out = {"tag": "r65_tetrade_anchor", "result": result,
           "combos_measured": len(adapter.measure),
           "measure": {f"{t},{r}": v for (t, r), v in
                       sorted(adapter.measure.items())},
           "model_check": {f"{t},{r}": v for (t, r), v in
                           sorted(model.items())},
           "delta_by_combo": {f"{t},{r}": d for (t, r), d in
                              sorted(deltas.items())}}
    json.dump(out, open(os.path.join(OUT, "r65_tetrade_anchor.json"),
                        "w"), indent=1)
    print(f"result={result} combos={len(adapter.measure)} "
          f"episodes={ep_no + 1} steps={step}")
    for (t, r), d in sorted(deltas.items()):
        n = len(adapter.measure[(t, r)])
        print(f"  t={t} r={r}: n={n} delta(actual-pred)={d}")
    session.close()
    tel.close()


if __name__ == "__main__":
    main()

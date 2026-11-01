#!/usr/bin/env python3
"""r65_tetrade_diag.py — WHY does the R64 Tetrade policy die at ~25
pieces/life?  Instrumented product-path diagnosis (Part F task 4).

Runs the EXACT engine decision loop (observe -> predict -> note_action
-> apply -> advance -> post_advance) with a DiagAdapter that decodes
the 222-vector at every NEW-piece frame and records board metrics:
holes, aggregate height, max height, bumpiness, row-9 pressure.  At
death it dumps the final board as ASCII.  Read-only: same legal inputs
as the product run; no memory writes; no policy change.
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.runtime.config import RuntimeConfig          # noqa: E402
from ps1play.runtime.telemetry import TelemetryLog        # noqa: E402
from ps1play.runtime.registry import (                    # noqa: E402
    adapter_for_game, policy_for_game)
from ps1play.runtime.controller import SafetyController   # noqa: E402
from ps1play.runtime.session import EnvSession, preflight, resolve_iso  # noqa: E402
from ps1play.adapters.tetrade.adapter import TetradeAdapter  # noqa: E402
from ps1play.adapters.tetrade import policy as P          # noqa: E402

OUT = "/home/z/my-project/ps1ai/data/r65"


def board_metrics(board):
    """board: (20,10) int 0/1, row 0 = top."""
    b = board > 0
    holes = 0
    for c in range(10):
        seen = False
        for r in range(20):
            if b[r, c]:
                seen = True
            elif seen:
                holes += 1
    heights = [0] * 10
    for c in range(10):
        for r in range(20):
            if b[r, c]:
                heights[c] = 20 - r
                break
    agg = sum(heights)
    mx = max(heights)
    bump = sum(abs(heights[i] - heights[i + 1]) for i in range(9))
    return {"holes": holes, "agg": agg, "max": mx, "bump": bump,
            "heights": heights}


def ascii_board(board):
    rows = []
    for r in range(20):
        rows.append("".join("#" if board[r, c] else "."
                            for c in range(10)))
    return rows


class DiagAdapter(TetradeAdapter):
    def __init__(self, env, telemetry=None):
        super().__init__(env, telemetry=telemetry)
        self.diag_rows = []
        self._last_type = -1
        self._piece_no = 0

    def observe(self, frame):
        obs = super().observe(frame)
        if obs.valid:
            v = obs.values
            t = int(v[200:207].argmax()) + 1 if v[200:207].sum() else 0
            if t != self._last_type:          # a NEW piece entered play
                self._piece_no += 1
                self._last_type = t
                m = board_metrics(v[0:200].reshape(20, 10).astype(int))
                self.diag_rows.append({
                    "piece": self._piece_no, "type": int(t),
                    "x": float(v[207 + 1]), "y": float(v[207 + 2]),
                    "rot": float(v[207]),
                    "score": float(v[217]), "lines": float(v[218]),
                    **m})
        return obs

    def final_board(self):
        """The live board straight from the struct (base + matrix@0)."""
        if self._base is None:
            return None
        try:
            a = self._snapshot().view("<i4")
            b4 = self._base // 4
            return a[b4:b4 + 200].reshape(20, 10).copy()
        except Exception:
            return None


def main():
    os.makedirs(OUT, exist_ok=True)
    for ep, k in enumerate((343, 350), start=1):
        cfg = RuntimeConfig(game="tetrade", episodes=1, seed_k=k,
                            max_frames_per_episode=10000,
                            max_runtime_s=600.0,
                            output_dir=f"/tmp/r65_tdiag_{ep}")
        cfg.validated()
        tel = TelemetryLog(os.path.join(cfg.output_dir, "events.jsonl"),
                           run_meta={"cmd": "r65_tetrade_diag"},
                           echo=False)
        assets = preflight(cfg, iso_path=resolve_iso(cfg),
                           require_model=False)
        session = EnvSession.boot_new(cfg, deadline_s=cfg.boot_timeout_s,
                                      telemetry=tel)
        adapter = DiagAdapter(session.env, telemetry=tel)
        policy = policy_for_game(cfg, telemetry=tel)
        controller = SafetyController(adapter, session, telemetry=tel)
        adapter.wait_ready(cfg.ready_timeout_s)
        adapter.start_episode(k)
        src = session.frames()
        policy.reset()
        frame = src.latest(require_fresh=False)
        result, steps = "alive", 0
        t0 = time.time()
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
            steps += 1
            if post.get("terminal"):
                result = "death"
                break
            frame = nf
        wall = time.time() - t0
        stats = adapter.episode_stats()
        rows = adapter.diag_rows
        fb = adapter.final_board()
        out = {
            "tag": "r65_tetrade_diag", "episode": ep, "seed_k": k,
            "result": result, "steps": steps, "wall_s": round(wall, 2),
            "lines": stats.get("pipes"), "pieces": len(rows),
            "per_piece": rows,
            "death_board": ascii_board(fb) if result == "death" else None,
        }
        path = os.path.join(OUT, f"r65_tetrade_diag_ep{ep}.json")
        json.dump(out, open(path, "w"), indent=1)
        m = rows[-1] if rows else {}
        print(f"ep{ep} k={k}: {result} steps={steps} "
              f"lines={stats.get('pipes')} pieces={len(rows)} "
              f"wall={wall:.0f}s | at death: holes={m.get('holes')} "
              f"agg={m.get('agg')} max={m.get('max')} "
              f"bump={m.get('bump')}")
        # first 6 rows: the stack profile from the very beginning
        for r in rows[:6]:
            print("   piece %2d t=%d holes=%d agg=%3d max=%2d bump=%2d"
                  % (r["piece"], r["type"], r["holes"], r["agg"],
                     r["max"], r["bump"]))
        session.close()
        tel.close()


if __name__ == "__main__":
    main()

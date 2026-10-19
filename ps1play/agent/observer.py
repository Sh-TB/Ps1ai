"""Observer — token-minimal game telemetry from RAM bytes.

An LLM agent reads the compact dict this module produces; it never sees
raw megabytes. Compares consecutive snapshots -> changed regions, digests,
counter guesses. All observe-only (no writes => no cheats).
"""
import numpy as np

from ..core.memory import diff_regions, digest


class Observer:
    def __init__(self, mem):
        self.mem = mem            # MemoryView over live RAM
        self.prev = None
        self.t_last = 0

    def observe(self, t=None, top=8):
        snap = self.mem.snapshot()
        d = diff_regions(self.prev, snap, top=top)
        row = {
            "t": t if t is not None else self.t_last,
            "digest": digest(snap),
            "changed_bytes": d["bytes_changed"],
        }
        if d["regions"]:
            row["top_regions"] = [
                {"addr": a, "len": b - a, "ch": c}
                for (a, b, c) in d["regions"][:top]
            ]
        self.prev = snap
        self.t_last = (t if t is not None else self.t_last + 1)
        return row

    def mark(self):
        """Remember current RAM as baseline (call before a perturbation)."""
        self.prev = self.mem.snapshot()

    def since_mark(self, t=None):
        snap = self.mem.snapshot()
        d = diff_regions(self.prev, snap)
        return {"t": t, "digest": digest(snap),
                "changed_bytes": d["bytes_changed"],
                "top_regions": [{"addr": a, "len": b - a, "ch": c}
                                for (a, b, c) in d["regions"]]}

"""ps1play.runtime.scoring — pipe passage counting (R62).

Vendored from scripts/r57_lib.PassageCounter (the R57–R61 scoring
semantics, byte-for-byte algorithm) so the runtime package is
self-contained; tests/test_r62_runtime.py asserts equivalence with the
original on randomized sequences, so the two cannot drift.
"""
from __future__ import annotations

from typing import List, Optional


class PassageCounter:
    """Visual passage detector: one event per pipe, strictly increasing.

    fire(bx) -> bool. bx = the tracked gap band center x (full-res
    vision). The band moves LEFT with the pipes; when the tracker JUMPS
    to the next pipe (bx > last + 60) exactly one passage has happened.
    Missing detections (None) are skipped.
    """

    def __init__(self) -> None:
        self.last: Optional[float] = None
        self.count = 0
        self.events: List[int] = []   # step indices of fired passages

    def fire(self, bx: Optional[float], step: int = 0) -> bool:
        ev = False
        if bx is not None:
            if self.last is not None and bx > self.last + 60:
                self.count += 1
                self.events.append(int(step))
                ev = True
            self.last = float(bx)
        return ev

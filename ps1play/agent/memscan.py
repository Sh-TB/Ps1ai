"""MemScan — a RetroArch/BizHawk-style cheat-finder, strictly READ-ONLY.

The classic GameShark/Cheat-Search workflow, rebuilt for our agent:
  1. scan():        every u8/u16/u32 word in RAM becomes a candidate
  2. narrow():      conditions between two moments (==, <, changed, inc...)
  3. results():     surviving addresses + live values

We use it to LOCATE counters (hp, ammo, lives) so the agent can READ them
like a GameShark code does — but we never write a byte (no cheating).
Zero tokens: pure numpy, no LLM involved.
"""
import numpy as np

# name -> (word size, numpy dtype)
DT = {"u8": (1, np.dtype("<u1")),
      "u16": (2, np.dtype("<u2")),
      "u32": (4, np.dtype("<u4"))}

# top of RAM: SPU/DMA audio buffers in many games -> never game counters
AUDIO_ZONE = 0x1FC000


class MemScan:
    """Candidate sets as boolean masks per dtype over the 2MB main RAM."""

    def __init__(self, mem, region=(0, AUDIO_ZONE)):
        self.mem = mem
        self.region = region
        self.masks = {}
        self.prev = None
        self.reset()

    # ------------------------------------------------------------------
    def _views(self, snap):
        lo, hi = self.region
        out = {}
        for name, (sz, dt) in DT.items():
            n = (hi - lo) // sz
            out[name] = snap[lo:lo + n * sz].view(dt)
        return out

    def reset(self):
        """Start over: every word of RAM is a candidate."""
        snap = self.mem.snapshot()
        self.prev = snap
        self.masks = {}
        for name, (sz, dt) in DT.items():
            v = self._views(snap)[name]
            # counters are smallish; drop obviously-junk high u32 words
            if name == "u32":
                self.masks[name] = v < 0x01000000
            else:
                self.masks[name] = np.ones(len(v), dtype=bool)
        return self.counts()

    def counts(self):
        return {k: int(v.sum()) for k, v in self.masks.items()}

    # ------------------------------------------------------------------
    def _apply(self, name, fn):
        if name not in self.masks:
            raise KeyError(name)
        cur = self._views(self.mem.snapshot())[name]
        keep = self.masks[name] & fn(cur)
        self.masks[name] = keep
        return int(keep.sum())

    def _cmp_prev(self, name, fn):
        cur = self._views(self.mem.snapshot())[name]
        prv = self._views(self.prev)[name]
        keep = self.masks[name] & fn(cur, prv)
        self.masks[name] = keep
        self.prev = self.mem.snapshot()
        return int(keep.sum())

    # ---- conditions on the CURRENT value ----
    def eq(self, name, val):
        return self._apply(name, lambda v: v == val)

    def ne(self, name, val):
        return self._apply(name, lambda v: v != val)

    def lt(self, name, val):
        return self._apply(name, lambda v: v < val)

    def le(self, name, val):
        return self._apply(name, lambda v: v <= val)

    def gt(self, name, val):
        return self._apply(name, lambda v: v > val)

    def ge(self, name, val):
        return self._apply(name, lambda v: v >= val)

    def between(self, name, lo, hi):
        return self._apply(name, lambda v: (v >= lo) & (v <= hi))

    # ---- conditions vs the PREVIOUS snapshot (call after playing N frames)
    def changed(self, name):
        return self._cmp_prev(name, lambda c, p: c != p)

    def unchanged(self, name):
        return self._cmp_prev(name, lambda c, p: c == p)

    def inc(self, name):
        return self._cmp_prev(name, lambda c, p: c > p)

    def dec(self, name):
        return self._cmp_prev(name, lambda c, p: c < p)

    def inc_by(self, name, d, tol=0):
        return self._cmp_prev(name, lambda c, p: np.abs((c - p) - d) <= tol)

    def dec_by(self, name, d, tol=0):
        return self._cmp_prev(name, lambda c, p: np.abs((p - c) - d) <= tol)

    # ------------------------------------------------------------------
    def results(self, name, top=24):
        """Surviving candidates with live values (addr is byte offset)."""
        sz = DT[name][0]
        cur = self._views(self.mem.snapshot())[name]
        idx = np.flatnonzero(self.masks[name])
        return [{"addr": int(i) * sz + self.region[0], "dtype": name,
                 "val": int(cur[i])} for i in idx[:top]]

    def addr_in(self, addr, name):
        """Is a specific address still a candidate (for validation)?"""
        sz = DT[name][0]
        i = (addr - self.region[0]) // sz
        if i < 0 or i >= len(self.masks[name]):
            return False
        return bool(self.masks[name][i])

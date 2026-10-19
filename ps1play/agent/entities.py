"""Entity-slot discovery — watch RAM while playing, find the game's
object arrays (enemies, bullets, items) WITHOUT any pixels or tokens.

How it works (all classic memory-analysis, done in numpy):
  * collect N snapshots during real gameplay
  * a WORD is a "live actor field" when:
      - it is non-zero most of the time (active slots)
      - it changes on a bounded fraction of frames (things move)
      - frame-to-frame deltas stay under a step limit (motion, not noise)
  * words that sit within a small stride of each other form BLOCKS;
    a block with several live fields = one entity slot table.

Typical outcome for Metal Slug X: blocks in the hit-anywhere zone
(0x085xxx) hold per-actor x/y/flags. The agent then reads "how many
enemies are near me" by counting active slots — zero tokens.
"""
import numpy as np


def _view(snap, lo, hi, dtype):
    sz = np.dtype(dtype).itemsize
    n = (hi - lo) // sz
    return snap[lo:lo + n * sz].view(dtype).astype(np.int64)


def collect(core, mem, frames=90, every=1):
    """Sample `frames` snapshots while the game runs idle (no input)."""
    snaps = []
    core.set_buttons(set())
    for i in range(frames):
        core.run_frame()
        if i % every == 0:
            snaps.append(mem.snapshot())
    return snaps


def find_live_fields(snaps, lo, hi, dtype="<u4", max_step=0x8000,
                     move_frac=(0.05, 1.0), nonzero_frac=0.25):
    """Return ranked live actor-field candidates inside [lo,hi)."""
    stack = np.stack([_view(s, lo, hi, dtype) for s in snaps])  # T x N
    d = np.abs(np.diff(stack, axis=0))
    moved = (d > 0) & (d <= max_step)
    frac = moved.mean(axis=0) if moved.shape[0] else np.zeros(stack.shape[1])
    nz = (stack != 0).mean(axis=0)
    lo_f, hi_f = move_frac
    mask = (frac >= lo_f) & (frac <= hi_f) & (nz >= nonzero_frac)
    idx = np.flatnonzero(mask)
    out = []
    for i in idx:
        out.append({
            "addr": lo + int(i) * np.dtype(dtype).itemsize,
            "dtype": dtype[1:],
            "move_frac": round(float(frac[i]), 3),
            "series": [int(x) for x in stack[::max(1, len(stack) // 8), i]],
        })
    out.sort(key=lambda r: -r["move_frac"])
    return out


def group_blocks(fields, stride_hint=(0x8, 0x80)):
    """Cluster nearby live fields into entity blocks."""
    if not fields:
        return []
    fs = sorted(fields, key=lambda f: f["addr"])
    blocks, cur = [], [fs[0]]
    lo_gap, hi_gap = stride_hint
    for f in fs[1:]:
        gap = f["addr"] - cur[-1]["addr"]
        if lo_gap <= gap <= hi_gap:
            cur.append(f)
        else:
            if len(cur) >= 2:
                blocks.append(cur)
            cur = [f]
    if len(cur) >= 2:
        blocks.append(cur)
    out = []
    for b in blocks:
        out.append({
            "start": b[0]["addr"], "end": b[-1]["addr"],
            "n_live": len(b),
            "addrs": [f["addr"] for f in b],
            "dtypes": sorted({f["dtype"] for f in b}),
        })
    out.sort(key=lambda b: (-b["n_live"], b["start"]))
    return out


def slot_count(snaps, lo, hi, dtype="<u4", slot=0x10, off=0x0,
               active=(1, 0x00FFFFFF), max_slots=32):
    """Count active slots over time for a fixed-stride table.

    Returns per-sample active counts — spikes = actors spawning/dying.
    """
    sz = np.dtype(dtype).itemsize
    counts = []
    for s in snaps:
        v = _view(s, lo, hi, dtype)
        n = min(max_slots, len(v) // slot)
        active_n = 0
        for k in range(n):
            val = v[k * slot // sz + off // sz]
            if active[0] <= val <= active[1]:
                active_n += 1
        counts.append(active_n)
    return counts

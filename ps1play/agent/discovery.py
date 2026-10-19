"""Discovery — find *meaningful* RAM addresses by playing, not by cheating.

The agent only injects buttons (like a human) and watches which bytes move.
Three generic, game-agnostic probes:

1. diff()        : what changed during a window (menus, events, timers)
2. correlate()   : A/B windows (idle vs holding a button) => movement
                   counters such as player X/Y, camera scroll
3. input_echo()  : find the address that mirrors the joypad bitmask
4. monotonic()   : ever-increasing counters => score / progress

Results become the per-game profile: discovered ONCE, reused forever.
"""
import numpy as np

from ..core.inputmap import parse_buttons
from ..core.memory import digest

DTYPES = {"u16": ("<u2", 2), "u32": ("<u4", 4)}


def _views(u8):
    out = {}
    for name, (dt, _) in DTYPES.items():
        n = len(u8) // DTYPES[name][1]
        out[name] = u8[:n * DTYPES[name][1]].view(dt)
    return out


def _sdiff(a, b, bits):
    """Signed delta with wrap-around resolved to minimal magnitude."""
    d = a.astype(np.int64) - b.astype(np.int64)
    half = 1 << (bits - 1)
    full = 1 << bits
    d = np.where(d > half, d - full, d)
    d = np.where(d < -half, d + full, d)
    return d


# movement-like |delta| band per 30-45f window: real counters move a
# little every frame; one-off byte flips jump by huge amounts -> excluded
SANE_MIN = 4
SANE_MAX = {"u16": 2048, "u32": 40000}   # u32 covers fixed-point (px<<8)
BITS = {"u16": 16, "u32": 32}

# RAM top 64KiB: SPU/DMA audio buffers in many games -> never game counters
AUDIO_ZONE = 0x1FC000


class DiscoverySession:
    def __init__(self, core, mem):
        self.core = core
        self.mem = mem

    def _run(self, frames, buttons=None):
        if buttons is None:
            self.core.set_buttons(set())
        else:
            self.core.set_buttons(buttons)
        for _ in range(frames):
            self.core.run_frame()

    # ---------------------------------------------------------------
    def diff(self, frames=45, buttons=None, top=10):
        """Snapshot -> run -> diff. `buttons` may be held during the window."""
        before = self.mem.snapshot()
        self._run(frames, buttons)
        after = self.mem.snapshot()
        changed = np.flatnonzero(before != after)
        regions = []
        if changed.size:
            gaps = np.flatnonzero(np.diff(changed) > 4)
            starts = np.concatenate(([0], gaps + 1))
            ends = np.concatenate((gaps, [changed.size - 1]))
            for s, e in zip(starts, ends):
                a, b = int(changed[s]), int(changed[e])
                regions.append((a, b + 1, e - s + 1))
            regions.sort(key=lambda r: -r[2])
        return {"digest_before": digest(before), "digest_after": digest(after),
                "changed_bytes": int(changed.size),
                "regions": [{"addr": a, "len": b - a, "ch": c}
                            for (a, b, c) in regions[:top]]}

    # ---------------------------------------------------------------
    def correlate(self, buttons, window=45, reps=2, top=14):
        """Hold `buttons` vs idle; find words that move consistently.

        Sequence per rep: idle window, action window. An address qualifies
        when its delta has the same sign in every rep and the idle window
        itself is quiet (filters game noise).
        """
        idle_snaps, act_snaps = [], []
        for _ in range(reps):
            self._run(window, set())
            idle_snaps.append(self.mem.snapshot())
            self._run(window, buttons)
            act_snaps.append(self.mem.snapshot())

        idle0, idle1 = _views(idle_snaps[0]), _views(idle_snaps[1])
        act0, act1 = _views(act_snaps[0]), _views(act_snaps[1])
        results = []
        for dt in DTYPES:
            i0, i1 = idle0[dt], idle1[dt]
            a0, a1 = act0[dt], act1[dt]
            bits = BITS[dt]
            d1 = _sdiff(a0, i0, bits)      # act1 - idle1
            d2 = _sdiff(a1, i1, bits)      # act2 - idle2
            idl = _sdiff(i1, i0, bits)     # idle drift (noise floor)
            quiet = np.abs(idl) <= 1
            same_sign = (np.sign(d1) == np.sign(d2)) & (d1 != 0)
            band = ((np.abs(d1) >= SANE_MIN) & (np.abs(d2) >= SANE_MIN) &
                    (np.abs(d1) <= SANE_MAX[dt]) & (np.abs(d2) <= SANE_MAX[dt]))
            ratio_ok = (np.minimum(np.abs(d1), np.abs(d2)) >=
                        0.2 * np.maximum(np.abs(d1), np.abs(d2)))
            mask = quiet & same_sign & band & ratio_ok
            if dt == "u32":
                # high-word flips (delta = k*65536) are aliasing junk
                m65536 = ((d1 % 65536) == 0) | ((d2 % 65536) == 0)
                mask &= ~m65536
            idx = np.flatnonzero(mask)
            for i in idx[:4000]:
                addr = int(i) * DTYPES[dt][1]
                if addr >= AUDIO_ZONE:
                    continue
                score = int(min(abs(d1[i]), abs(d2[i])))
                results.append({
                    "addr": addr, "dtype": dt,
                    "deltas": [int(d1[i]), int(d2[i])], "score": score,
                    "dir": "+" if d1[i] > 0 else "-",
                })
        results.sort(key=lambda r: -r["score"])
        # dedup: drop u32 hits that alias a better u16 hit? keep both views
        return results[:top]

    # ---------------------------------------------------------------
    def input_echo(self, buttons, window=20, reps=2):
        """Find a word whose bits equal the pressed-button mask while held."""
        buttons = parse_buttons(buttons)
        bits = 0
        for b in buttons:
            bits |= (1 << b)
        masks = [bits, bits & 0xFF, (bits & 0xF) | ((bits & 0xF0) << 8)]
        hits = {}
        for _ in range(reps):
            self._run(window, set())
            idle = self.mem.snapshot()
            self._run(window, buttons)
            act = self.mem.snapshot()
            for dt in DTYPES:
                iv, av = _views(idle)[dt], _views(act)[dt]
                for m in masks:
                    for val, tag in ((m, "eq"), (m, "ne")):
                        if tag == "eq":
                            sel = (av == m) & (iv != m)
                        else:
                            sel = (av != m) & (iv == m)
                        idx = np.flatnonzero(sel)
                        for i in idx[:64]:
                            key = (int(i) * DTYPES[dt][1], dt)
                            hits[key] = hits.get(key, 0) + 1
        out = [{"addr": a, "dtype": dt, "mask": hex(masks[0]), "hits": h}
               for (a, dt), h in sorted(hits.items(), key=lambda kv: -kv[1])]
        return out[:8]

    # ---------------------------------------------------------------
    def verify_series(self, states, base_state, addr, dtype,
                      btn="RIGHT", frames=60, step=10):
        """Restore the SAME savestate, sample value series idle vs held.

        A real movement counter: consistent per-step sign while held,
        nearly flat while idle. Returns quality-ranked dict or None.
        """
        read = self.mem.u32 if dtype == "u32" else self.mem.u16
        bits = BITS[dtype]
        half = 1 << (bits - 1)

        def sample(buttons):
            states.load(self.core, base_state)
            vals = [read(addr)]
            for _ in range(frames // step):
                self._run(step, buttons)
                vals.append(read(addr))
            return vals

        idle = sample(set())
        act = sample({btn})
        ds_act, ds_idle = [], []
        for series, acc in ((idle, ds_idle), (act, ds_act)):
            for i in range(len(series) - 1):
                d = series[i + 1] - series[i]
                if d > half:
                    d -= (1 << bits)
                elif d < -half:
                    d += (1 << bits)
                acc.append(d)
        if not ds_act:
            return None
        m_act = sum(ds_act) / len(ds_act)
        m_idle = sum(ds_idle) / len(ds_idle)
        same = sum(1 for d in ds_act if d != 0 and (d > 0) == (m_act > 0))
        mono = same / len(ds_act)
        if abs(m_act) <= 2 * abs(m_idle) + 1:
            return None
        return {"addr": addr, "dtype": dtype, "btn": btn,
                "m_act": round(m_act, 2), "m_idle": round(m_idle, 2),
                "mono_frac": round(mono, 2),
                "quality": round(abs(m_act) * mono, 2),
                "act_series": act, "idle_series": idle}

    # ---------------------------------------------------------------
    def monotonic(self, frames=180, step=30, buttons=None, top=10):
        """Counters that never decrease => score, progress, timers."""
        snaps = []
        nwin = max(2, frames // step)
        for _ in range(nwin):
            self._run(step, buttons if buttons is not None else set())
            snaps.append(self.mem.snapshot())
        out = []
        for dt in DTYPES:
            views = [_views(s)[dt].astype(np.int64) for s in snaps]
            acc_pos = np.ones_like(views[0], dtype=bool)
            any_inc = np.zeros_like(views[0], dtype=bool)
            for a, b in zip(views, views[1:]):
                d = b - a
                acc_pos &= (d >= 0)
                any_inc |= (d > 0)
            idx = np.flatnonzero(acc_pos & any_inc)
            for i in idx[:2000]:
                total = int(views[-1][i] - views[0][i])
                if 0 < total <= 10000:
                    out.append({"addr": int(i) * DTYPES[dt][1], "dtype": dt,
                                "gain": total,
                                "val_now": int(views[-1][i])})
        out.sort(key=lambda r: -r["gain"])
        return out[:top]

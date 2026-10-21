"""Common experiment harness (Issue #6 Phase C).

A thin, standardized layer OVER the existing PS1Play runner — not a
parallel runner. Every experiment records compact JSONL events plus a
readable summary; large artifacts (snapshots, screenshots) stay on disk
and only hashes/paths enter the trace.

Standard ops: boot observe act step_frames checkpoint restore replay
watch compare restart stop. Unsupported operations raise explicit
errors (UnsupportedCapabilityError for plugin-level ops, CapabilityError
for backend-level ones) — never silent no-ops.

Guards: frame/time budgets, hang detection (zero-activity windows),
bounded memory observation (sampled fields + hashes, never full RAM
dumps in the trace).
"""
import hashlib
import json
import os
import time

import numpy as np

from .plugins.contract import UnsupportedCapabilityError  # noqa: F401


class CapabilityError(RuntimeError):
    """The backend/plugin cannot perform this op. Explicit, not silent."""


def _ram_hash(snapshot):
    return hashlib.blake2b(bytes(snapshot), digest_size=8).hexdigest()


class ExperimentHarness:
    """One harness instance per experiment run."""

    def __init__(self, play, out_dir, max_frames=200000,
                 max_wallclock_s=1800, hang_window=900):
        self.p = play
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.trace_path = os.path.join(out_dir, "trace.jsonl")
        self._t0 = time.time()
        self._start_fc = None
        self.max_frames = max_frames
        self.max_wallclock_s = max_wallclock_s
        self.hang_window = hang_window
        self._activity = []          # changed-byte counts per op
        self._runs = {}              # name -> list of (fc, ram_hash)
        self._closed = False

    # ---------------- plumbing ----------------
    def _log(self, op, **fields):
        row = {"ts": time.time(), "op": op}
        row.update(fields)
        with open(self.trace_path, "a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return row

    def _guard(self, frames):
        fc = self.p.core.frames_run
        if self._start_fc is None:
            self._start_fc = fc
        used = fc - self._start_fc
        wall = time.time() - self._t0
        if used + frames > self.max_frames:
            raise CapabilityError(
                f"frame budget exceeded: {used}+{frames} > {self.max_frames}")
        if wall > self.max_wallclock_s:
            raise CapabilityError(
                f"wall-clock budget exceeded: {wall:.0f}s")

    def _advance(self):
        pass  # frame bookkeeping lives in the core; kept for symmetry

    def _activity_check(self, changed):
        """Hang detection from an independent signal: a run of fully
        static windows means the game is stalled (not 'stable')."""
        self._activity.append(changed)
        tail = self._activity[-self.hang_window // 60:]
        if len(tail) >= 3 and all(c == 0 for c in tail[-3:]):
            self._log("hang_suspected", static_windows=3)
            return True
        return False

    # ---------------- standard ops ----------------
    def boot(self):
        info = self.p.boot()
        self._start_fc = self.p.core.frames_run
        self._log("boot", **{k: info.get(k) for k in
                             ("core", "serial", "plugin", "ram_bytes")})
        return info

    def observe(self):
        return self.p.observe()

    def act(self, buttons, frames):
        """Deterministic input for exactly `frames` frames + activity."""
        self._guard(frames)
        s0 = self.p.mem.snapshot()
        self.p.core.run(frames, buttons)
        s1 = self.p.mem.snapshot()
        changed = int(np.count_nonzero(np.frombuffer(s0, np.uint8) !=
                                       np.frombuffer(s1, np.uint8)))
        self._advance()
        hung = self._activity_check(changed)
        row = self._log("act", buttons=sorted(buttons), frames=frames,
                        changed=changed, ram_hash=_ram_hash(s1),
                        hang=hung)
        return row

    def step_frames(self, frames, buttons=None):
        """Frame-exact advance with optional held buttons."""
        return self.act(buttons or set(), frames)

    def checkpoint(self, name):
        res = self.p.save_state(name)
        self._log("checkpoint", name=name, **{k: res.get(k)
                                              for k in ("bytes",)})
        return res

    def restore(self, name):
        res = self.p.load_state(name)
        self._log("restore", name=name,
                  fc=self.p.core.frames_run)
        return res

    def replay(self, name, frames, buttons=None):
        """Restore + deterministic re-run + end-state hash."""
        self.restore(name)
        act_row = self.act(buttons or set(), frames)
        row = self._log("replay", name=name, frames=frames,
                        end_hash=act_row["ram_hash"])
        return row

    def watch(self, fields, frames, every=30, buttons=None):
        """Bounded sampled observation of declared fields during a run.
        fields: {'role': (addr, dtype)} — sampled every `every` frames,
        never the full RAM dump."""
        self._guard(frames)
        samples = []
        done = 0
        while done < frames:
            n = min(every, frames - done)
            self.p.core.run(n, buttons or set())
            done += n
            self._advance()
            s = {"fc": self.p.core.frames_run}
            for role, (addr, dt) in fields.items():
                if dt == "u8":
                    s[role] = self.p.mem.u8(addr)
                elif dt == "u32":
                    s[role] = self.p.mem.u32(addr)
                else:
                    s[role] = self.p.mem.u16(addr)
            samples.append(s)
        self._log("watch", frames=frames, every=every,
                  fields=list(fields), samples=len(samples))
        return samples

    def compare(self, name_a, name_b, frames, buttons_a=None,
                buttons_b=None, chunk=60):
        """First-divergence finder: two branches from their checkpoints,
        chunk-wise RAM hashing, byte-level diff at the first mismatch."""
        self._guard(frames)
        self.restore(name_a)
        hashes_a = []
        done = 0
        while done < frames:
            n = min(chunk, frames - done)
            s0 = self.p.mem.snapshot()
            self.p.core.run(n, buttons_a or set())
            self._advance()
            hashes_a.append(_ram_hash(self.p.mem.snapshot()))
            done += n
        self._guard(frames)
        self.restore(name_b)
        hashes_b = []
        done = 0
        while done < frames:
            n = min(chunk, frames - done)
            self.p.core.run(n, buttons_b or set())
            self._advance()
            hashes_b.append(_ram_hash(self.p.mem.snapshot()))
            done += n
        first = None
        for i, (ha, hb) in enumerate(zip(hashes_a, hashes_b)):
            if ha != hb:
                first = i
                break
        byte_diff = None
        if first is not None:
            self.restore(name_a)
            s0 = self.p.mem.snapshot()
            self.p.core.run((first + 1) * chunk, buttons_a or set())
            ea = np.frombuffer(self.p.mem.snapshot(), np.uint8)
            self.restore(name_b)
            self.p.core.run((first + 1) * chunk, buttons_b or set())
            eb = np.frombuffer(self.p.mem.snapshot(), np.uint8)
            d = np.nonzero(ea != eb)[0]
            byte_diff = {"bytes": int(len(d)),
                         "first": int(d[0]) if len(d) else None,
                         "last": int(d[-1]) if len(d) else None}
        row = self._log("compare", a=name_a, b=name_b, frames=frames,
                        first_divergent_chunk=first,
                        total_chunks=len(hashes_a), **(byte_diff or {}))
        row["byte_diff"] = byte_diff
        return row

    def restart(self):
        self.p.core.reset()
        info = self.boot()
        self._log("restart")
        return info

    def stop(self):
        """Finalize: compact summary from the JSONL trace."""
        if self._closed:
            return None
        self._closed = True
        events = []
        with open(self.trace_path) as f:
            for line in f:
                events.append(json.loads(line))
        summary = {
            "ops": len(events),
            "frames_run": self.p.core.frames_run - (self._start_fc or 0),
            "wallclock_s": round(time.time() - self._t0, 2),
            "hang_suspected": any(e.get("op") == "hang_suspected"
                                  for e in events),
            "trace": self.trace_path,
            "trace_bytes": os.path.getsize(self.trace_path),
        }
        with open(os.path.join(self.out_dir, "summary.json"), "w") as f:
            json.dump(summary, f, indent=1)
        self._log("stop", **summary)
        return summary

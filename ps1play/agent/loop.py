"""AgentLoop — sense → decide → act, with checkpointing and a tiny journal."""
import time


class AgentLoop:
    def __init__(self, core, mem, plugin, observer, states, journal=None):
        self.core = core
        self.mem = mem
        self.plugin = plugin
        self.obs = observer
        self.states = states
        self.journal = journal

    def run(self, frames, chunk=60, checkpoint_every=1800,
            stall_limit=300, t_start=0, tag="play"):
        """Play `frames` using plugin.policy. Human-like: only buttons.

        stall: how long a watched feature has been frozen. Plugins use it
        to jump / restart / press START, exactly what a human does.
        """
        t = t_start
        stall = 0
        last_feat_val = None
        next_ckpt = checkpoint_every
        t0 = time.time()
        while t < t_start + frames:
            n = min(chunk, t_start + frames - t)
            obs = self.obs.observe(t)
            feat = self.plugin.features(self.mem, obs)
            watched = feat.get("x") if "x" in feat else None
            if watched is not None and last_feat_val is not None:
                stall = stall + n if watched == last_feat_val else 0
            last_feat_val = watched
            ctx = {"t": t, "chunk": n, "stall": stall, "feat": feat,
                   "obs": obs}
            segs = self.plugin.policy(ctx) or [{"frames": n, "btns": set()}]
            done = 0
            for seg in segs:
                k = min(seg["frames"], n - done)
                if k <= 0:
                    continue
                self.core.run(k, seg["btns"])
                done += k
            if done < n:
                self.core.run(n - done)
            if ctx.get("stall_reset"):
                stall = 0
            t += n
            if self.journal:
                self.journal.log({
                    "t": t, "tag": tag, "feat": feat,
                    "digest": obs.get("digest"),
                    "changed": obs.get("changed_bytes"),
                })
            if next_ckpt and t >= next_ckpt:
                self.states.save(self.core, f"auto_{t // 1000:04d}k",
                                 meta={"stage": "play"})
                self.states.prune()
                next_ckpt += checkpoint_every
        dt = time.time() - t0
        return {"frames": frames, "wall_s": round(dt, 1),
                "fps": round(frames / dt, 1) if dt else 0.0,
                "t_end": t}

"""WorldModel — the UNIVERSAL 'what is on screen' base for any game.

Zero tokens, zero pixels: pure RAM behaviour analysis (numpy). The model
answers, every frame, the questions a human answers by LOOKING:

  * how many enemies, and where (relative to me)
  * is a bullet/projectile flying at me
  * is there a health item I should eat
  * is there a pickup on the ground I should collect

Method (game-agnostic, learned live in ~2-3k frames, O(MB) memory):
  1. ONLINE pass: stream frame pairs, accumulate per-word stats
     (change fraction, nonzero fraction, mean step) — no snapshot storage
  2. candidate "coordinate-like" words: often-changing, small steps,
     long-lived, not a calibrated counter
  3. COLLECT pass: re-run a short probe and keep time-series ONLY for
     the few thousand candidates
  4. classify slots by behaviour:
       PLAYER : x follows OUR input (rises while running, flat standing)
       ENEMY  : moves WITHOUT our input; fast ones = BULLET
       ITEM   : static until touched, then vanishes (spawn/despawn)
  5. read_world() rebuilds the live scene every frame from the slots

If discovery cannot certify slots, read_world() returns an empty scene
and the semantic policy falls back to event-driven telemetry rules.
"""
import numpy as np

AUDIO_ZONE = 0x1FC000          # top of RAM = SPU buffers, never entities
SCAN_HI = 0x100000             # entity/counter zone of PS1 games (1MB)


class StructSlot:
    """One entity table slot: base offset + x/y field offsets."""

    __slots__ = ("base", "stride", "x_off", "y_off", "cls",
                 "x_addr", "y_addr", "last")

    def __init__(self, base, stride, x_off, y_off, cls="unknown"):
        self.base, self.stride = base, stride
        self.x_off, self.y_off = x_off, y_off
        self.cls = cls
        self.x_addr = base + x_off
        self.y_addr = base + y_off
        self.last = None

    def to_dict(self):
        return {"base": hex(self.base), "stride": self.stride,
                "x": hex(self.x_off), "y": hex(self.y_off),
                "cls": self.cls}


class WorldModel:
    def __init__(self, mem, counters=None):
        self.mem = mem
        self.slots = []
        self.player_x_addr = None
        self.player_y_addr = None
        self.counters = counters or {}     # addr -> role (exclude from scan)
        self.discovery = {}

    # ================================================================
    # DISCOVERY
    # ================================================================
    def discover(self, core, states, base_state, budget=2400, dbg=False):
        states.load(core, base_state)
        n_w = SCAN_HI // 2
        chg = np.zeros(n_w, np.int32)
        nz = np.zeros(n_w, np.int32)
        step = np.zeros(n_w, np.float64)
        prev = self.mem.ram[0:SCAN_HI].view("<u2").astype(np.int32)
        total = 0

        def _sample():
            nonlocal prev, total, chg, nz, step
            cur = self.mem.ram[0:SCAN_HI].view("<u2").astype(np.int32)
            d = cur - prev
            m = d != 0
            chg += m
            nz += cur != 0
            step += np.abs(d)
            prev = cur
            total += 1

        # ---- phase A: advance + fire (movement, kills) ------------------
        half = budget // 2
        for i in range(half):
            core.set_buttons({"RIGHT", "Y"} if (i // 30) % 2 == 0
                             else {"RIGHT"})
            core.run_frame()
            if i % 2 == 0:
                _sample()
        # ---- phase B: stand and fight (enemies act on their own) --------
        for i in range(half):
            core.set_buttons({"Y"} if (i // 20) % 2 == 0 else set())
            core.run_frame()
            if i % 2 == 0:
                _sample()

        chg_frac = chg / max(total, 1)
        nz_frac = nz / max(total, 1)
        mean_step = step / np.maximum(chg, 1)

        excl = {a // 2 for a in self.counters}
        if self.player_x_addr:
            for a in range(self.player_x_addr - 8, self.player_x_addr + 9):
                excl.add(a // 2)

        # coordinate-like: anything that moves smoothly OR continuously
        # (16.16 fixed-point LOW words change on ~every frame with big
        # steps — they MUST be allowed in, they are the best anchors)
        mask = ((chg_frac > 0.04) & (mean_step <= 0x20000)
                & (nz_frac > 0.4))
        idx = np.flatnonzero(mask)
        idx = np.array([i for i in idx if int(i) not in excl
                        and int(i) * 2 < SCAN_HI - 8], dtype=np.int64)
        # cap: prefer mid-frequency changers (motion-like)
        if len(idx) > 4000:
            score = 1.0 - np.abs(chg_frac[idx] - 0.5)
            idx = idx[np.argsort(-score)][:4000]
            idx = np.sort(idx)
        cands = [int(i) * 2 for i in idx]
        if dbg:
            print(f"[world] online pass: {total} samples, "
                  f"{len(cands)} candidate words", flush=True)

        # ---- collect pass: series only for candidates (vectorised) ----
        states.load(core, base_state)
        idx_w = (np.array(cands, dtype=np.int64) // 2)
        T = 600
        series = np.zeros((T, len(cands)), dtype=np.int32)
        acts = []
        ci = 0
        for i in range(T):
            core.set_buttons({"RIGHT", "Y"} if i < T // 2 else
                             ({"Y"} if (i // 20) % 2 == 0 else set()))
            core.run_frame()
            if i % 2 == 0 and ci < T:
                w = self.mem.ram[0:SCAN_HI].view("<u2")
                series[ci] = w[idx_w]
                acts.append("run" if i < T // 2 else "stand")
                ci += 1
        series = series[:ci]
        acts = acts[:ci]

        # ---- cluster + classify -----------------------------------------
        blocks = self._cluster(cands, max_gap=0x24, min_size=2)
        slots = []
        for b in blocks[:60]:
            s = self._classify_slot(b, cands, series, acts)
            if s:
                slots.append(s)
        self.slots = slots

        # player anchor from slots if calibration missed it
        if self.player_x_addr is None:
            for s in slots:
                if s.cls == "player":
                    self.player_x_addr = s.x_addr
                    if s.y_addr != s.x_addr:
                        self.player_y_addr = s.y_addr
                    break

        counts = {}
        for s in slots:
            counts[s.cls] = counts.get(s.cls, 0) + 1
        self.discovery = {"samples": total, "cand_words": len(cands),
                          "blocks": len(blocks), "slots": len(slots),
                          "classes": counts,
                          "player_anchor": (hex(self.player_x_addr)
                                            if self.player_x_addr else None)}
        if dbg:
            print(f"[world] discovery: {self.discovery}", flush=True)
            for s in slots[:14]:
                print("   ", s.to_dict(), flush=True)
        return self.discovery

    def _cluster(self, addrs, max_gap=0x24, min_size=2):
        if not addrs:
            return []
        blocks, cur = [], [addrs[0]]
        for a in addrs[1:]:
            if a - cur[-1] <= max_gap:
                cur.append(a)
            else:
                if len(cur) >= min_size:
                    blocks.append(cur)
                cur = [a]
        if len(cur) >= min_size:
            blocks.append(cur)
        blocks.sort(key=len, reverse=True)
        return blocks

    def _classify_slot(self, addrs, all_cands, series, acts):
        """Behavioural classification of one candidate struct block.
        series: T x NC matrix; addrs: byte addresses aligned to columns."""
        col_of = {a: k for k, a in enumerate(all_cands)}
        T = len(acts)
        scored = []
        for a in addrs:
            k = col_of.get(a)
            if k is None:
                continue
            col = series[:, k]
            dd = np.abs(np.diff(col))
            nz = float((col != 0).mean())
            score = float((dd > 0).mean()) * nz
            scored.append((score, a, col))
        scored.sort(key=lambda t: -t[0])
        if len(scored) < 2:
            return None
        sx, ax, cx = scored[0]
        sy = ay = cy = None
        for s in scored[1:]:
            if s[1] != ax:
                sy, ay, cy = s
                break
        if ay is None:
            return None

        run_d = [int(cx[i + 1] - cx[i]) for i in range(T - 1)
                 if acts[i] == "run"]
        std_d = [int(cx[i + 1] - cx[i]) for i in range(T - 1)
                 if acts[i] == "stand"]
        run_gain = sum(run_d)
        base = ax & ~3
        # PLAYER: x advances strongly while running, ~flat while standing
        if run_gain > 400 and abs(sum(std_d)) < max(200, run_gain // 4):
            return StructSlot(base, 4, ax - base, ay - base, "player")
        # ENEMY: keeps moving while we stand still (independent motion)
        st_move = sum(1 for v in std_d if v != 0)
        run_move = sum(1 for v in run_d if v != 0)
        if st_move > len(std_d) * 0.3 and run_move > 0:
            speed = np.abs(np.array([v for v in run_d + std_d if v]))
            cls = "bullet" if (len(speed) and np.median(speed) > 300) \
                else "enemy"
            return StructSlot(base, 4, ax - base, ay - base, cls)
        # ITEM: mostly static, occasional spawn/despawn jumps
        changes = sum(1 for v in run_d + std_d if v != 0)
        if changes <= (T - 1) * 0.12:
            return StructSlot(base, 4, ax - base, ay - base, "item")
        return None

    # ================================================================
    # LIVE SCENE
    # ================================================================
    def read_world(self, core=None):
        """Rebuild the scene: player + classified actors, in the player's
        coordinate frame (dx = actor_x - player_x)."""
        anchor = self.player_x_addr
        if anchor is None:
            for s in self.slots:
                if s.cls == "player":
                    anchor = s.x_addr
                    break
        if anchor is None:
            return {"player": None, "enemies": [], "bullets": [],
                    "items": [], "health": [], "n_enemies": 0,
                    "threat": None, "nearest_enemy": None,
                    "nearest_health": None, "nearest_item": None}
        px = self._rd(anchor)
        py = self._rd(self.player_y_addr) if self.player_y_addr else 0
        out = {"player": {"x": px, "y": py},
               "enemies": [], "bullets": [], "items": [], "health": []}
        for s in self.slots:
            if s.cls == "player":
                continue
            try:
                ax = self._rd(s.x_addr)
                ay = self._rd(s.y_addr)
            except Exception:
                continue
            if ax == 0 or not (0 < ax < 0x10000):
                continue
            dx = ax - px
            if abs(dx) > 0x4000:
                continue
            v = 0
            if s.last is not None:
                v = ax - s.last
            s.last = ax
            ent = {"dx": dx, "dy": ay - py, "x": ax, "y": ay, "vx": v,
                   "slot": s.base}   # generic slot identity (additive;
                                     # consumed by the MSX scene adapter
                                     # for cross-frame y tracking)
            if s.cls == "enemy":
                out["enemies"].append(ent)
            elif s.cls == "bullet":
                if abs(v) >= 2 and abs(dx) < 3000:
                    out["bullets"].append(ent)
            elif s.cls == "item":
                out["items"].append(ent)
        return out

    def _rd(self, addr):
        return self.mem.u16(addr)

    # ---------------- helpers ----------------
    def nearest(self, scene, kind, max_dx=0x2000):
        lst = scene.get(kind) or []
        lst = [e for e in lst if abs(e["dx"]) <= max_dx]
        if not lst:
            return None
        return min(lst, key=lambda e: abs(e["dx"]))

    def threat(self, scene, max_dx=0x1000):
        """Closest bullet heading TOWARD the player (tight gates: the
        bullet slots are heuristic, only confident fast movers count)."""
        best = None
        for b in scene.get("bullets") or []:
            toward = (b["dx"] > 0 and b["vx"] < -3) or \
                     (b["dx"] < 0 and b["vx"] > 3)
            if toward and abs(b["dx"]) < max_dx:
                if best is None or abs(b["dx"]) < abs(best["dx"]):
                    best = b
        return best

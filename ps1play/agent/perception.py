"""PerceptionGuard — keeps the GameShark-grade perception alive.

Discovery this session (SLUS-01212, our dump):
  * the gameplay-data cluster (hp/bombs/ammo/lives/timer/weapon, layout
    exactly as the published GameShark codes imply) is DYNAMICALLY
    placed: it moves per BOOT and per MISSION-RELOAD (continue/death).
  * within one mission instance the layout is rock solid, and the
    internal offsets match the published codes exactly, so ONE
    event-verified anchor (bombs: -1 exactly per grenade, found by
    live A-diff) translates the whole cluster by a per-instance delta.
  * static globals (pad word 0x0D4948, score 0x0EE318, POW 0x087A78)
    never move — verified by static xrefs + live probes.

The guard: anchor() finds bombs by A-diff; read() returns the semantic
state; valid() sanity-checks every read; reanchor() re-runs after any
mission reload. Zero tokens, all numpy.
"""
import numpy as np

PUB = {"bombs": 0x0398B4, "ammo": 0x02DCD8, "hp": 0x032764,
       "lives": 0x0475A8, "timer": 0x0295F8, "weapon": 0x02D92C}
PAD_P1 = 0x0D4948
SCORE = 0x0EE318
POW = 0x087A78

PAD_BITS = {"RIGHT": 0x0020, "LEFT": 0x0080, "UP": 0x0010,
            "DOWN": 0x0040, "START": 0x0008}   # verified empirically


class PerceptionGuard:
    def __init__(self, p):
        self.p = p
        self.delta = None
        self.addrs = {}
        self.hp_scale = None            # 100 or 200
        self.anchors_done = 0

    # ---------------- anchor ----------------
    def anchor(self, tries=3, log=print):
        """Find bombs via live A-diff (exact -1, idle-stable, in 3..30).
        NOTE: hp is NOT assumed to follow the cluster delta — it gets its
        own freeze-verified anchor (find_player_hp)."""
        p = self.p
        from mission import responsive, recover
        for k in range(tries):
            ok, _ = responsive(p)
            if not ok:
                recover(p, log=log)
            p.save_state("_pg")
            i0, i1 = self._trial("_pg", set())
            a0, a1 = self._trial("_pg", {"A"})
            ai0 = i0[:0x1FC000].view("<u2").astype(np.int32)
            ai1 = i1[:0x1FC000].view("<u2").astype(np.int32)
            aa0 = a0[:0x1FC000].view("<u2").astype(np.int32)
            aa1 = a1[:0x1FC000].view("<u2").astype(np.int32)
            d_idle, d_a = ai1 - ai0, aa1 - aa0
            c = np.flatnonzero((d_a != d_idle) & (d_a == -1) &
                               (aa0 >= 3) & (aa0 <= 30) & (ai0 == aa0))
            for w in c.tolist():
                addr = int(w) * 2
                p.load_state("_pg")
                p.core.run(10, set())
                v0 = p.mem.u16(addr)
                p.core.run(15, {"A"})
                p.core.run(90, set())
                p._advance()
                if p.mem.u16(addr) == v0 - 1:      # 2nd grenade confirms
                    self.addrs["bombs"] = addr
                    self.delta = addr - PUB["bombs"]
                    self.anchors_done += 1
                    log(f"[percept] anchor #{self.anchors_done}: "
                        f"bombs@{addr:#x} delta={self.delta:+#x}")
                    return {"ok": True, "bombs": hex(addr),
                            "delta": self.delta}
            p.load_state("_pg")
            log(f"[percept] anchor try{k}: no candidate")
        return {"ok": False}

    def _trial(self, base, action):
        p = self.p
        p.load_state(base)
        p.core.run(8, set())
        s0 = p.mem.snapshot()
        p.core.run(15, action)
        p.core.run(90, set())
        p._advance()
        return s0, p.mem.snapshot()

    # ---------------- reads ----------------
    def read(self, role):
        a = self.addrs.get(role)
        if a is None:
            return None
        try:
            return self.p.mem.u16(a)
        except Exception:
            return None

    def state(self):
        return {role: self.read(role) for role in PUB}

    def valid(self):
        """Is the current anchor still pointing at live game data?"""
        b = self.read("bombs")
        hp = self.read("hp")
        if b is None or hp is None:
            return False
        bombs_ok = 0 <= b <= 40
        hp_ok = (0 <= hp <= 110) if (self.hp_scale or 100) == 100 \
            else (0 <= hp <= 210)
        return bombs_ok and hp_ok

    def pad(self):
        return self.p.mem.u16(PAD_P1)

    def score(self):
        return self.p.mem.u32(SCORE)

    # ---------------- player hp: freeze-verified anchor ----------------
    def find_player_hp(self, log=print, max_cands=4, window=480):
        """THE safe way to get the Invincible address.
        1) from a fresh spawn, stand still: hp-band words that DROP are
           hp-like (player got stabbed)
        2) freeze each dropper; the one whose value CANNOT drop while the
           player SURVIVES the same window is the player's own hp.
        Only that address is safe to freeze long-term."""
        p = self.p
        from mission import responsive
        p.save_state("hpbase")
        s0 = p.mem.snapshot()
        p.core.run(window, set())
        p._advance()
        s1 = p.mem.snapshot()
        a0 = s0[:0x1FC000].view("<u2").astype(np.int32)
        a1 = s1[:0x1FC000].view("<u2").astype(np.int32)
        band = ((a0 >= 80) & (a0 <= 210) & (a1 < a0))
        cands = [int(w) * 2 for w in np.flatnonzero(band)][:max_cands]
        log(f"[percept] hp-like droppers: {[hex(a) for a in cands]}")
        if not cands:
            return None
        for addr in cands:
            p.load_state("hpbase")
            v0 = p.mem.u16(addr)
            # freeze WITHOUT the engine (direct per-frame poke)
            p.core.set_buttons(set())
            alive = True
            for _ in range(window):
                p.core.run_frame()
                p.mem.ram[addr:addr + 2] = (v0 & 0xFF, (v0 >> 8) & 0xFF)
            p._advance()
            ok, _ = responsive(p)
            v1 = p.mem.u16(addr)
            log(f"[percept] hp freeze test {addr:#x}: {v0}->{v1} "
                f"alive={ok}")
            if v1 == v0 and ok:
                self.addrs["hp"] = addr
                self.hp_scale = 200 if v0 > 150 else 100
                log(f"[percept] PLAYER HP confirmed @ {addr:#x} "
                    f"(full={v0})")
                p.load_state("hpbase")
                return addr
        p.load_state("hpbase")
        return None

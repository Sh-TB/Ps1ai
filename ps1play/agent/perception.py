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
        # v0.6 §5: per-role verification ledger. Code existing is not
        # verification: a role is VERIFIED only after its own event test.
        self.verification = {}
        self.invalidations = []

    # ---------------- observation contract (v0.6 §5) ----------------
    def _set_role(self, role, addr, status, method, frame=None,
                  confidence=0.0):
        self.addrs[role] = addr
        self.verification[role] = {
            "address": addr, "width": 2, "encoding": "u16le",
            "status": status, "verification_method": method,
            "last_verified_frame": frame, "confidence": confidence,
            "valid_for_current_mission": status in ("VERIFIED",
                                                    "CALIBRATED"),
            "source_probe": method}

    def observation_contract(self):
        """The §5 contract: EVERY public role with its honest status.
        Roles never anchored are reported PENDING with null address —
        the bombs anchor working does NOT make the rest verified."""
        contract = {}
        for role in PUB:
            v = self.verification.get(role)
            if v is None:
                contract[role] = {
                    "role": role, "value": None, "address": None,
                    "width": 2, "encoding": "u16le", "status": "PENDING",
                    "verification_method": None,
                    "last_verified_frame": None, "source_probe": None,
                    "valid_for_current_mission": False, "confidence": 0.0}
            else:
                entry = dict(v)
                entry["role"] = role
                entry["value"] = self.read(role)
                contract[role] = entry
        return contract

    def invalidate(self, reason, log=print):
        """Drop ALL dynamic-cluster roles (they move per mission reload);
        static globals (pad/score/pow) survive. Caller must re-anchor."""
        dropped = [r for r in list(self.addrs)
                   if r not in ("pad", "score", "pow")]
        for r in dropped:
            self.addrs.pop(r, None)
            v = self.verification.get(r)
            if v:
                v["status"] = "INVALID"
                v["valid_for_current_mission"] = False
        self.invalidations.append({"reason": reason, "dropped": dropped})
        log(f"[percept] INVALIDATED {dropped}: {reason}")

    def validate_anchor(self, log=print):
        """Post-reload plausibility re-check of the bombs anchor:
        in-range (0..40) and NOT increasing across a short window
        (grenades can only decrement; a rising word is a wrong field).
        Returns {"ok": bool, "reason": str}."""
        b = self.read("bombs")
        if b is None:
            return {"ok": False, "reason": "no anchor"}
        if not (0 <= b <= 40):
            self.invalidate(f"bombs out of range: {b}", log=log)
            return {"ok": False, "reason": f"out of range: {b}"}
        p = self.p
        p.core.run(30, set())
        p._advance()
        b2 = self.read("bombs")
        if b2 is not None and b2 > b:
            self.invalidate(f"bombs rose {b}->{b2}: wrong field latched",
                            log=log)
            return {"ok": False, "reason": f"rose {b}->{b2}"}
        return {"ok": True, "reason": "in range and stable/decreasing"}

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
                    self._set_role("bombs", addr, "VERIFIED",
                                   "grenade event: -1 exactly, repeated 2x",
                                   confidence=0.95)
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

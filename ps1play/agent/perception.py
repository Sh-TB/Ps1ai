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
        self.dtypes = {}          # role -> "u8" | "u16" (default u16)
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
    def _series_snaps(self):
        """Boundary snapshots around 4 separated grenade presses (no
        long idle: the mission-1 opening is lethal to idlers)."""
        p = self.p
        snaps = []

        def snap():
            snaps.append(p.mem.ram[:0x1FC000].copy())

        p.core.run(45, set())
        snap()
        p.core.run(30, set())
        snap()
        for _ in range(4):
            p.core.set_buttons({"A"})
            for _ in range(30):
                p.core.run_frame()
            p.core.set_buttons(set())
            p.core.run(60, set())
            snap()
        p._advance()
        return snaps

    @staticmethod
    def _series_vals(snaps, idx, width):
        a = [s.view("<u2" if width == 2 else np.uint8).astype(np.int32)
             for s in snaps]
        return [int(a[i][idx]) for i in (1, 2, 3, 4, 5)]

    def anchor(self, tries=3, log=print):
        """Find the REAL grenade-inventory counter via the STRICT
        4-press series: exactly -1 per separated throw, bounded 0..60,
        idle-stable, REPRODUCED from a savestate reload.

        v0.13 honesty fix: the previous '-1 x2' anchor locked onto an
        animation/scratch impostor at 0xCAF9C (its series jumps
        4->84->74 across 135 frames; scripts/scan_bombs_strict.py and
        scripts/diag_bombs_anchor.py document the trap). The real
        counter is a u8 (series 10,9,8,7,6 in this boot) which the
        u16-only A-diff scan could never see. Both u16 words and u8
        bytes are scanned here, and every candidate must reproduce
        the full series from an equivalent starting state.

        NOTE: the published-cluster 'delta' is INVALID (the state area
        is dynamically placed per boot and the old delta came from the
        impostor); translations from the published layout are never
        trusted by this guard.
        """
        p = self.p
        from mission import responsive, recover
        for k in range(tries):
            ok, _ = responsive(p)
            if not ok:
                recover(p, log=log)
            p.save_state("_pg")
            snaps = self._series_snaps()
            found = None
            for width in (2, 1):
                view = "<u2" if width == 2 else np.uint8
                a = [s.view(view).astype(np.int32) for s in snaps]
                idle_stable = a[1] == a[0]
                dec = np.ones(a[0].shape, bool)
                bounded = np.ones(a[0].shape, bool)
                for m in range(4):
                    dec &= (a[2 + m] - a[1 + m]) == -1
                for arr in a[1:6]:
                    bounded &= (arr >= 0) & (arr <= 60)
                cand = np.flatnonzero(idle_stable & dec & bounded)
                log(f"[percept] anchor strict try{k} "
                    f"width={'u16' if width == 2 else 'u8'}: "
                    f"{len(cand)} candidate(s)")
                for idx in cand.tolist()[:8]:
                    # stage 2: independent reproduction from savestate
                    p.load_state("_pg")
                    snaps2 = self._series_snaps()
                    vals = self._series_vals(snaps2, idx, width)
                    if all(vals[m + 1] - vals[m] == -1
                           for m in range(4)):
                        found = (int(idx) * width, width, vals)
                        break
                if found:
                    break
            if found:
                addr, width, vals = found
                dtype = "u8" if width == 1 else "u16"
                self._set_role(
                    "bombs", addr, "VERIFIED",
                    f"strict 4-press grenade series {vals}: -1 each, "
                    "bounded, idle-stable, reproduced from savestate",
                    confidence=0.97)
                self.dtypes["bombs"] = dtype
                self.delta = None
                self.anchors_done += 1
                log(f"[percept] anchor #{self.anchors_done}: "
                    f"bombs@{addr:#x} ({dtype}) series={vals}")
                p.load_state("_pg")
                return {"ok": True, "bombs": hex(addr),
                        "dtype": dtype, "series": vals,
                        "delta": None}
            p.load_state("_pg")
            log(f"[percept] anchor strict try{k}: no candidate")
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
            if self.dtypes.get(role) == "u8":
                return self.p.mem.u8(a)
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

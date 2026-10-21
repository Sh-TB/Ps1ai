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

# mission-init may reset the leftover demo score ~150 frames into a
# fresh mission — that reset is NOT a death (inv5 false-pulse lesson)
HP_WARMUP = 150

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
        self.hp_tier = None

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
    @staticmethod
    def _in_play(p):
        """flags_word u32@0x0EE518: 0xFF=active play, 0x1=menus/GAME
        OVER (issue-5 evidence, 4/4). Cheap death/alive oracle."""
        return int(p.mem.u32(0x0EE518)) & 0xFF == 0xFF

    # per-life score u32@0x0EE318 (VERIFIED static; the accumulator
    # RESETS on checkpoint respawn — inv2 trace: 220->8 with flags
    # still 0xff).  A drop beyond DEATH_DROP is therefore a respawn
    # (a life lost) even while flags stay 0xFF.
    SCORE_ADDR = 0x0EE318
    DEATH_DROP = 30
    @classmethod
    def _death_pulse(cls, p, last_max):
        """Return (died, new_max).  Died = lives-death oracle that
        sees checkpoint respawns (score collapse) AND game over
        (flags 0x1)."""
        if not cls._in_play(p):
            return True, last_max
        s = int(p.mem.u32(cls.SCORE_ADDR))
        if s < last_max - cls.DEATH_DROP:
            return True, last_max
        return False, max(last_max, s)

    def hp_candidates(self, log=print, window=2400, max_cands=6,
                      advance=None):
        """Stationary-burst baseline; returns the min-tracking dropper
        list (band 80..210), prioritized by proximity to the last
        freeze-VERIFIED player-HP placement (0xCABE4), plus whether
        the baseline lost a life at all (the death-differential
        discriminator only exists when it did)."""
        p = self.p

        def _btns(i):
            if advance is not None:
                return advance(i)
            # active baseline: grenade-relevant damage (Y bursts) plus
            # short RIGHT taps — NEVER a long idle (the SLUS port pulls
            # the attract demo over real play on idle; ctxchk evidence)
            if i % 120 < 40:
                return {"Y"}
            if i % 90 < 6:
                return {"RIGHT"}
            return set()

        # warm-up: the mission-init may reset the leftover demo score
        # in the first ~150 frames — that is NOT a death (inv5 lesson)
        WARMUP = HP_WARMUP
        p.save_state("hpbase")
        a0 = p.mem.ram[:0x1FC000].view("<u2").astype(np.int32)
        minv = a0.copy()
        died = False
        f = 0
        smax = int(p.mem.u32(self.SCORE_ADDR))
        while f < window:
            p.core.set_buttons(_btns(f))
            p.core.run_frame()
            f += 1
            if f > WARMUP:
                died, smax = self._death_pulse(p, smax)
            if died:
                break
            if f % 6 == 0:
                cur = p.mem.ram[:0x1FC000].view("<u2").astype(np.int32)
                np.minimum(minv, cur, out=minv)
        p._advance()
        band = ((a0 >= 80) & (a0 <= 210) & (minv < a0 - 5))
        cands = [int(w) * 2 for w in np.flatnonzero(band)]
        cands.sort(key=lambda a: abs(a - 0xCABE4))
        cands = cands[:max_cands]
        log(f"[percept] hp baseline: died={died} frames={f} "
            f"droppers={[hex(a) for a in cands]}")
        if not cands:
            p.load_state("hpbase")
        return {"cands": cands, "died": died, "frames": f,
                "restored": not cands}

    def find_player_hp(self, log=print, max_cands=6, window=2400,
                       advance=None):
        """Player-HP anchor with a two-tier honesty contract.

        Tier 1 (death differential, strongest): while the baseline
        loses a life, freeze each candidate through horizon =
        death_frame + 600; the candidate with NO life loss is the
        player HP (proven in this boot).
        Tier 2 (dropper-top + prior verification, used ONLY when the
        baseline never loses a life — the opening enemies are too
        slow to kill an idle/bursting Marco, inv6 evidence): the top
        dropper near the previously-VERIFIED 0xCABE4 placement is
        returned; its protective effect is then confirmed in-run by
        the exploration death rate (see issue5_invincible_explore),
        and any life loss during exploration counts AGAINST it."""
        p = self.p
        base = self.hp_candidates(log=log, window=window,
                                  max_cands=max_cands, advance=advance)
        cands, died, f = (base["cands"], base["died"],
                          base["frames"])
        if not cands:
            return None
        if not died:
            # Tier 2: no death happened, no differential available.
            # The top dropper (prior-VERIFIED region) is returned for
            # in-run protection confirmation; never claimed as proven.
            addr = cands[0]
            p.load_state("hpbase")
            self.addrs["hp"] = addr
            self.hp_tier = "tier2_dropper_top"
            self.hp_scale = 200 if p.mem.u16(addr) > 150 else 100
            log(f"[percept] hp TIER2 dropper-top @ {addr:#x} "
                "(baseline lost no life; protection must be confirmed "
                "by in-run death rate)")
            return addr
        p.load_state("hpbase")
        horizon = f + 600
        for addr in cands:
            p.load_state("hpbase")
            v0 = p.mem.u16(addr)
            survived = True
            smax = int(p.mem.u32(self.SCORE_ADDR))
            for i in range(horizon):
                p.core.set_buttons(
                    advance(i) if advance is not None else
                    ({"Y"} if i % 120 < 40 else
                     ({"RIGHT"} if i % 90 < 6 else set())))
                p.core.run_frame()
                p.mem.ram[addr:addr + 2] = (v0 & 0xFF, (v0 >> 8) & 0xFF)
                if i > HP_WARMUP:
                    d, smax = self._death_pulse(p, smax)
                    if d:
                        survived = False
                        break
            log(f"[percept] hp freeze test {addr:#x}: survived="
                f"{survived} horizon={horizon} "
                f"(baseline died at {f})")
            if survived:
                self.addrs["hp"] = addr
                self.hp_tier = "tier1_death_differential"
                self.hp_scale = 200 if v0 > 150 else 100
                log(f"[percept] PLAYER HP confirmed @ {addr:#x} "
                    f"(frozen full={v0}; death-differential survival)")
                p.load_state("hpbase")
                return addr
        p.load_state("hpbase")
        return None

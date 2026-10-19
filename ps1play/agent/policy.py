"""SemanticPolicy — the UNIVERSAL 'what a human does' rule base.

Takes the WorldModel scene + calibrated telemetry and emits button
segments. Rules, in strict human-priority order:

  1. BULLET INCOMING            -> dodge (jump / back off)     [survive]
  2. ENEMY IN RANGE             -> face it, tap-fire (grenade  [kill]
                                   big clusters, like humans)
  3. HEALTH ITEM REACHABLE      -> walk to it and eat it       [heal]
  4. PICKUP ON THE GROUND       -> walk to it, collect         [loot]
  5. NOTHING SEEN               -> advance right, hop obstacles,
                                   keep a human tap-fire rhythm [progress]

Works for any game whose WorldModel found slots; degrades to rule 5
(+ hp/bomb telemetry reflexes) when none are certified yet.
"""
import time


class SemanticPolicy:
    def __init__(self, plugin=None):
        self.plugin = plugin            # fallback telemetry policy
        self.name = "semantic"
        self.last_act = {"t": 0, "act": None}
        self.recover = 0                # post-dodge cooldown frames
        self.hop_cd = 0
        self.burst = 0
        self.stats = {"dodge": 0, "shoot": 0, "heal": 0, "pickup": 0,
                      "advance": 0, "grenade": 0}

    # ----------------------------------------------------------------
    def decide(self, chunk, scene, feat, stall=0):
        """Return [{'frames':n,'btns':set}] covering `chunk` frames."""
        segs = []
        self.recover = max(0, self.recover - chunk)
        self.hop_cd = max(0, self.hop_cd - chunk)

        hp = feat.get("hp")
        bombs = feat.get("bombs")
        events = feat.get("events") or []

        # ---- reflex 0: death/respawn handling --------------------------
        if "death" in events or hp == 0:
            self.recover = 120
            return [{"frames": 20, "btns": {"START"}},
                    {"frames": min(100, chunk - 20), "btns": set()}]

        # ---- 1) DODGE incoming bullets ---------------------------------
        threat = scene.get("threat")
        if threat is not None and self.recover <= 0:
            self.recover = 70
            self.stats["dodge"] += 1
            self._mark("dodge")
            k = min(18, chunk)
            # jump over ground shots; if it aims high, back off instead
            segs.append({"frames": k, "btns": {"B", "RIGHT"}})
            segs.append({"frames": min(chunk - k, 30), "btns": {"Y"}})
            segs.append({"frames": max(0, chunk - k - 30),
                         "btns": {"RIGHT", "Y"}})
            return segs

        # ---- 2) SHOOT the nearest enemy ---------------------------------
        enemy = scene.get("nearest_enemy")
        if enemy is not None and self.recover <= 0:
            dx = enemy["dx"]
            facing_right = dx >= 0
            adx = abs(dx)
            # big cluster + grenades -> grenade it (human behaviour)
            n_enemies = scene.get("n_enemies", 0)
            if n_enemies >= 4 and (bombs or 0) > 2 and adx < 0x1200:
                self.stats["grenade"] += 1
                self._mark("grenade")
                k = min(12, chunk)
                segs.append({"frames": k, "btns": {"A"}})
                segs.append({"frames": max(0, chunk - k),
                             "btns": self._fire(facing_right)})
                return segs
            if adx < 0x1400:               # in effective weapon range
                self.stats["shoot"] += 1
                self._mark("shoot")
                btns = self._fire(facing_right)
                # small side-step while firing (harder to hit, human-like)
                if self.burst % 3 == 2 and chunk > 40:
                    k = min(10, chunk)
                    segs.append({"frames": k, "btns": btns | {"B"}})
                    rest = chunk - k
                else:
                    k = 0
                    rest = chunk
                self.burst += 1
                segs.append({"frames": rest, "btns": btns})
                return segs
            # enemy exists but far -> advance toward it
            btns = {"RIGHT"} if dx > 0 else {"LEFT"}
            segs.append({"frames": chunk, "btns": btns | {"Y"}})
            return segs

        # ---- 3) EAT the health item -------------------------------------
        health = scene.get("nearest_health")
        if health is not None and abs(health["dx"]) < 0x1000:
            self.stats["heal"] += 1
            self._mark("heal")
            btns = {"RIGHT"} if health["dx"] > 0 else {"LEFT"}
            segs.append({"frames": chunk, "btns": btns})
            return segs

        # ---- 4) PICK UP items on the ground (only when very close) ------
        item = scene.get("nearest_item")
        if item is not None and abs(item["dx"]) < 0x280:
            self.stats["pickup"] += 1
            self._mark("pickup")
            btns = {"RIGHT"} if item["dx"] > 0 else {"LEFT"}
            segs.append({"frames": chunk, "btns": btns})
            return segs

        # ---- 5) ADVANCE (with obstacle hop + tap-fire rhythm) -----------
        self.stats["advance"] += 1
        self._mark("advance")
        if stall >= 500:
            k = min(22, chunk)
            return [{"frames": k, "btns": {"RIGHT", "B"}},
                    {"frames": k, "btns": {"RIGHT", "B"}},
                    {"frames": max(0, chunk - 2 * k), "btns": {"RIGHT", "Y"}}]
        if stall > 90 or (self.hop_cd <= 0 and chunk > 120):
            k = min(16, chunk)
            self.hop_cd = 240
            segs.append({"frames": k, "btns": {"RIGHT", "B"}})
            left = chunk - k
        else:
            left = chunk
        self.burst = (self.burst + chunk) % 90
        btns = {"RIGHT", "Y"} if self.burst < 55 else {"RIGHT"}
        segs.append({"frames": left, "btns": btns})
        return segs

    # ----------------------------------------------------------------
    def _fire(self, facing_right=True):
        b = {"RIGHT"} if facing_right else {"LEFT"}
        b.add("Y")
        return b

    def _mark(self, act):
        self.last_act = {"t": time.strftime("%H:%M:%S"), "act": act}

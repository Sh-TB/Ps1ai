#!/usr/bin/env python3
"""r76_battery_plan.py — generate THE 100-TEST SAVESTATE BATTERY PLAN
(the owner directive: freeze the game at the death point, load from
there, and test — each test exactly once; 100 tests to pass the
stage).

Blocks (all restore-only after ONE boot):
  A  THE DEATH-DODGE MATRIX (55) — CP_C_PREDEATH (f1820, 64f before
     the r74b1/r75b1 death at f1884): hold-offset x action grid.
  B  THE MARCHER/CORRIDOR TESTS (20) — CP_B_PREBARR (f1495, before
     the chaser marchers arrive): the walk-lob alignment (the R76
     feed-clearing lever, measured not guessed), the fire barrage,
     the hop, the controls.
  C  THE CONNECT GEOMETRY (12) — CP_A2_THROW (f1378, 2f before the
     proven 229 throw): the throw offset d in [-4..+4] -> the exact
     connect-window width on the head's 259-grid.
  D  THE DEATH MYSTERY (10) — CP_D_DEATHM1 (f1878, 6f before the
     death): the last-microsecond dodges + the killer scan.
  E  THE CONTROLS (3) — the determinism replays.

Output: scripts/r76_battery_plan.json (committed; the runner
executes the list in order, one JSONL row per test).
"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "r76_battery_plan.json")
ACTIONS_A = ("IDLE", "WALK", "BACK", "FIRE", "HOP")
OFFS_A = (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)

tests = []
# ---- Block A: the death-dodge matrix (55)
n = 0
for o in OFFS_A:
    for a in ACTIONS_A:
        n += 1
        tests.append({
            "id": f"A{n:02d}", "block": "A",
            "cp": "CP_C_PREDEATH",
            "title": f"hold {a} from f1820+{o}",
            "inj": {"idle": o, "hold": a, "horizon": 90},
            "question": "does the player survive the f1884 death "
                        "window? what is the death frame otherwise?",
        })

# ---- Block B: the marcher/corridor tests (20)
B = [
    ("walk RIGHT 10f, lob", {"walk": 10, "lob": True, "obs": 150}),
    ("walk RIGHT 20f, lob", {"walk": 20, "lob": True, "obs": 150}),
    ("walk RIGHT 30f, lob", {"walk": 30, "lob": True, "obs": 150}),
    ("walk RIGHT 40f, lob", {"walk": 40, "lob": True, "obs": 150}),
    ("walk RIGHT 62f, lob (the ~999.5 alignment)", {"walk": 62, "lob": True, "obs": 150}),
    ("walk RIGHT 80f, lob", {"walk": 80, "lob": True, "obs": 150}),
    ("walk 20f, lob, walk BACK 20f, lob", {"walk": 20, "lob": True, "back": 20, "lob2": True, "obs": 150}),
    ("walk 40f, lob, walk BACK 40f, lob", {"walk": 40, "lob": True, "back": 40, "lob2": True, "obs": 150}),
    ("walk 62f, lob, walk BACK 62f, lob", {"walk": 62, "lob": True, "back": 62, "lob2": True, "obs": 150}),
    ("FIRE barrage 300f", {"fire": 300, "obs": 60}),
    ("FIRE barrage 600f", {"fire": 600, "obs": 60}),
    ("IDLE 400f (the barricade timeline)", {"idle": 400}),
    ("lob at the record posture (the C2 check)", {"lob": True, "obs": 150}),
    ("HOP forward at the barricade", {"hop": True, "obs": 150}),
    ("walk 62f, HOP, lob", {"walk": 62, "hop": True, "lob": True, "obs": 150}),
    ("walk 40f, BACK, lob", {"walk": 40, "back": 40, "lob": True, "obs": 150}),
    ("lob x2 (the double lob at the posture)", {"lob": True, "lob2": True, "obs": 150}),
    ("walk RIGHT 100f, lob", {"walk": 100, "lob": True, "obs": 150}),
    ("walk RIGHT 130f, lob", {"walk": 130, "lob": True, "obs": 150}),
    ("walk 20f, IDLE 200f (the marcher arrival record)", {"walk": 20, "idle": 200}),
]
for i, (title, inj) in enumerate(B, 1):
    tests.append({"id": f"B{i:02d}", "block": "B", "cp": "CP_B_PREBARR",
                  "title": title, "inj": inj,
                  "question": "do the marchers die / does the corridor "
                              "clear / where does the lob land?"})

# ---- Block C: the connect geometry (12)
# CP_A2_THROW = f1375 (fight_f 224; the decision frames run from
# 225) — the lob at fight_f 229+d -> idle = 5+d frames
for d in (-4, -3, -2, -1, 0, 1, 2, 3, 4):
    tests.append({
        "id": f"C{d+5:02d}", "block": "C", "cp": "CP_A2_THROW",
        "title": f"throw at fight_f {229}+{d:+d} (the land "
                 f"{259 + d:+d}f)",
        "inj": {"idle": 5 + d, "lob": True, "obs": 60},
        "question": "the exact connect-window width on the head's "
                    "259-grid",
    })
tests.append({"id": "C10", "block": "C", "cp": "CP_A2_THROW",
              "title": "IDLE control (no throw)",
              "inj": {"idle": 100}, "question": "no a4 change expected"})
tests.append({"id": "C11", "block": "C", "cp": "CP_A2_THROW",
              "title": "the 0-offset repeat (the determinism x2)",
              "inj": {"idle": 5, "lob": True, "obs": 60},
              "question": "the connect reproduces byte-exact"})
tests.append({"id": "C12", "block": "C", "cp": "CP_A2_THROW",
              "title": "the grenade readiness (an off-grid probe at "
                       "fight_f 268)",
              "inj": {"idle": 44, "lob": True, "obs": 60},
              "question": "the cooldown state does not block"})

# ---- Block D: the death mystery (10)
D = [
    ("IDLE (the exact death-frame record)", {"idle": 120}),
    ("FIRE at the death instant", {"fire": 120}),
    ("WALK RIGHT at the death instant", {"walk": 120}),
    ("BACK LEFT at the death instant", {"back": 120}),
    ("HOP at the death instant", {"hop": True, "idle": 120}),
    ("CROUCH DOWN at the death instant", {"down": 120}),
    ("GRENADE at the death instant", {"lob": True, "idle": 120}),
    ("IDLE + the entity scan every frame", {"idle": 120, "scan": True}),
    ("CROUCH 30f then IDLE", {"down": 30, "idle": 90}),
    ("HOP with B (the back-hop)", {"bhop": True, "idle": 120}),
]
for i, (title, inj) in enumerate(D, 1):
    tests.append({"id": f"D{i:02d}", "block": "D", "cp": "CP_D_DEATHM1",
                  "title": title, "inj": inj,
                  "question": "the killer's identity + the last-frame "
                              "dodge"})

# ---- Block E: the controls (3)
tests.append({"id": "E01", "block": "E", "cp": "CP_C_PREDEATH",
              "title": "IDLE 120 (the death determinism x1)",
              "inj": {"idle": 120}})
tests.append({"id": "E02", "block": "E", "cp": "CP_C_PREDEATH",
              "title": "IDLE 120 (the death determinism x2)",
              "inj": {"idle": 120}})
tests.append({"id": "E03", "block": "E", "cp": "CP_B_PREBARR",
              "title": "IDLE 120 (the pre-barricade control)",
              "inj": {"idle": 120}})

plan = {
    "round": "R76",
    "directive": "the owner: freeze at the death point, load, test — "
                 "100 tests, each exactly once",
    "boot_budget": "ONE product boot for the route + the checkpoint "
                   "harvest; the battery itself is restore-only "
                   "(ZERO boots) — the r66/r67 restore-only precedent",
    "n_tests": len(tests),
    "checkpoints": {
        "CP_A2_THROW": "f1375 (fight_f 224; the decision frames "
                       "225+ — 4f before the proven 229 throw)",
        "CP_B_PREBARR": "f1495 (before the marchers arrive ~f1515)",
        "CP_C_PREDEATH": "f1820 (64f before the death at f1884)",
        "CP_D_DEATHM1": "f1878 (6f before the death)",
    },
    "tests": tests,
}
assert len(tests) == 100, len(tests)
with open(OUT, "w") as f:
    json.dump(plan, f, indent=1)
print(f"plan written: {len(tests)} tests -> {OUT}")
for b in ("A", "B", "C", "D", "E"):
    print(" ", b, sum(1 for t in tests if t["block"] == b))

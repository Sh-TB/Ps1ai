#!/usr/bin/env python3
"""post_issue6_round15.py — Issue #6 round-15 report."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO

BODY = """## Round 15 — first tiny-game PLAYING+WINNING in one round (FlappyBirdPSX), plus the tiny→big transfer playbook

### 1. The deliverable: real play, the game's own win state, one session

**GIF (725 frames @ 20 fps, complete run): https://n.uguu.se/PGbBVuMY.gif**

[FlappyBirdPSX](https://github.com/IcePanorama/FlappyBirdPSX) (Unlicense) — **5th accepted game**:

| honest status | evidence |
|---|---|
| RUNNING | direct boot (the disc SHIPS license sectors — decision-tree route 1, zero patching); "Get Ready" at ~f600 |
| PLAYING | 60 Hz closed-loop vision servo: bird centroid + pipe-gap detection + edge-correct pulses; every flap observed in the pad buffer |
| WINNING | **10 pipe passes**, each anchored by the pipe `pos.x` (RAM i16, pool slot 1) crossing the game's own scoring gate (`x < -1152` world, from `s_in_green_area`); the drawn score counter reads **"10"** at the win frame with the bird alive ([WIN_FRAME.png](../blob/main/docs/evidence/round15/WIN_FRAME.png)) |

The run: 2,176 frames — **1 real death** (pipe clip, pre-death frame ring logged) → START restart (the game's own flow) → 10 passes with 69 flaps.

### 2. What it took (four dead runs, each a reusable lesson)

1. **Controller truth table** ([probed from the pad buffer](../blob/main/docs/tiny_games_playbook.md)): ps1play's `X` delivers PSX **TRIANGLE** (mirror 0xEFFF) — the flap (CROSS) silently never fired. Flap = `B` (JP_B → CROSS, 0xBFFF).
2. **Edge-triggered input**: source `get_command` keeps `i32_last_padd` — holding X = ONE flap. Every flap is a 2-frame pulse + ≥3-frame release.
3. **Collision geometry read from RAM pools** (PhysicsCompnt stride 12, ColShape `{pid,w,h,ptr}`): top box [1,105], bottom [175,201] for a gap at 140 — **the boxes match the visible pipes exactly**; the author's "phantom collision" FIXME does not fire on the shipped build. Deaths were servo geometry.
4. **Servo from the measured impulse**: one flap = 36 px rise over 8 f → flap at `gap_center+14` (apex −22) keeps the 20 px bird inside the 70 px gap; the earlier +2 threshold overshot the gap top by 3.5 px and died.
5. **Scene-color discipline**: pale bush green matched the pipe mask (clipped low gaps); shaded pipe columns fragmented the band (1-px dilation); the game-over box is **tan, not white**. All three measured from pixels, not assumed.

### 3. The transfer layer (the point of tiny games) — [`docs/tiny_games_playbook.md`](../blob/main/docs/tiny_games_playbook.md)

- Honest **RUNNING / PLAYING / WINNING** taxonomy with required evidence per rung (r14's retraction is the enforcement case).
- **Boot-route decision tree** (license-on-disc → license-patch → ≤32 KB EXE container → >32 KB blocked, levers).
- **Sensor ladder**: source/map symbols → whole-RAM delta pinning during real play → vision. New measured lesson: the pipe `pos.x` is an i16 at `base+2` — **an i32 scan is structurally blind to it**.
- **Measured speedup**: rounds from "new game" to honest real play — hello_pong **4** (r11→r14, incl. the retraction), Tetrade 4, **FlappyBirdPSX 1**.
- Big-game application queue: MSX MISSION SELECT (r12 lever) = sensor-ladder rung 2 + pulse discipline on menu taps; Doukutsu menu navigation = the same servo problem; psxBreakout stays pending on boot route 4 (timeboxed, per the playbook).

### 4. Housekeeping

- `data/homebrew/manifest.json`: flappybirdpsx ACCEPTED (sha-verified ISO, `round15_addendum`), accepted = 5.
- Evidence: `scratch/round15_flappy/{boot,sensors,inputprobe,colprobe,sweep,play}` (local), `docs/evidence/round15/` (committed), tools `scripts/r15_flappy_*.py` (6 scripts).
- Suite: **548 passed + 1 xfailed** (unchanged). HEAD `9ae11f7` (pushed via the Git Data API as `4ab14db4d20912ee233c79fbeaab85efed1b7a46`). No game bytes committed."""

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY})
print("issue #6 comment:", s, d.get("id"), d.get("html_url"))

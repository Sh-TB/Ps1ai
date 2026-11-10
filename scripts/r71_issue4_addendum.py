#!/usr/bin/env python3
"""r71_issue4_addendum.py — the R71 product-path addendum to issue #4
(the R68/R69/R70 precedent), read back byte-identical."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R71 product-path addendum (the Metal Slug X truck campaign, the chip-connect kill schedule) — the deterministic Mission-1 policy v1.9.0 (K1) + the adapter 0.5.2.** Push [`d9f01ad`](https://github.com/Sh-TB/Ps1ai/commit/d9f01ad13926) · the full round report on #9 · evidence `truck_evidence/r71/`.

**What changed on the product path this round:**

- **K1 the aimed cooldown chip-fire shipped (policy 1.9.0):** during the grenade cooldown / the phase-hold at the record posture, the policy turns toward the truck and fires on the 12f cadence — ONLY when the corridor to the truck is clear (the C2 bullet-line guard) and no escort stands. The grenade keeps grid priority (the chip-fire never delays a phase throw). **CONFIRMED in-game (boot 1): the player's own bullets reach the parked truck — 3 chips measured under the chip-fire rules.**
- **The a4-aware liveness filter shipped (adapter 0.5.2):** the observation now drops the DEAD unknown rows (the boot-1 ghost blocker `0x6730` a4=0 that withheld the k=0 window while dead) and PACKS the LIVE chaser-throw rows the `h>64` drop used to hide (the invisible thief stack `0xb4e4/0xabdc` that stole the phase-exact k=1 lob). The R66 projectile guard is preserved verbatim.
- **Boot 3 (the falsification arm, disclosed pre-run): THE CONNECT LANDED ON THE PHASE GRID** — a4 280 -> 180 at the land = freeze + 506 ± 2f (178 + 164×2, tolerance 2f), thrown at dx -133.5 EXACT from the record posture. The phase law's local validity is confirmed at k=2.
- **THE PHASE LAW IS STREAM-DEPENDENT (the honest falsification):** the same boot's k=0/k=1 throws (ON the grid) missed; the chip-fire stream never connected (0/2); the r69b volley connected 2/7. The R67 cadence law generalizes: the input stream is part of the deterministic trajectory — the R72 lever is the volley+phase hybrid (the gre40 cadence gated by the phase tolerance).

**The measured round outcome (honest):** no truck kill yet — the best boot reached **a4 160** (1 connect + 5 chips from 300) and the score record moved to **2400** (boot 1, +300 over the R70 best). The chips flow reliably (8-13 per boot, the aimed + the stray paths); the connect is the named bottleneck.

The corridor-feed map (offline): the walker spawns are POSITION-keyed (the world band ~969-1180), and the land-window occupancy is stream-dependent — the idle-hold stream kept all four grid lands clean (boot 3), the chip-fire stream left two occupied (boot 2, the guard correctly withheld both).

The experiment track (restore-only) delivered the watchpoint pass: the frontier rebuild byte-exact 8-for-8 (px 1254.8), the +500 captured at the watchpoint (tap 6 verbatim, the pay-frame law 3/3), the payment clusters mapped (the stack band `0x1FFD00-0x1FFF00` + the entity rows `0xCA6xx-0xCBDxx` + the HUD neighborhood `0xEE3xx-0xEF4xx`); the payment-writer PC is NOT readable on beetle (the tool limit, disclosed) — the follow-up is the PCSX-Redux debugger oracle.

Suite 924 passed + 10 skipped + 1 xfailed (21 new R71 tests; zero weakened). Zero RAM writes in the product track, legal inputs only, no training, no runtime LLM."""

s, d = req(f"/repos/{REPO}/issues/4/comments", "POST", {"body": BODY})
print("HTTP", s, "comment id:", d.get("id"))
if s == 201:
    s2, comments = req(f"/repos/{REPO}/issues/4/comments?per_page=100")
    mine = [c for c in comments if c["id"] == d["id"]]
    print("read back byte-identical:",
          bool(mine) and mine[0]["body"] == BODY)

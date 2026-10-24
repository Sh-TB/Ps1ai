#!/usr/bin/env python3
"""post_session5_reports.py — session-5 batch reports on the existing
Issues #5 (MSX grenade-vs-truck campaign) and #6 (small-games batch).
Updates only — no new issues (mission rule)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api                                                     # noqa

B5 = """## Session 5 — the owed grenade-vs-armored-truck live run DELIVERED (4 arms) + regression (2026-10-24)

**Baseline:** HEAD `b044142` -> **`18a56b1`** (pushed, API-verified). Suite **400 passed + 1 xfailed** (11 new offline tests). Disc/workspace/evidence artifacts local-only.

### The owed run: grenade vs the armored truck (slot 14, hp 254, Y-immune)

`scripts/msx_grenade_truck.py` — stand-ground lob campaign at the truck encounter from `chopper_ckpt`, per-chunk JSONL (px, hp pair, score, grenade counter 0xEDCF4, scan, lobs), death/flags endpoint accounting:

| Arm | Stock | Result |
|---|---|---|
| `gtruck1` | honest 10 | **truck hp 254 -> 207** (grenades DO damage armor; Y was 254->254), score 0->**700** (6 kill-events >=100), counter 10->0 VERIFIED, player survives 40 chunks |
| `gtruck2` | honest 10 | **bit-identical repro of gtruck1** (same hp 207 / score 700 / damage trace) |
| `gtruck3_top50` | DISCLOSED top-up 50 | identical outcome — extra grenades all miss once the truck closes: **lob arc sails over at close range**, damage freezes at 207 |
| `gtruck4_retreat` | top-up 50 + retreat-lob | died c31 in the rear mortar/chopper zone with LESS truck damage (288) — retreating re-opens the rear kill zones |

**Verdict (honest):** the grenade is the confirmed anti-armor weapon (damage reproduced 3x, counter-verified), but the **full kill is BLOCKED by geometry** — the clamp funnels the player into the ram one-shot (−291) while retreat re-opens the rear zones. D2 stays PARTIAL with a much sharper boundary. Ledger + final-report addendum updated.

### Regression

`policy_pass8` re-verified the round-3 combat behaviours live: engage 5 / front_engage 300 / dodge 5 / rear_check 2 / rear_resolved 1 / advance_silent 14-15; same 27-chunk clamp death at px 1164 (D7 blocker unchanged).

### Next experiments named
1. Point-blank UP-lob vs the truck (arc over the ram window) — the one geometry not yet tried.
2. D7 pin state-machine handlers (0x80032d28 / 0x800b83e0) trace.
"""

B6 = """## Session 5 — small-games batch: 2nd COMPLETE PLUGIN (PSXMC) + 5/5 sweep + new <50MB fetch (2026-10-24)

**Baseline:** HEAD `18a56b1`. Suite **400 passed + 1 xfailed**.

### Boot sweep (owner directive: "test the small games we have")
5/5 BOOTED with adaptive pad-mirror settle (`scripts/smallgames_sweep.py`): Tetrade, PSX-Minecraft, Nortis, Poy Poy, Trap Gunner.

### PSX-Minecraft — COMPLETE PLUGIN #2 (`PSXMCPlayPlugin`, after Tetrade)
- Source-first: MIT EngineersBox/PSX-Minecraft structs + PSXMC.map symbols (`player` 0x3C608, `world` 0x3C61C, `time_ms` 0x3C5A0).
- Live-verified by input causality (probe series `scripts/psxmc_probe*.py`): pos/vel/pitch/yaw/fwd/strafe offsets, flags bits (on_ground/jumping/crouching), health=20/armour=0/air=20 at spawn.
- 250-chunk live session (`scripts/run_psxmc_play.py`): **232 verified move bursts** (live displacement per burst), out-and-back patrol engineered around TWO discovered infdev hazards: (a) the fall handler is UNIMPLEMENTED — >7 blocks from spawn = game halt (observed 2x); (b) the R2 dig can halt the game (suspected `worldGetChunk` NULL-deref on the breaking-state transition) — dig is gated to a bounded final experiment. Health 20/air 20 at BUDGET_END (sandbox: no game-over exists — nothing claimed beyond verified events).

### Pad-class truth (decisive, probe5 matrix at the game's own `input` buffer)
The beetle DIGITAL pad (id 0x41) delivers **all 16 button bits incl. L2/R2/L3/R3**. The host gained a backward-compatible opt-in `INPUT_DEVICE` capability (default JOYPAD unchanged), but beetle 0.9.44.1's ANALOG mode is input-DEAD (A/B: digital d_z 844038 vs analog all-zero) — no plugin uses it today.

### The rest of the batch
- **Poy Poy**: `PoyPoyPlugin` — menu path title->START->MODE SELECT data-frozen, cursor nav verified; match-entry confirm NOT identified (X/O/START/SQ/TR tested; X/O/START bounce to title — idle-timeout suspected). Honest BLOCKED-by-discovery.
- **Trap Gunner**: menu walk -> TUTORIAL MOVIE submenu reached (main-game entry unmapped).
- **Nortis**: local autoplay (188 rule inputs, 67 field-active chunks, score-region capture) — license-BLOCKED for distribution unchanged.
- **NEW <50 MB fetch**: FFT6 — World of Ruin (hack) 29,734,169 B sha256 `6fc04405…` — boots (license sectors intact, BOOT=SCUS_942.21), pad live, X/LEFT causal (7.1) — boot-verified candidate, RAM mapping pending.

All disc binaries/evidence local-only, never committed. Ranking doc session-5 table + ledger labels updated.
"""

for issue, body in ((5, B5), (6, B6)):
    st, r = gh_api.req(f"/repos/{gh_api.REPO}/issues/{issue}/comments",
                       method="POST", payload={"body": body})
    print(issue, st, r.get("html_url", r)[:80])

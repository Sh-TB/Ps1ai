#!/usr/bin/env python3
"""r71_capsule_update.py — append the R71 events to the MSX capsule
and set next_experiment = R72.

The R71 round (the capsule lever executed: the chip-connect kill
schedule + the corridor-feed map + the restore-only watchpoint pass).
THREE consolidated events with provenance, each read back verbatim
after the write (the R37+ discipline).
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
CAP = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")

EVENTS = [
    {
        "what": (
            "R71 THE CHIP-CONNECT KILL SCHEDULE (the capsule lever, "
            "the product track; policy 1.8.5 -> 1.9.0 K1, adapter "
            "0.5.1 -> 0.5.2; 3 product boots, the r71 ledger "
            "disclosed pre-run cap 3, 3/3 spent).  K1 SHIPPED: the "
            "aimed cooldown chip-fire at the record posture — runs "
            "ONLY inside the corridor-cleared throw branch (the C2 "
            "bullet-line guard; the v1.6.1 bullets-eaten failure "
            "mode is what the guard removes), no escort precedence, "
            "the grenade keeps grid priority, the FIRE_COOLDOWN 12f "
            "cadence.  BOOT 1 (v1.9.0 on the 0.5.1 adapter): 8 chips "
            "a4 300 -> 220 (3 under the aimed chip-fire rules — THE "
            "AIMED CHIP PATH CONFIRMED, the R70 escort-stray path "
            "plus the player's own fire both reach the parked "
            "truck); the k=0 grid window WITHHELD by the GHOST "
            "BLOCKER (slot23 st 0x6730, x 995.0, h 64, a4 0 — an "
            "unknown dead-walk state NOT in CORPSE_ST blocked the "
            "corridor while dead, the R66 predicate violated by the "
            "observation); the phase-exact k=1 lob (f1123, dx "
            "-133.5) STOLEN by the INVISIBLE THIEF STACK at x "
            "1062.3 (0xb4e4 a4 30 h 102 / 0xabdc a4 300 h 205 / "
            "0xb4e4 a4 30 h 142 — the h > GROUND_HEIGHT drop hid "
            "the LIVE rows); the push pinned the player at px "
            "1105.8 (the approach BACK cannot beat the scroll pin); "
            "death f1298, score 2400 = THE NEW RECORD (+300 over "
            "the R70 best).  BOOT 2 (adapter 0.5.2): the ghost gone "
            "(the k=0 corridor CLEAN, the throw FIRED at fight_f "
            "148, dx -133.5) and MISSED; 13 chips a4 300 -> 170; "
            "the k=1 correctly WITHHELD (the thief now visible in "
            "the observation); death f1714, score 1800.  BOOT 3 "
            "(the ONE-VARIABLE FALSIFICATION ARM, disclosed "
            "pre-run: TRUCK_CHIP_FIRE=False = the exact v1.8.5 "
            "idle-hold semantics on the v0.5.2 adapter): ALL THREE "
            "grid throws fired clean (the corridor stayed clean "
            "through k=2) and THE CONNECT LANDED — a4 280 -> 180 at "
            "f1659, the land = freeze + 506 +- 2f ON THE PHASE GRID "
            "(178 + 164*2 = 506, the tolerance 2f) — the phase "
            "law's LOCAL validity confirmed at k=2; but the k=0/k=1 "
            "throws (freeze+178/342, ON the grid) MISSED — THE "
            "PHASE LAW IS STREAM-DEPENDENT: it was verified on the "
            "v1.7.1 gre40 volley stream (2/7 connects) and does "
            "NOT transfer verbatim to the v1.9.0 chip-fire stream "
            "or the v0.5.2-visibility stream (the R67 cadence law "
            "generalized to the meta level: the input stream is "
            "part of the deterministic trajectory).  THE ROUND "
            "OUTCOME (honest): NO truck kill — the best boot ran "
            "1 connect + 5 chips (a4 300 -> 160 at the death); the "
            "chips flow reliably (8/13 per boot, both the aimed "
            "and the stray paths); the connect remains the "
            "bottleneck (1/3 on-grid in the idle-hold stream, 0/2 "
            "in the chip-fire stream).  Evidence: truck_evidence/"
            "r71/r71_chip_probe.jsonl (boot 3) + r71_chip_probe_"
            "boot2.jsonl (boot 2; the boot-1 JSONL was overwritten "
            "by the boot-3 run — the same output path, disclosed; "
            "the boot-1 verdicts live in the A4 PNG series and the "
            "round report)."
        ),
        "status": "OBSERVED",
        "round": "R71",
        "provenance": {
            "source": ("scripts/r71_chip_probe.py + the policy "
                       "1.9.0 K1 + the adapter 0.5.2 + the boot-3 "
                       "falsification arm (R71_CHIP_FIRE=0)"),
            "evidence": ("data/games/SLUS-01212/truck_evidence/r71/"
                         "r71_chip_probe.jsonl + "
                         "r71_chip_probe_boot2.jsonl"),
            "boots": 3,
        },
    },
    {
        "what": (
            "R71 THE CORRIDOR-FEED MAP (the capsule lever, the "
            "offline analysis over the preserved product JSONLs — "
            "no boots): the walker spawn zone is "
            "POSITION-KEYED, not frame-keyed — the sanitized spawn "
            "x values concentrate in the world band ~969-1180 "
            "(the corridor + the rear zone; the posture is 1071) "
            "across boots 2-3, with no fixed frame grid; the "
            "pre-window hygiene must stay position-keyed (the "
            "escort rule), not frame-keyed.  The corridor "
            "occupancy at the grid lands is STREAM-DEPENDENT: the "
            "chip-fire stream left the k=1/k=2 lands OCCUPIED "
            "(the guard correctly withheld both throws, boot 2) "
            "while the idle-hold stream kept ALL FOUR lands clean "
            "(boot 3, all throws fired).  Evidence: truck_evidence/"
            "r71/r71_corridor_feed_map.json."
        ),
        "status": "OBSERVED",
        "round": "R71",
        "provenance": {
            "source": "scripts/r71_corridor_feed_map.py (offline)",
            "evidence": ("data/games/SLUS-01212/truck_evidence/r71/"
                         "r71_corridor_feed_map.json"),
            "boots": 0,
        },
    },
    {
        "what": (
            "R71 THE WATCHPOINT PASS (the capsule lever, the "
            "experiment track, restore-only; the ledger cap "
            "2 -> 4 by two DISCLOSED amendments — boot 3 was a "
            "no-op env-var tool bug, honestly labeled).  Stage 1: "
            "the frontier rebuild BYTE-EXACT AGAIN (the R47/R66/"
            "R68 recipe verbatim: frontier_px 1254.8 = the record "
            "EXACTLY, the determinism dividend now 8-for-8).  "
            "Stage 2: the verbatim R66 pass B tap replay with the "
            "WATCHPOINT telemetry patched at the DISCLOSED R52 "
            "seam (R50T.frame_walk): THE +500 CAPTURED AT THE "
            "WATCHPOINT — tap 6 verbatim (slot16, st_pre 0x1e38, "
            "dx +20.3, score 7702 -> 8202) at flight TAIL f1 — the "
            "pay-frame law now 3/3.  THE PAYMENT CLUSTERS (the "
            "co-changing RAM regions at the pay frames): the "
            "+1000 cluster COMPLETE (1034 B, 200 regions) INCLUDING "
            "the score-word region 0xEE318-0xEE31A (2 B); the +500 "
            "cluster (2695 B churn, 200 regions) had its 2-B "
            "score-word region cut by the top-N cap (the tool "
            "limit, disclosed — the delta itself is arithmetic: "
            "2 bytes).  THE WRITER FOOTPRINT: both payments churn "
            "the STACK band 0x1FFD00-0x1FFF00 (the call frames), "
            "the ENTITY TABLE rows 0xCA6xx-0xCBDxx and the "
            "score/HUD neighborhood 0xEE3xx-0xEF4xx — consistent "
            "with the R69 narrowed writer set (the overlay damage "
            "tail executing through the credit tables).  THE PC "
            "QUESTION ANSWERED HONESTLY: a literal payment-writer "
            "PC is NOT readable on the beetle/libretro stack (no "
            "CPU state export — the tool limit); the store site "
            "STAYS NARROWED (the R69 static verdict), the runtime "
            "pass pins the payment timeline + the clusters, and "
            "the follow-up is the CPU-instrumented oracle (the "
            "PCSX-Redux debugger, the R64 tools matrix).  The "
            "tap-6 replay reproduced BYTE-IDENTICAL across three "
            "boots (the same frontier state + the verbatim "
            "protocol).  Evidence: truck_evidence/r71/r71wp_"
            "stage2.jsonl (boot 2, top-24) + r71wpc_stage2.jsonl "
            "(boot 4, top-200)."
        ),
        "status": "OBSERVED",
        "round": "R71",
        "provenance": {
            "source": ("scripts/r71_watchpoint_pass.py (the r66t1 "
                       "code path verbatim + the disclosed R52 "
                       "seam patch)"),
            "evidence": ("data/games/SLUS-01212/truck_evidence/r71/"
                         "r71wp_stage2.jsonl + r71wpc_stage2.jsonl"),
            "boots": 4,
        },
    },
]

NEXT = {
    "id": "R72",
    "budget": (
        "product boots + probes are the separate gameplay track; "
        "the experiment track stays restore-only arms from the r66 "
        "frontiers (the rebuild is byte-exact 8-for-8)"),
    "hypothesis": (
        "the CONNECT is the kill bottleneck (1/3 on-grid in the "
        "idle-hold stream, 0/2 in the chip-fire stream, 2/7 in the "
        "r69b volley stream — the phase law is STREAM-DEPENDENT). "
        "Two evidence-armed leads: (1) PRODUCT - the volley+phase "
        "HYBRID: the gre40 cadence gated by the phase tolerance "
        "(the throw at every 40f cadence frame whose land sits "
        "within +-2f of ANY grid point) — the r69b evidence says "
        "the cadence volume pays (7 throws, 2 connects); the "
        "boot-3 evidence says the on-grid lands connect (1/3) — "
        "the hybrid maximizes on-grid landings per window; "
        "(2) SOURCE-FIRST - the watchpoint clusters: the stack "
        "band 0x1FFD00-0x1FFF00 + the entity rows 0xCA6xx-0xCBDxx "
        "+ the HUD neighborhood 0xEE3xx-0xEF4xx — the Ghidra xref "
        "on those cluster addresses closes the R69 narrowed set "
        "to the exact store (the offline decode, zero boots); "
        "(3) the zero-overlap test re-runs on any new +500 "
        "capture"),
    "method": (
        "product-path: the v1.9.0 policy with the K1 arm "
        "re-selected by the boot-3 evidence (the idle-hold stream "
        "connects; the chip-fire stream does not — the K1 arm "
        "stays available as the chip-damage supplement AFTER the "
        "connect mechanism is solved); experiment-track: the "
        "cluster xref is offline; the watchpoint hardware (the "
        "frontier states) stays on disk"),
    "m2_gate_note": (
        "unchanged - interactive M2 entry stays gated on a clean "
        "(deaths=0, no-restart) deep resolve posture"),
}


def main():
    with open(CAP) as f:
        cap = json.load(f)
    before = len(cap["events"])
    cap["events"].extend(EVENTS)
    cap["next_experiment"] = NEXT
    meta = cap.setdefault("meta", {})
    meta["last_updated"] = time.strftime("%FT%TZ", time.gmtime())
    meta["last_commit_note"] = (
        "R71: the chip-connect kill schedule executed — K1 the "
        "aimed cooldown chip-fire shipped (the aimed chip path "
        "CONFIRMED: the player's own bullets reach the parked "
        "truck), the adapter 0.5.2 a4-aware liveness filter (the "
        "ghost blocker gone, the invisible thief visible), the "
        "boot-3 falsification arm connected ON GRID (a4 280->180 "
        "at freeze+506+-2f = the phase law's local validity at "
        "k=2) and falsified its stream-independence (0/2 for "
        "k=0/k=1; the law is STREAM-DEPENDENT — the R67 cadence "
        "law generalized), the corridor-feed map (the spawns "
        "position-keyed x ~969-1180; the land occupancy "
        "stream-dependent), the watchpoint pass delivered (the "
        "+500 at tail f1 3/3; the payment clusters: the stack "
        "churn + the entity rows + the HUD neighborhood; the PC "
        "not readable on beetle — the honest tool limit, the "
        "follow-up = the PCSX-Redux oracle); NO kill (the best "
        "1 connect + 5 chips, a4 160 at death; the score record "
        "2400).  The R72 = the volley+phase hybrid + the cluster "
        "xref.  Mission 1 OPEN.")
    with open(CAP, "w") as f:
        json.dump(cap, f, indent=1, ensure_ascii=False)
    # read back verbatim
    with open(CAP) as f:
        back = json.load(f)
    assert len(back["events"]) == before + len(EVENTS), \
        "event count mismatch"
    for i, e in enumerate(EVENTS):
        assert back["events"][before + i] == e, f"event {i} mismatch"
    assert back["next_experiment"] == NEXT
    print(f"capsule updated: +{len(EVENTS)} events "
          f"({before} -> {len(back['events'])}), "
          f"next_experiment={NEXT['id']}, "
          f"bytes={os.path.getsize(CAP)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

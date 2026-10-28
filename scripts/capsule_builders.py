#!/usr/bin/env python3
"""capsule_builders.py — build knowledge capsules from LOCAL VERIFIED
EVIDENCE ONLY (manifest + worklog + issue reports + r37 probe).

Every entry carries provenance + status. Nothing is invented here; a fact
not present in the evidence base simply does not appear.
"""
import hashlib
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.knowledge import Capsule  # noqa: E402

DATA = os.path.join(REPO, "data")
MSX_BIN = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
RECOMP_TSV = os.path.join(DATA, "knowledge/msx/external/"
                          "msxrecomp_functions.tsv")
RECOMP_EDGES = os.path.join(DATA, "knowledge/msx/external/"
                            "msxrecomp_edges.json")

W = lambda doc: {"source": "worklog+docs " + doc, "evidence": doc}


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _cap(identity):
    return Capsule.new(identity)


# ---------------------------------------------------------------------------
def build_buzzybee():
    c = _cap({"game_id": "buzzybee", "title": "BuzzyBee",
              "serial": "homebrew (PS-EXE wrap)", "region": "NTSC (patched)",
              "exe_sha256": "9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac8"
                            "3f5f0dda95c909a8ba",
              "fingerprint": {"license": "MIT (in-header, flagged)",
                              "repo": "github.com/NDR008/BuzzyBee"}})
    c["prior_art"] = [
        {"name": "NDR008/BuzzyBee", "kind": "upstream repo (code, MIT)",
         "url": "https://github.com/NDR008/BuzzyBee",
         "license": "MIT header only — flagged", "inspected": True,
         "classification": "DIRECTLY_REUSABLE (source-assisted)"}]
    P = {"source": "upstream map + r23t2_buzzybee_boot4.py live probe",
         "evidence": "scratch/r23/buzzybee/boot4_log.json (rollback-"
                     "affected; facts re-affirmed r34/r35)"}
    for va, w, role in ((0x80058810, 4, "screen_width"),
                        (0x80058814, 4, "screen_height"),
                        (0x8005881C, 4, "input_pad"),
                        (0x80058820, 4, "input_trig"),
                        (0x80058824, 4, "input_held"),
                        (0x80058830, 4, "game_state"),
                        (0x80058838, 4, "best_score"),
                        (0x8005883C, 4, "score"),
                        (0x8005EDC0, 4, "player_ptr/struct"),
                        (0x8005EF48, 4, "player_health"),
                        (0x8005F548, 4, "player_timer"),
                        (0x8005EB7C, 4, "wasp_entity"),
                        (0x8005EBA0, 4, "flowers_array (stride 0x24)"),
                        (0x8005F55C, 4, "rocks_array (stride 0x24)")):
        c.add_field(va, w, role, "VERIFIED",
                    dict(P, evidence=P["evidence"] + " + r35 entity trace"))
    c["controls"] = [
        {"button": "B (CROSS)", "effect": "flap tap (y_vel -3072; "
         "gravity +256/f)", "status": "VERIFIED", "provenance": W(
             "issue6_r23_report.md + r35 bot A (4000f, score 4003)")},
        {"button": "START", "effect": "title gate -> gameplay (gs 0->1)",
         "status": "VERIFIED", "provenance": W(
             "r23 boot4: vis_diff 122.4")},
        {"button": "SELECT", "effect": "pause/resume (gs 99 + resume)",
         "status": "VERIFIED", "provenance": W("r23 boot4")}]
    c.add_event("NTSC 2-instruction patch disclosed for rendering "
                "(SCREEN_HEIGHT 256->240, SetVideoMode 1->0) — logic "
                "unpatched", "OBSERVED",
                {"source": "scripts/r23t2_ntsc_patch_and_wrap.py",
                 "evidence": "patched image sha 042b94bb… local-only"})
    c.add_event("systems closure ALL_PHASES_OK (drain -3/f exact, enemy "
                "-1500 edge, death->gs5, auto-return 381f)", "VERIFIED",
                W("issue6_r34_report.md"))
    c.add_event("PLAYING_BOT: 4000f never-died, 8 causal dodges, 17 flower "
                "pickups vs idle 1000; NOT dominant (7 hits/15 passes)",
                "OBSERVED", W("issue6_r35_report.md"))
    c["unknowns"] = ["score cap 1000 residual (mechanism not disassembled)",
                     "mainHealth/mainTimer anchors located but not yet "
                     "wired into a bot policy"]
    c["next_experiment"] = {
        "hypothesis": "policy-v4 (arc-checked below-side taps + fx>0 "
                      "flower window) reaches dominance (0 hits/1500f)",
        "method": "A/B bot-v4 vs bot-A on savestate r35b checkpoint",
        "budget": "1 boot + savestate restores"}
    return c


# ---------------------------------------------------------------------------
def build_mspsx():
    c = _cap({"game_id": "mspsx",
              "title": "Minesweeper Plus (MSPSX)",
              "serial": "homebrew disc v0.1", "region": "NTSC",
              "exe_sha256": "d35a189b1ed14b7f07bf4cc31423ca43d8f34e35e8c3c"
                            "b40c11bc6d3d0a4c5fa",
              "fingerprint": {"license": "Unlicense (spi.c MPL-2.0 vendored)",
                              "repo": "github.com/AcidGunner/MSPSX"}})
    c["prior_art"] = [
        {"name": "AcidGunner/MSPSX", "kind": "upstream repo (full source)",
         "url": "https://github.com/AcidGunner/MSPSX",
         "license": "Unlicense", "inspected": True,
         "classification": "DIRECTLY_REUSABLE"}]
    P23 = {"source": "scripts/r23t1_mspsx_boot.py + r22.3(a) source map",
           "evidence": "scratch/r23 symbols + reveal trace"}
    P35 = {"source": "scripts r35c flood-plan run",
           "evidence": "docs/evidence_gifs/r35_mspsx_win.gif"}
    for va, role in ((0x18CD0, "cursor_y (phys off)"),
                     (0x18CD4, "cursor_x (phys off)"),
                     (0x18CDC, "revealed_total"),
                     (0x18CD8, "valid_total"),
                     (0x18CE0, "lost flag"),
                     (0x18CE4, "control_disable"),
                     (0x18CEC, "mines_left"),
                     (0x199DC, "board base (phys off, 16B/cell)")):
        c.add_field(va, 4, role, "VERIFIED", dict(P35, **P23))
    c["controls"] = [
        {"button": "B (CROSS)", "effect": "reveal/chord — needs hold 40f "
         "> 33f SPI poll cadence", "status": "VERIFIED",
         "provenance": W("issue6_r23_report.md")},
        {"button": "A (CIRCLE)", "effect": "flag 3-cycle", "status": "VERIFIED",
         "provenance": {"source": "r22.3(a) main.c :607-620",
                        "evidence": "source map"}},
        {"button": "START", "effect": "restart after end-state", "status":
         "VERIFIED", "provenance": {"source": "main.c :628-640",
                                    "evidence": "source map"}}]
    c.add_event("FULL BOARD WIN (r35): 59-click flood plan, WinCheck "
                "auto-flags all 32 mines, YOU WIN! RAM+PNG+source",
                "VERIFIED", W("issue6_r35_report.md"))
    c.add_event("Win-quirk: revealed_total stays stale after START regen "
                "(GenerateBoard does not reset it)", "OBSERVED", W(
                    "issue6_r35_report.md"))
    c["next_experiment"] = {"hypothesis": "usable as intake-calibration "
                            "benchmark (known-good sensors + known win)",
                            "method": "intake-game --game mspsx dry run",
                            "budget": "0 boots (offline)"}
    return c


# ---------------------------------------------------------------------------
def build_msx():
    disc_sha = _sha(MSX_BIN) if os.path.exists(MSX_BIN) else "UNAVAILABLE"
    c = _cap({"game_id": "msx",
              "title": "Metal Slug X (PS1 port)",
              "serial": "SLUS-01212", "region": "NTSC-U",
              "exe_sha256": disc_sha[:64],
              "fingerprint": {"disc_sha256": disc_sha,
                              "boot_exe": "SLUS_012.12",
                              "overlay": "ENEMY.BIN @0x8009C0E8 (468 fns)",
                              "publisher_disc": "Agetec, 2001-04-14"}})
    c["prior_art"] = [
        {"name": "TechnicallyComputers/Metal-Slug-X-Recomp",
         "kind": "static recompilation + mechanical C (PSXrecomp)",
         "url": "https://github.com/TechnicallyComputers/"
                "Metal-Slug-X-Recomp",
         "license": "none found in repo — reference-only, local research "
                    "use; requires owning the game",
         "inspected": True,
         "classification": "METHOD_REUSABLE — same build SLUS-01212; "
                           "2,931 EXE functions + 7,725 call edges "
                           "(functions.tsv/edges.json imported as external "
                           "static analysis); generated C is NOT original "
                           "source; ONLY 1 named symbol (BootEntry "
                           "0x80082A44); no ENEMY.BIN overlay coverage"},
        {"name": "gamehacking.org Metal Slug X (NTSC-U)",
         "kind": "cheat/RAM-map database",
         "url": "https://gamehacking.org/game/89284",
         "license": "public codes (hypotheses, not facts)",
         "inspected": True,
         "classification": "CALIBRATION_ONLY until validated"},
        {"name": "psxdatacenter SLUS-01212", "kind": "disc identity",
         "url": "https://psxdatacenter.com/games/U/M/SLUS-01212.html",
         "license": "reference", "inspected": True,
         "classification": "CALIBRATION_ONLY"}]
    # --- VERIFIED by prior runtime evidence (Issues 3/5/9, r24/25, r35) ---
    c.add_field(0x800CA268, 4, "entity_table_base", "VERIFIED",
                {"source": "Issue #5 A/B (hp_pair_freeze) + r24/25 live "
                           "probes",
                 "evidence": "worklog r-b256b17: stride 0x14C, HP+0x8E, "
                             "spawn+0xA0; damage-entry enemy_800A41D8 "
                             "(R38 note: the HP+0x8E part of that worklog "
                             "line is the SUPERSEDED label — see the "
                             "CONTRADICTED event; the stride/base stand "
                             "on independent evidence)"})
    # R38 contradiction fix: the old role "P1_entity_HP (base+0x8E)"
    # VERIFIED claim is retained ONLY as an address observation under a
    # new honest role; the semantic label is recorded as a CONTRADICTED
    # event (supersedes_role) so the guard in capsule.py rejects any
    # silent re-promotion.
    c.add_field(0x800CA2F6, 2, "entity_field_+0x8E (slot0 address "
                "observation; semantics UNRESOLVED — see CONTRADICTED "
                "event)", "OBSERVED",
                {"source": "Issue #5 pair-freeze A/B (b256b17) + Issue #10 "
                           "Gate B no-fire control (fab6538) + pincorr1 "
                           "telemetry",
                 "evidence": "A/B froze the PAIR 0x800CA2F6+0x800CA2FE "
                             "(mediator word NOT isolated); Gate B no-fire "
                             "decay 3/3 identical (raw JSON local-wiped; "
                             "committed records: docs/tools_matrix_issue10"
                             ".md caveat + combat.py note); pincorr1 "
                             "slot0+0x8E swings 291->81 damage-correlated "
                             "with regen-like recoveries while px-scroll "
                             "~0 (download/mission2_section_pin/pincorr1/"
                             "result.json); R38 reader census: 5 EXE "
                             "read-hits, ZERO halfword stores to +0x8E "
                             "(death_path.json + capstone decode; "
                             "r38_function_shortlist.json); EXCLUDED from "
                             "success oracles per R38 policy"})
    c.add_field(0x800CA30C, 2, "armored_entity_HP (entity_base+0xA4; "
                "truck live-verified)", "VERIFIED",
                {"source": "Issue #5 truck campaign (d99db899..b19ad97, "
                           "uplob6-12 + sessions 1-4)",
                 "evidence": "truck hp_a4 300->200->100->0 under grenades "
                             "(100 dmg/hit) with +400/+800 score events; "
                             "kill GAMEPLAY_VERIFIED 16x across sessions; "
                             "docs/truck_blocker_resolution.md; NOTE same "
                             "address as the cheatcc 'Invisible P1' poke "
                             "(cheat_leads[2]) — P1-slot +0xA4 semantics "
                             "remain UNKNOWN"})
    c.add_field(0x800D4210, 2, "mission_unlock_counter (u16)", "OBSERVED",
                {"source": "r20-t1 probe",
                 "evidence": "worklog r20: unlock counter, NOT stage "
                             "selector (r19 1-based conclusion RETRACTED)"})
    # --- cheat-DB leads (INFERRED until validated in-game) ---
    CHEAT_SRC = {"source": "gamehacking.org/game/89284 (Code Master/"
                 "nolberto82) + cheatcc 2001 variants",
                 "evidence": "r37t1 probe: values plausible-zero in menus, "
                             "in-game window BLOCKED (ladder not reproduced "
                             "in 2-boot cap post-rollback #8); "
                             "scratch/r37/msx_anchors/verdicts.json"}
    c.add_field(0x800EE318, 4, "score_p1 (u32 LE; max-score code writes "
                "0x05F5E0FF = 99,999,999)", "INFERRED", dict(CHEAT_SRC))
    c.add_field(0x800EE320, 4, "score_p2 (u32 LE)", "INFERRED", dict(CHEAT_SRC))
    c.add_field(0x80087A78, 1, "prisoners_saved_p1 (u8)", "INFERRED",
                dict(CHEAT_SRC))
    c.add_field(0x800D4213, 1, "unlock_another_mission byte (300-format "
                "code pokes it) — high byte of unlock u16", "INFERRED",
                dict(CHEAT_SRC, note="corroborates the 0x800D4210 block"))
    c["cheat_leads"] = [
        {"source": "gamehacking.org/game/89284",
         "code": "8003273E 2400 / 80032764 00C8 / 80032766 2405",
         "meaning": "Invincible (instruction patches)",
         "validation": "NOT_APPLIED (policy: cheat-assisted exploration "
                       "kept separate from normal-play claims)"},
        {"source": "gamehacking.org/game/89284",
         "code": "D00D4948 8000 / 800D4948 0000",
         "meaning": "Rapid Fire condition on 0xD4948 word",
         "validation": "PENDING"},
        {"source": "cheatcc 2001", "code": "800CA30C 0068",
         "meaning": "Invisible P1 — data poke inside P1 entity",
         "validation": "INFERRED (struct-consistent)"}]
    c.add_function(0x800A41D8, "damage entry (enemy side)", "VERIFIED",
                   {"source": "Issue #5 static death path",
                    "evidence": "worklog r-b256b17"})
    c.add_function(0x800A87F8, "in-overlay caller hub (8 callers)",
                   "OBSERVED",
                   {"source": "Issue #10 Gate A Ghidra run",
                    "evidence": "docs/mission2_final_value.md"})
    c.add_event("heli-kill recipe VERIFIED (hop + UP-lob at apex, |dx| "
                "7-29, 3 connects: hp_a4 300->0, +1100)", "VERIFIED",
                W("issue6_r35_report.md"))
    c.add_event("D7 pin: 4 attack policies all stopped at px 1164; "
                "past_clamp 1163.0 was a FALSE-POSITIVE (corrected to "
                ">1164.5); score 0->0 = zero real kills (honest "
                "correction of SlotTracker)", "VERIFIED",
                W("issue6_r35_report.md"))
    c.add_event("truck lives in slot 33 — outside the historical 24-slot "
                "scan window", "VERIFIED", W("issue6_r35_report.md"))
    c.add_event("mosque cannon is the rain source (session-2 +800 volley "
                "-> fallers 459->0-7); D7 pin-lift never reproduced",
                "OBSERVED", W("issue6_r35_report.md worklog archaeology"))
    c.add_event("r37t1: pure-input menu ladder (r17 ground truth) NOT "
                "reproduced within a 2-boot cap after rollback #8 — "
                "states 9->6 regression under repeated CROSS; checkpoints "
                "wiped", "OBSERVED",
                {"source": "scripts/r37t1_msx_cheat_anchors.py",
                 "evidence": "scratch/r37/msx_anchors/verdicts.json"})
    # --- R38 contradiction record: the '+0x8E = entity HP' label ---
    c.add_event(
        "The '+0x8E = entity HP' semantic label is CONTRADICTED for world "
        "entities and UNRESOLVED for slot 0. Contradicting evidence: (a) "
        "parked truck +0x8E stayed 254->254 under standing fire while its "
        "+0xA4 fell 300->0 under grenades (the historical '254->207 "
        "grenade damage' was the truck MOVING — screen-x shrink); (b) "
        "chopper +0x8E decayed 148->2 with NO player fire (camera advance, "
        "Gate B no-fire control, 3/3 identical); (c) static: writer "
        "0x80064674 adds camera-scroll deltas to +0x8C/+0x90 per entity "
        "(+0x8E = screen-x integer half); (d) the Issue #5 freeze A/B "
        "held the PAIR 0x800CA2F6+0x800CA2FE, so word-level causality was "
        "never isolated, and pincorr1 slot-0 readings (291->81, "
        "damage-correlated, regen-like recoveries, px-scroll ~0) do not "
        "distinguish player-HP from other per-entity state. RESOLUTION "
        "RULE: +0x8E is EXCLUDED from success oracles; armored-entity HP "
        "evidence is +0xA4; the address observation stays under role "
        "entity_field_+0x8E.",
        "CONTRADICTED",
        {"source": "Issue #5 truck campaign worklog (r-d99db899..b19ad97) "
                   "+ Issue #10 Gate B (fab6538) + R38 pincorr1 "
                   "re-analysis",
         "evidence": "docs/truck_blocker_resolution.md (SUPERSEDED section) "
                     "+ docs/tools_matrix_issue10.md caveat + "
                     "download/mission2_section_pin/pincorr1/result.json + "
                     "ps1play/agent/combat.py corrected-semantics block"},
        supersedes_role="P1_entity_HP (base+0x8E)")
    c.add_event(
        "Truck campaign semantics (Oct 25, GAMEPLAY_VERIFIED): armored "
        "truck HP = u16 at entity_base+0xA4 (300 fresh; grenade = 100 "
        "dmg; death state word0 = 0xA304); truck identity = ground "
        "contact (h=64) + state 0x9E88 + hp_a4 in [100,600]; truck seen "
        "in slot 14 (Oct 24 phase) and slot 33 (Oct 25 phase) — scans "
        "must cover >=36 slots", "VERIFIED",
        {"source": "scripts uplob6-12 + truck_resolution_session*.json "
                   "+ ps1play/agent/combat.py truck_kill_segments",
         "evidence": "data/games/SLUS-01212/truck_evidence/ "
                     "+ docs/truck_blocker_resolution.md (8/8+5+3 kills)"})
    c.add_event(
        "D7 release condition: the section VM's pending-entity queue "
        "CLEARING releases the pin — walker state 0xB -> 0xC, flags 0x1 "
        "-> 0x8, progress word leaves 0xFFFFFFFF (PROVEN 3/3 + policy "
        "banner 3/3 from the Oct-25 pin_ckpt phase, MISSION 1 banner "
        "6/6 total); NOT yet reproduced from a post-rollback rebuilt "
        "checkpoint (R35's 4 custom policies died at the pin with zero "
        "kills — checkpoint-phase variance, worklog 2026-10-23 note); "
        "release REQUIRES the section entities dead (chopper hop-lob "
        "|dx| 7-29; frozen 0x4054 soldiers = 2 AIMED bullets from px "
        "~992 side; truck via grenade lob |dx| 53-135)", "VERIFIED",
        {"source": "scripts/release_test.py rel1-3 + policy_chain_trial.py "
                   "(session 4) vs r35a_attack*.py (R35)",
         "evidence": "truck_evidence/session3/ + session4/ PNGs+JSONs; "
                     "worklog 2026-10-25 sessions 3-4; R35 report "
                     "issue6_r35_report.md"})
    c.add_event(
        "R38 TRUCK KILLED BY THE SHIPPED POLICY (matched live trial from "
        "the rebuilt r38_ckpt, deterministic x2): hp_a4 240 at engage -> "
        "-10 steps under sustained standing fire -> 150, one grenade "
        "-100 (counter 8->7) -> 50 -> wreck residual 30 -> 10 -> row "
        "gone by c95; wreck state 0xA44C at slot 9; the pure-RIGHT "
        "control arm held hp_a4 = 300 FROZEN for 45 chunks (no "
        "self-decay — the damage is input-caused). Score 0 -> 4600 "
        "(25+ kill events) with 0 combat deaths vs control score 0. "
        "The Oct-23 'forward fire does not kill armor (254->254)' "
        "reading is hereby corrected: that field was +0x8E screen-x; "
        "the REAL hp_a4 DOES chip under sustained fire", "VERIFIED",
        {"source": "scripts/r38t1_reach.py + r38t2_trials.py "
                   "(trialA1/A2 vs trialB_control)",
         "evidence": "truck_evidence/r38/r38_trial_report.json + "
                     "scratch/r38/trials.jsonl; boot ledger 2/5 "
                     "disclosed"})
    c.add_event(
        "R38 D7 PIN STILL HOLDS FROM THE REBUILT PHASE — blocker "
        "ISOLATED to the chopper: at every pin observation the census "
        "keeps slot 4 = chopper (st 0xAA94/0xABDC cycle, hp_a4 300, h "
        "207-210) ALIVE while the truck is a wreck (0xA44C) and the "
        "soldier wave is dead; the walker cycles (0xA,0x43) <-> (0,0) "
        "and no 0xC appears. The new aa_kill rule (J1 hop + UP-lob) "
        "CONNECTED once live per run (hp_a4 300 -> 200, the -100 "
        "grenade signature, deterministic x2) but the kill needs 3 "
        "connects and the connect rate is ~1/10 throws (chopper "
        "patrols dx -9..-51 vs the proven 7-29 band). A |dx|<=40 "
        "pre-throw gate was tried and FALSIFIED (0/6 connects, earlier "
        "one-shot bomb death php 291->0 because the first build had "
        "dropped the rain-hop); ungated + rain-hop restored = stable. "
        "Runs end at the death->restart wall; F6 respawn refills "
        "grenades (8->10 observed). Cheats stayed OUT of all success "
        "claims", "OBSERVED",
        {"source": "scripts/r38t3_aa_trial.py (boots 3-5, ledger "
                   "amendments 3->4->5 disclosed pre-run; one aborted "
                   "launch corrected in the ledger)",
         "evidence": "truck_evidence/r38/r38_aa_trial_report.json + "
                     "scratch/r38/aa_trials.jsonl + png/trialA1_pin_0a_43.png"})
    if os.path.exists(RECOMP_TSV):
        c.add_artifact("msxrecomp_functions", RECOMP_TSV)
    if os.path.exists(RECOMP_EDGES):
        c.add_artifact("msxrecomp_edges", RECOMP_EDGES)
    c["unknowns"] = [
        "slot-0 +0x8E semantics (player-HP-like vs other per-entity "
        "state) UNRESOLVED — pair-freeze A/B did not isolate the mediator "
        "word; excluded from oracles",
        "chopper kill rate: 1 connect/10 throws live; the positioning "
        "sub-rule that walks the player INTO the 7-29 band is the R39 "
        "lever (the pre-throw gate was falsified)",
        "the +0xA4 damage-delivery write site (EXE-side) not located",
        "score/prisoners/unlock cheat addresses not validated in-game "
        "(menu ladder still not re-walked post-rollback)",
        "lives counter data address (both DBs give code patches only)",
        "ENEMY.BIN overlay not covered by external recomp analysis",
        "boss HP outside 0x14C table or phase-gated (Issue #5 BLOCKED)"]
    c["next_experiment"] = {
        "hypothesis": "R39: a positioning sub-rule (walk/hold to keep "
                      "the tracked chopper within the 7-29 band at "
                      "throw time, then the proven J1 hop+UP-lob) "
                      "raises the connect rate enough to land 3 "
                      "connects inside one mission window -> the "
                      "pending-entity queue clears -> the pin releases "
                      "(0xB->0xC) -> the MISSION 1 banner through the "
                      "shipped policy from a REBUILT checkpoint",
        "method": "boot 1 reach rebuild (r38t1 recipe); boot 2: "
                  "matched trial AA-v3 (positioning sub-rule) vs the "
                  "recorded r38 aa trials as baseline; oracle = chopper "
                  "hp_a4 300->0 + walker 0xC + banner PNG (never +0x8E)",
        "budget": "2 boots, ~20k frames"}
    return c


BUILDERS = {"buzzybee": build_buzzybee, "mspsx": build_mspsx,
            "msx": build_msx}


def build_capsule(game_id):
    if game_id not in BUILDERS:
        raise KeyError(f"no builder for {game_id}; known: "
                       f"{sorted(BUILDERS)}")
    return BUILDERS[game_id]()


if __name__ == "__main__":
    for gid in ("buzzybee", "mspsx", "msx"):
        cap = build_capsule(gid)
        out = os.path.join(DATA, "knowledge", gid, "capsule.json")
        size = cap.save(out)
        print(f"{gid}: {size} B {len(cap['memory_fields'])} fields "
              f"{len(cap['events'])} events")

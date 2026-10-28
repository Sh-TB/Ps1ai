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
                             "spawn+0xA0; damage-entry enemy_800A41D8"})
    c.add_field(0x800CA2F6, 2, "P1_entity_HP (base+0x8E)", "VERIFIED",
                {"source": "Issue #5 in-run A/B anchor framework",
                 "evidence": "hp 56 dmg baseline vs freeze treatment"})
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
    c.add_field(0x800CA30C, 2, "P1 entity base+0xA4 (cheat 'Invisible P1' "
                "writes 0x0068 here)", "INFERRED", dict(
                    CHEAT_SRC,
                    note="independently consistent with the VERIFIED "
                         "entity table at 0x800CA268 (offset inside "
                         "stride 0x14C)"))
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
    if os.path.exists(RECOMP_TSV):
        c.add_artifact("msxrecomp_functions", RECOMP_TSV)
    if os.path.exists(RECOMP_EDGES):
        c.add_artifact("msxrecomp_edges", RECOMP_EDGES)
    c["unknowns"] = [
        "D7 pin release condition (state machine owner unknown)",
        "score/prisoners/unlock cheat addresses not validated in-game "
        "(ladder BLOCKED this round)",
        "lives counter data address (both DBs give code patches only)",
        "ENEMY.BIN overlay not covered by external recomp analysis",
        "boss HP outside 0x14C table or phase-gated (Issue #5 BLOCKED)"]
    c["next_experiment"] = {
        "hypothesis": "menu-ladder re-walk with DOWN-highlight steps "
                      "reaches Mission 1 and enables the cheat-anchor "
                      "validation windows (H1/H4)",
        "method": "single boot, state-byte-driven ladder with cursor-"
                  "struct polling (0x957D8-0x957F8), then W1/W2 windows",
        "budget": "1-2 boots, ~8k frames"}
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

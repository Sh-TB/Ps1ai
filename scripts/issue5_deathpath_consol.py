#!/usr/bin/env python3
"""issue5_deathpath_consol.py — merge the §4 static death-path scan with
curated annotations into data/games/SLUS-01212/death_path.json, and
register the NEW entity-table discovery in entities.json.

Discovery chain (all evidence-backed, this session):
  1. overlay reader `lhu $a1, 0x8e($s1)` with $s1 = 0x800CA268
     (disasm 0x800a00e0..0x800a00f8) -> entity[0].HP = 0x800CA2F6
     = the live-verified freeze word (validate_inv2 / ab A/B).
  2. $s2 = $s1 + 0x14c -> entity stride 0x14C; entity[1].HP = 0x800CA442
     (cross-check: EXE 0x80056610 lhu -0x5bbe($v0) = 0x800CA442).
  3. EXE func_8002DB48 / func_8002F3C4: spawn/reset HP := 0xA0 (160).
  4. Overlay enemy_800A41D8: collision-gated HP writes (+0x40/-0x80/+0x40)
     via the player pointer *(0x800C9A98) + handler word (+0x0) ->
     0x800A87F8 (dispatch cluster) + state byte +0xDE.
"""
import json
import os
import sqlite3

REPO = "/home/z/my-project/ps1ai"
KB = os.path.join(REPO, "data", "games", "SLUS-01212")
WORK = "/home/z/my-project/work/msx_recomp"
SCAN = os.path.join(KB, "death_path.json")

db = sqlite3.connect(os.path.join(WORK, "index", "re_index.sqlite"))


def callers(fva):
    return [r[0] for r in db.execute(
        "SELECT src FROM edges WHERE dst=?", (fva,)).fetchall()]


def main():
    scan = json.load(open(SCAN))
    scan["curated"] = {
        "identity": {
            "exe_sha256": "1508b53216cc20dad8c1354e7702dae2940c34e7b2adeff"
                          "b00337ab6659e0f35",
            "disc_md5": "37d9e1179a32661800e74858009a4f8b",
            "overlay": "ENEMY.BIN verbatim at VA 0x8009C0E8 (live-verified,"
                       " probe3 V1/V2)",
        },
        "entity_table": {
            "status": "VERIFIED",
            "base": "0x800CA268",
            "stride": 0x14C,
            "fields": {
                "+0x00": "state-handler word (sw 0x800A87F8 on hurt)",
                "+0x27": "u8 (read by mission logic)",
                "+0x2a": "s16 (reset -1 at spawn)",
                "+0x2c": "u16 (0x18/0x19 at spawn; sound/anim id)",
                "+0x8e": "HP u16 (spawn 0xA0=160; entity[0].HP = "
                         "0x800CA2F6 = live-verified freeze word)",
                "+0x92": "companion u16 (0x70/0x80 at spawn; +-0x20 on "
                         "hurt)",
                "+0x96": "u16 — second member of the live pair "
                         "(0x800CA2FE); semantics NOT yet pinned",
                "+0xc4": "u16 (0xFFFF at spawn)",
                "+0xd1": "u8 HUD-copy enable flag",
                "+0xd2": "u8 HUD-copy enable flag",
                "+0xde": "u8 state byte (written by mission logic)",
                "+0xea/+0xeb": "u8 blink/i-frame flags (Issue #3)",
            },
            "evidence": [
                "OVL 0x800a00b0 lw $v0, -0x6568($v0) with lui 0x800d -> "
                "root slot 0x800C9A98; sb $x, 0xde($v0) writes player "
                "state byte",
                "OVL 0x800a00e8 addiu $s2, $s1, 0x14c; 0x800a00f0/94/f8 "
                "lhu 0x8e($s1/$a0/$s2) -> three entity HP reads",
                "$s1 = 0x800CA268 via addiu $s1, $v0, -0x5d98 (lui 0x800d)",
                "EXE 0x80056610 lhu -0x5bbe($v0) = 0x800CA442 = "
                "entity[1].HP (base 0x800CA3B4 + 0x8e)",
                "EXE func_8002DB48 spawn: sh 0xa0, 0x8e($v1) after lw "
                "-0x6568($s0)",
            ],
        },
        "hp_writers": {
            "spawn_reset": [
                {"pc": "0x8002db88", "fn": "func_8002DB48",
                 "note": "player spawn/reset HP:=0xA0; also 0x92:=0x80, "
                         "0x2c:=0x18, 0xc4:=0xFFFF, 0x2a:=-1"},
                {"pc": "0x8002f4c8", "fn": "func_8002F3C4",
                 "note": "respawn/vehicle reset HP:=0xA0; 0x92:=0x70, "
                         "sound 0x19"},
                {"pc": "0x8002d3e8", "fn": "func_8002D3C0",
                 "note": "entity type 0xA00 spawn HP:=0xA0 (0x92:=0x70) "
                         "— same table+field for enemies"},
            ],
            "damage_entry_overlay": {
                "fn": "enemy_800A41D8",
                "status": "STRONG_CANDIDATE (collision-gated)",
                "pc_stores": ["0x800a437c (+0x40)", "0x800a4398 (-0x80)",
                              "0x800a43b4 (+0x40)"],
                "flow": "jal 0x800196a4 collision gate (ent+0x30, "
                        "ent+0x78 args) -> player->0x92 += 0x20; "
                        "player->HP += 0x40; call 0x80050d14; HP -= "
                        "0x80; call; HP += 0x40; player->handler(+0x0) "
                        "= 0x800A87F8 (dispatch cluster); 0x92 -= 0x20",
                "interpretation": "hurt-state entry: the -0x80 (=-128) "
                                  "store is the blast/truck-scale damage; "
                                  "the +0x40 pair brackets it (net 0 when "
                                  "all three run — consistent with the "
                                  "blink/i-frame window, NOT with "
                                  "attrition damage)",
            },
            "per_hit_decrement": {
                "status": "PENDING — the observed ~-16/hit attrition "
                          "store is NOT among the 6 sh +0x8e sites; it "
                          "must go through a word store or a different "
                          "base-register chain. Next: live hook on "
                          "entity[0].HP writer (watchpoint-style diff "
                          "with the verified mapping)",
            },
        },
        "flags_word_writers": [
            {"pc": "0x8006f074", "fn": "func_8006EFF0",
             "note": "player-status OR-bit updater (0x8006F058..74 "
                     "cluster)"},
            {"pc": "0x800718b8", "fn": "func_80071808",
             "note": "GAME OVER setter candidate (adjacent to the "
                     "' GAME OVER' string render gate)"},
            {"pc": "0x8006e968", "fn": "func_8006E8B0"},
            {"pc": "0x8006ed48", "fn": "func_8006ED04"},
        ],
        "death_check_sites": (
            "22 lhu +0x8e/zero-branch sites (see hits); func_8002ACE4 "
            "identified as the HUD copier (copies entity[0]/[1] HP into "
            "a UI buffer gated by flags 0xd1/0xd2) — NOT a death check"),
        "death_paths": {
            "path1_hp_damage": {
                "status": "EVIDENCE_BACKED",
                "chain": "enemy contact/projectile -> collision gate "
                         "(0x800196a4 family) -> overlay HP writes "
                         "(enemy_800A41D8 / per-hit decrement PENDING) "
                         "-> HP 0 -> death state (state byte +0xDE / "
                         "handler +0x0) -> lives attrition -> flags_word "
                         "-1 (GAME OVER, func_80071808 family)",
                "live": "hp_pair_freeze VERIFIED prevents damage death "
                        "(validate_inv2 + this session's A/B)",
            },
            "path2_instant_pit": {
                "status": "OBSERVED_LIVE / PENDING_STATIC",
                "evidence": "deaths with zero recent i-frame hits "
                            "(pit signature, issue5_controller full-runs; "
                            "water channels/pits bypass HP entirely)",
                "next": "identify the Y-coordinate/state-byte transition "
                        "for pit death in the overlay",
            },
        },
    }
    # attach caller info to hp reader hits
    for h in scan.get("hits", []):
        if h.get("function", {}).get("va"):
            fva = int(h["function"]["va"], 16)
            h["function"]["callers_full"] = [hex(c) for c in callers(fva)]
    with open(SCAN, "w") as f:
        json.dump(scan, f, indent=1)
    print("death_path.json consolidated")

    # ---- entities.json registry update ----
    ep = os.path.join(KB, "entities.json")
    ent = json.load(open(ep))
    ent.setdefault("entity_table", {})
    ent["entity_table"] = {
        "status": "VERIFIED",
        "updated": "2026-10-22",
        "root_pointer_slot": "0x800C9A98",
        "base": "0x800CA268",
        "stride": "0x14C",
        "hp_field": "+0x8e u16 (spawn 0xA0)",
        "entity0_hp": "0x800CA2F6",
        "entity1_hp": "0x800CA442",
        "pair_second_word": "0x800CA2FE = entity0+0x96 (semantics PENDING)",
        "evidence": scan["curated"]["entity_table"]["evidence"],
        "provenance": "issue5_deathpath.py + curated disassembly "
                      "(issue #5 continuation section 4)",
    }
    with open(ep, "w") as f:
        json.dump(ent, f, indent=1, sort_keys=True)
    print("entities.json updated with entity_table")


if __name__ == "__main__":
    main()

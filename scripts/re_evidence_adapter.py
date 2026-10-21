#!/usr/bin/env python3
"""re_evidence_adapter.py — verified RE evidence contract for ps1play
tools (issue #5 continuation §7).

A thin, read-only adapter over the EXISTING knowledge base:
  data/games/SLUS-01212/{entities.json, death_path.json, cheats.json,
  overlay_index.json, re_index.json}

It exposes ONLY evidence-tagged references (every entry carries a
status + provenance pointer) so runners/telemetry never hard-code an
unverified address. It does NOT create a new index — it projects the
committed KBs into a stable in-memory contract.

CLI:  python3 scripts/re_evidence_adapter.py [--json] [--only VERIFIED]
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(_REPO, "data", "games", "SLUS-01212")


def _load(name, required=True):
    p = os.path.join(KB, name)
    if not os.path.exists(p):
        if required:
            raise FileNotFoundError(f"KB file missing: {p}")
        return {}
    with open(p) as f:
        return json.load(f)


def build_contract():
    """Project committed KBs into the verified-evidence contract."""
    ent = _load("entities.json")
    dp = _load("death_path.json", required=False)
    ov = _load("overlay_index.json", required=False)
    et = ent.get("entity_table", {})

    refs = {}

    def add(key, addr, dtype, role, status, provenance):
        refs[key] = {"addr": addr, "dtype": dtype, "role": role,
                     "status": status, "provenance": provenance}

    # live-verified player HP pair (freeze target; registry VERIFIED)
    add("hp_pair_0", 0x800CA2F6, "u16", "player_entity_hp_word_1",
        "VERIFIED", "validate_inv2 hit-diff + ab_invuln A/B; "
        "entity_table cross-check (base 0x800CA268 + 0x8e)")
    add("hp_pair_1", 0x800CA2FE, "u16", "player_entity_hp_word_2",
        "VERIFIED", "validate_inv2 hit-diff (co-drop); semantics = "
        "entity0+0x96 PENDING")
    add("entity_table_base", int(et.get("base", "0x800CA268"), 16),
        "ptr", "entity_array_base", et.get("status", "PENDING"),
        "issue5_deathpath.py curated disassembly "
        "(OVL 0x800a00e0..f8 + EXE 0x80056610)")
    add("entity_stride", int(et.get("stride", "0x14C"), 16), "u32",
        "entity_struct_stride", et.get("status", "PENDING"),
        "OVL addiu $s2, $s1, 0x14c")
    add("player_root_slot", int(et.get("root_pointer_slot",
        "0x800C9A98"), 16), "ptr", "player_entity_pointer_slot",
        "OBSERVED", "root-relative writes (sb +0xde) in overlay "
        "mission logic; live value varies (handle/ptr per boot)")
    add("flags_word", 0x800EE518, "u32", "game_state_flags "
        "(0xFF active, 0x1 menus/GAME_OVER, -1 game-over draw gate)",
        "VERIFIED", "issue5_trace full-run 4/4 correlation + static "
        "61-xref block")
    add("score", 0x800EE318, "u32", "score_low (LOW-BYTE only per HUD "
        "convergence)", "VERIFIED", "issue3 live causality")
    add("per_life_accum", 0x800CA2E0, "u16",
        "per-life accumulator (RESETS ON DEATH — death sensor)",
        "OBSERVED", "issue3 anchor; resets observed across boots")
    add("grenade_counter", 0x800EDCF4, "u8",
        "grenade inventory (strict-series anchor)", "VERIFIED",
        "validate_cheats strict series 10,9,8,7,6 x2 boots")
    add("iframe_word", 0x800CA30C, "u16",
        "damage-window word (partial gate; NOT invulnerability)",
        "TESTED", "validate_iframe: freeze reduces damage, does not "
        "close the gate")
    add("entity1_hp", 0x800CA442, "u16", "entity[1].hp",
        et.get("status", "PENDING"), "EXE 0x80056610 lhu -0x5bbe($v0); "
        "base 0x800CA3B4 + 0x8e")

    overlay = {
        "module": "ENEMY.BIN",
        "status": (ov.get("modules", {}).get("ENEMY.BIN", {})
                   .get("status", "UNKNOWN")) if isinstance(ov, dict)
                  else "UNKNOWN",
        "live_dest": "0x8009C0E8",
        "code_head": "0x800A9268",
        "note": "0x800A7800 mapping FALSIFIED live (probe3)",
    }
    death_paths = (dp.get("curated", {}).get("death_paths", {})
                   if isinstance(dp, dict) else {})
    return {
        "schema": "ps1play-re-evidence/1",
        "game": "SLUS-01212",
        "exe_sha256": "1508b53216cc20dad8c1354e7702dae2940c34e7b2adeff"
                      "b00337ab6659e0f35",
        "refs": refs,
        "overlay": overlay,
        "death_paths": death_paths,
        "rule": "any address not in this contract (or with status other "
                "than VERIFIED) must NOT drive policy/writes",
    }


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    only = "--only" in args and "VERIFIED"
    c = build_contract()
    if only:
        c["refs"] = {k: v for k, v in c["refs"].items()
                     if v["status"] == "VERIFIED"}
    if "--json" in args or (args and "--only" in args):
        print(json.dumps(c, indent=1))
    else:
        print(f"RE evidence contract — {c['game']} "
              f"(exe {c['exe_sha256'][:16]}…)")
        for k, v in sorted(c["refs"].items()):
            print(f"  {k:20s} {v['addr']:#x} {v['dtype']:4s} "
                  f"{v['status']:9s} {v['role']}")
        print(f"  overlay: {c['overlay']['module']} @ "
              f"{c['overlay']['live_dest']} "
              f"({c['overlay']['status']})")
    return c


if __name__ == "__main__":
    main()

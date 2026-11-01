#!/usr/bin/env python3
"""r66_dryrun.py — the OFFLINE telemetry contract dry-run (zero boots).

The R51/R52 offline-dry-run rule applied to the R66 runner BEFORE the
stage-2 boot is spent.  Checks (mock memory/core only — no emulator):

  1. the union net is exactly the R51 union (0x60..0xE0 even, 65).
  2. frame_walk_hunt rows carry BOTH the R48 `direct` 5-word table
     AND the pay-frame union-net `words` (the R48-R52 joins intact).
  3. the R50 helpers (slot_state_in / slot_alive_in / sc_jumps)
     accept the hunt rows unchanged.
  4. gate_diag classifies a synthetic starved census correctly
     (invul rejection + corridor_occupied with the occupant list).
  5. the ledger gate refuses to exceed the cap and consumes no entry.
  6. the R66 goals/flags are the disclosed ones (PIERCE withheld,
     pass B destarve, advance budget sane).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r66t1_payframe_destarve as R66             # noqa: E402
import r48t1_frame_exact_taps as R48              # noqa: E402
from r50t1_controlled_corridor import (           # noqa: E402
    slot_state_in, slot_alive_in, sc_jumps)
from r51t1_wound_hunt import corridor_occupants   # noqa: E402


class FakeMem:
    def u16(self, addr):
        return (addr % 97) + (addr // 7 % 31)

    def u32(self, addr):
        return self.u16(addr) | (self.u16(addr + 2) << 16)

    def u8(self, addr):
        return addr % 251


class FakeCore:
    def run(self, n, btns):
        pass

    def frame_rgb(self):
        return None


class FakeP:
    core = FakeCore()

    def load_state(self, name):
        pass

    def save_state(self, name):
        pass


def main():
    ok = {}
    # ---- 1. the union net --------------------------------------------
    net = list(R66.UNION_NET)
    ok["net_is_union_60_e0"] = (net[0] == 0x60 and net[-1] == 0xE0
                                and all(o % 2 == 0 for o in net)
                                and len(net) == 65)

    # ---- stub the census layers (offline, no game state) -------------
    ents = [{"slot": 3, "st": 0x4054, "x": 1275.0, "kind": "enemy"},
            {"slot": 18, "st": 0x515C, "x": 1357.2, "kind": "enemy"},
            {"slot": 0, "st": 0x1, "x": 0.0, "kind": "player"}]
    R66.mini_census = lambda m, px: [dict(e) for e in ents]

    def fake_direct(mm):
        return [{"slot": 3, "st": 0x4054, "x": 1275.0},
                {"slot": 18, "st": 0x515C, "x": 1357.2}]

    R66.direct_table = fake_direct

    # ---- 2. the hunt rows contract -----------------------------------
    rows = R66.frame_walk_hunt(FakeP(), FakeMem(), lambda ev: None, 9,
                               "TEST", 4, {"Y"})
    r0 = rows[0]
    ok["rows_have_direct"] = all("direct" in r for r in rows)
    ok["rows_have_words"] = (
        "words" in r0 and set(r0["words"].keys()) == {"3", "18"}
        and all(len(v) == 65 for v in r0["words"].values()))
    ok["rows_have_sc_px"] = all(
        "sc" in r and "px" in r and "f_rel" in r for r in rows)
    ok["net_label_once"] = (r0["net"] is not None
                            and rows[1]["net"] is None)

    # ---- 3. the R50 helpers accept the rows --------------------------
    ok["sc_jumps"] = sc_jumps(rows) == []
    ok["slot_state_in"] = slot_state_in(rows, 3)[0]["to"] == 0x4054
    ok["slot_alive_in"] = slot_alive_in(rows, 3) is True

    # ---- 4. gate_diag classification ----------------------------------
    cen = [
        {"slot": 5, "st": 0xAB94, "x_px": 1300.0, "targetable": True,
         "kind": "wasp"},
        {"slot": 8, "st": 0x42BC, "x_px": 1350.0, "targetable": True,
         "kind": "soldier"},
        {"slot": 11, "st": 0x4054, "x_px": 1310.0, "targetable": True,
         "kind": "soldier"},
        {"slot": 12, "st": 0x0004, "x_px": 0.0, "targetable": False,
         "kind": "corpse"},
    ]
    d = R66.gate_diag(cen, 1224.0, used=set())
    ok["diag_n_live"] = d["n_live"] == 3          # slot12 x=0 dropped
    ok["diag_invul"] = d["n_invul"] == 1
    by_slot = {c["slot"]: c for c in d["candidates_rejected"]}
    ok["diag_invul_reason"] = \
        by_slot[5]["reason"] == "invulnerable"
    occ8 = by_slot[8]["reason"] == "corridor_occupied" and \
        {o["slot"] for o in by_slot[8]["occupants"]} == {5, 11}
    ok["diag_occupied_reason"] = occ8

    # ---- 5. the ledger gate ------------------------------------------
    with tempfile.TemporaryDirectory() as td:
        old_s, old_e, old_l = R66.SCRATCH, R66.EVID, R66.LEDGER
        R66.SCRATCH, R66.EVID = td, td
        R66.LEDGER = os.path.join(td, "boots_used.json")
        try:
            led_path = os.path.join(td, "boots_used.json")
            with open(led_path, "w") as f:
                json.dump({"cap": 2, "count": 2, "log": []}, f)
            try:
                R66.amend_ledger("over-cap probe")
                ok["ledger_gate"] = False
            except SystemExit:
                ok["ledger_gate"] = True
            with open(led_path) as f:
                led = json.load(f)
            ok["ledger_no_entry"] = led["count"] == 2 and \
                len(led["log"]) == 0
        finally:
            R66.SCRATCH, R66.EVID, R66.LEDGER = old_s, old_e, old_l

    # ---- 6. the disclosed goals/flags ---------------------------------
    ok["pierce_withheld"] = R66.PIERCE_GOAL == 0
    ok["connect_goal"] = R66.CONNECT_GOAL == 4
    ok["kill_goal"] = R66.KILL_GOAL == 1
    ok["advance_sane"] = (0 < R66.ADVANCE_STEP_F <= 30
                          and R66.ADVANCE_BUDGET_F <= 300)
    ok["frontier_names"] = R66.FRONTIER == ("r66_frontier_a",
                                            "r66_frontier_b")
    ok["tap_window"] = (R48.TAP_FRAMES == 3 and R48.TAIL_FRAMES == 20)

    bad = [k for k, v in ok.items() if not v]
    print(json.dumps({"ok": not bad, "checks": ok,
                      "failed": bad}, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""r52_dryrun.py — the OFFLINE telemetry contract dry-run (zero boots).

The R51 offline-gate-dry-run precedent applied to the R52 telemetry
defect family: boot 2 crashed on the missing `direct` key (the R50
helpers read it), boot 3 on the missing `direct_table` import (the
control walk).  Both are runner-code defects, NOT protocol defects —
this dry-run proves the frame-row contract offline BEFORE boot 4:

  1. frame_walk_hunt rows carry BOTH the R48 `direct` 5-word table
     AND the pay-frame union-net `words` (a strict superset of the
     R48 row format — the R48/R50 analysis joins stay intact).
  2. the R50 helpers (slot_state_in / slot_alive_in / sc_jumps)
     accept the hunt rows unchanged.
  3. the union net is exactly the R51 union (0x60..0xE0 even).

Mock memory/core only — no emulator, no boot, no game state.
"""
from __future__ import annotations

import os
import sys

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r52t1_payframe_wound as R52                # noqa: E402
import r48t1_frame_exact_taps as R48              # noqa: E402
from r50t1_controlled_corridor import (           # noqa: E402
    slot_state_in, slot_alive_in, sc_jumps)


class FakeMem:
    """Deterministic mock: u16 = (base % 97) + (off % 31), u32 composed."""

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
    # ---- 3. the union net is the R51 union ---------------------------
    net = list(R52.UNION_NET)
    ok["net_is_union_60_e0"] = (net[0] == 0x60 and net[-1] == 0xE0
                                and all(o % 2 == 0 for o in net)
                                and len(net) == 65)

    # ---- stub the census layers (offline, no game state) -------------
    ents = [{"slot": 3, "st": 0x4054, "x": 1275.0, "kind": "enemy"},
            {"slot": 18, "st": 0x515C, "x": 1357.2, "kind": "enemy"},
            {"slot": 0, "st": 0x1, "x": 0.0, "kind": "player"}]
    R52.mini_census = lambda m, px: [dict(e) for e in ents]

    def fake_direct(mm):
        return [{"slot": e["slot"], "st": e["st"], "x": e["x"],
                 "sx": 1.0, "h": 2, "a4": 3} for e in ents]

    R52.direct_table = fake_direct

    # ---- 1. the hunt rows carry direct AND words ---------------------
    rows = R52.frame_walk_hunt(FakeP(), FakeMem(), lambda ev: None,
                               0, "DRYRUN", 3, set())
    ok["rows_n"] = len(rows) == 3
    ok["rows_have_direct"] = all("direct" in r for r in rows)
    ok["rows_have_words"] = all("words" in r and r["words"]
                                for r in rows)
    live = [str(e["slot"]) for e in ents
            if e["slot"] and e["x"] != 0.0]
    ok["words_live_slots_only"] = all(
        set(r["words"].keys()) == set(live) for r in rows)
    ok["words_full_net"] = all(
        all(len(v) == len(net) for v in r["words"].values())
        for r in rows)
    ok["net_key_recorded_once"] = (
        rows[0]["net"] is not None and rows[1]["net"] is None)

    # ---- 2. the R50 helpers accept the hunt rows ---------------------
    r0 = rows[0]
    trans = slot_state_in(rows, 3)
    ok["slot_state_in_works"] = isinstance(trans, list)
    ok["slot_alive_in_works"] = slot_alive_in(rows, 18) is not None
    ok["sc_jumps_works"] = isinstance(sc_jumps(rows), list)

    # ---- the fire_tap composition contract (row keys read) -----------
    need = {"f_rel", "sc", "px", "ents", "direct"}
    ok["rows_superset_of_r48"] = need.issubset(set(r0.keys()))

    print("[r52-dryrun]", ok)
    if not all(ok.values()):
        raise SystemExit(f"DRYRUN FAILED: "
                         f"{[k for k, v in ok.items() if not v]}")
    print("[r52-dryrun] ALL CONTRACT CHECKS PASS — boot 4 cleared "
          "for the telemetry path (the disclosed amendment)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

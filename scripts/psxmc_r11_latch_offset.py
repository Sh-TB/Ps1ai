#!/usr/bin/env python3
"""psxmc_r11_latch_offset.py — Round 11 (Task 17-b), SEGMENT 1.

Static extraction of the CURRENT BreakingState offset inside the player
struct (the round-10 "canonical-latch disambiguation" lever, player.c:134
semantics) + a live cross-validation boot (ONE beetle boot, --live).

STATIC (--static, default, no emulator):
  1. player.c / breaking_state.h provenance: the release tarball
     (infdev_release_2025_04_18T04_35_17_.tar.gz) contains ONLY binaries
     (PSXMC.bin/.elf/.exe/.map/.cue) — the upstream source used since
     round 10 is the EngineersBox/PSX-Minecraft checkout (git 8142a1a).
     Layout recorded from breaking_state.h (fields, order, types).
  2. capstone disasm of the FIXED binary (/home/z/my-project/emu/
     games_homebrew/PSXMC.elf + PSXMC.map): updateBreakingState
     @0x80013C9C (player.c:134 per map) — the latch store site after
     the raycast; playerInit reset (inlined breakingStateReset);
     playerInputHandler jal sites.  Emits the concrete offset of
     player->breaking.

LIVE (--live): boot -> settle -> world -> 3x straight-down known-hit
probes (pitch 88) parsed via breaking_current (static window) + world
arbitration + validate_known_hit; horizon negative control (window must
stay zeroed); +20deg forward probe; RepeatLatchTracker across all
probes (live latch must update on EVERY probe); agreement with the r10
diff-candidate scan (same block-ptr slot).

Verdicts: LATCH_OFFSET_EXTRACTED / LATCH_OFFSET_VALIDATED /
LATCH_OFFSET_BROKEN / INCONCLUSIVE (honest, with numbers).
Evidence: scratch/round11_psxmc/latch_offset/
"""
import json
import os
import struct
import subprocess
import sys

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from psxmc_r7_lib import Evid, sha  # noqa: E402
import psxmc_r10_lib as L  # noqa: E402
import psxmc_r10_oracle as O  # noqa: E402
import psxmc_r11_lib as R11  # noqa: E402

ELF = "/home/z/my-project/emu/games_homebrew/PSXMC.elf"
MAP = "/home/z/my-project/emu/games_homebrew/PSXMC.map"
TARBALL = "/home/z/my-project/emu/games_homebrew/infdev_release_2025_04_18T04_35_17_.tar.gz"
SRC_CHECKOUT = "/tmp/psxmc_up/psxmc"
OUT = os.path.join(REPO, "scratch", "round11_psxmc", "latch_offset")
WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r11"

SRC_FILES = [
    "src/game/entity/player.c",
    "src/game/entity/player.h",
    "src/game/blocks/breaking_state.h",
    "src/game/world/world_raycast.h",
    "src/entity/entity.h",
    "src/physics/physics_object.h",
]

CUE = O.CUE


# ---------------------------------------------------------------- static ----
def load_segments(raw):
    if raw[:4] == b"\x7fELF":
        e_phoff = struct.unpack_from("<I", raw, 0x1C)[0]
        e_phentsize = struct.unpack_from("<H", raw, 0x2A)[0]
        e_phnum = struct.unpack_from("<H", raw, 0x2C)[0]
        segs = []
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type, p_offset, p_vaddr, p_paddr, p_filesz = \
                struct.unpack_from("<IIIII", raw, off)
            if p_type == 1:
                segs.append((p_vaddr, p_offset, p_filesz))
        return segs
    return [(0x80010000, 0x800, len(raw) - 0x800)]


def disasm(raw, segs, va, sz):
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    for sva, soff, ssz in segs:
        if sva <= va < sva + ssz:
            f = soff + (va - sva)
            return [(i.address, i.mnemonic, i.op_str)
                    for i in md.disasm(raw[f:f + sz], va)]
    return []


def find_jal(raw, segs, target_va, text=(0x80010000, 0x1000, 0x2C59E)):
    tva, toff, tsz = text
    wj = 0x0C000000 | ((target_va >> 2) & 0x3FFFFFF)
    words = struct.unpack_from(f"<{tsz // 4}I", raw, toff)
    return [tva + i * 4 for i, w in enumerate(words) if w == wj]


def static_extract(ev):
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32  # noqa: F401
    rep = {"mode": "static", "inputs": {}}
    for path in (ELF, MAP, TARBALL):
        h = sha(open(path, "rb").read())
        rep["inputs"][os.path.basename(path)] = h[:16]

    # --- 1. source provenance ------------------------------------------------
    tar_members = subprocess.run(
        ["tar", "-tzf", TARBALL], capture_output=True, text=True
    ).stdout.split()
    rep["tarball_members"] = tar_members
    src_ok = os.path.isdir(os.path.join(SRC_CHECKOUT, "src"))
    rep["source"] = {
        "tarball_has_src": any("player.c" in m for m in tar_members),
        "checkout": SRC_CHECKOUT if src_ok else None,
        "note": "release tarball is binaries-only; upstream source read "
                "from the EngineersBox/PSX-Minecraft checkout used since "
                "round 10 (git 8142a1a)" if src_ok else "MISSING",
    }
    if src_ok:
        gi = subprocess.run(["git", "log", "--oneline", "-1"],
                            cwd=SRC_CHECKOUT, capture_output=True, text=True
                            ).stdout.strip()
        rep["source"]["git_head"] = gi
        rep["source"]["sha256"] = {}
        for rel in SRC_FILES:
            p = os.path.join(SRC_CHECKOUT, rel)
            if os.path.exists(p):
                rep["source"]["sha256"][rel] = sha(open(p, "rb").read())[:16]
        # copy the load-bearing excerpts into the evidence dir
        os.makedirs(OUT, exist_ok=True)
        for rel in ("src/game/entity/player.c",
                    "src/game/blocks/breaking_state.h"):
            dst = os.path.join(OUT, os.path.basename(rel))
            with open(os.path.join(SRC_CHECKOUT, rel), "rb") as f, \
                    open(dst, "wb") as g:
                g.write(f.read())

    # --- 2. capstone extraction ----------------------------------------------
    raw = open(ELF, "rb").read()
    segs = load_segments(raw)
    rep["segments"] = [[hex(a), hex(o), hex(s)] for a, o, s in segs]

    mp = open(MAP).read()
    import re
    sym = {}
    for name in ("updateBreakingState", "playerInit", "playerInputHandler",
                 "worldRayCastIntersection", "player"):
        m = re.search(rf"\b{name} [TDBbr] (?:ffffffff)?([0-9a-f]+)", mp)
        if m:
            sym[name] = int(m.group(1), 16)
    rep["map_syms"] = {k: hex(v) for k, v in sym.items()}

    ubs = sym.get("updateBreakingState", R11.UBS_VA)
    ins = disasm(raw, segs, ubs, 0x120)
    rep["updateBreakingState_head"] = [
        [hex(a), m, o] for a, m, o in ins]

    # (a) state = &player->breaking : addiu $s?, $a0, IMM
    br_off = None
    for a, mn, op in ins:
        if mn == "addiu" and op.startswith("$s") and "$a0," in op:
            try:
                br_off = int(op.rsplit(",", 1)[1].strip(), 16)
                br_at = a
                break
            except ValueError:
                pass
    rep["breaking_off_addiu"] = None if br_off is None \
        else {"off": hex(br_off), "at": hex(br_at)}

    # (b) the latch store site: sw $zero run 0x6C..0x88 then result stores
    full = disasm(raw, segs, ubs, 0x530)
    store_site = None
    for k, (a, mn, op) in enumerate(full):
        if mn == "sw" and op.startswith("$zero,") and \
                op.endswith("($s0)") and \
                int(op.split(",")[1].split("(")[0], 16) == R11.BREAKING_OFF:
            run = full[k:k + 8]
            offs = [int(x[2].split(",")[1].split("(")[0], 16)
                    for x in run if x[1] == "sw" and "$zero," in x[2]]
            if offs == [0x6C, 0x70, 0x74, 0x78, 0x7C, 0x80, 0x84, 0x88]:
                store_site = full[k:k + 16]   # zeros + result re-stores
                break
    rep["store_site"] = [[hex(a), m, o] for a, m, o in (store_site or [])]
    rep["store_site_va"] = hex(store_site[0][0]) if store_site else None

    # (c) ticks_so_far += ONE at +0x74
    tick = [[hex(a), m, o] for a, m, o in full
            if mn_ok(m) and "0x74($s0)" in o and
            (m == "sw" or (m == "lw"))]
    rep["ticks_so_far_sites"] = tick[:6]

    # (d) playerInit inlined breakingStateReset
    pi = disasm(raw, segs, sym.get("playerInit", 0x80013954), 0x60)
    rep["playerInit_head"] = [[hex(a), m, o] for a, m, o in pi]

    # (e) call sites
    latch_calls = find_jal(raw, segs, ubs)
    rep["jal_updateBreakingState"] = [hex(c) for c in latch_calls]
    wrc = sym.get("worldRayCastIntersection")
    if wrc:
        rep["jal_worldRayCastIntersection"] = \
            [hex(c) for c in find_jal(raw, segs, wrc)]
    if latch_calls:
        c = latch_calls[0]
        rep["latch_call_context"] = [
            [hex(a), m, o]
            for a, m, o in disasm(raw, segs, c - 0x30, 0x50)]

    # verdict on the static extraction
    static_ok = (br_off == R11.BREAKING_OFF and store_site is not None
                 and R11.BREAKING_LAYOUT["block"] == br_off + 0x1C)
    rep["verdict"] = "LATCH_OFFSET_EXTRACTED" if static_ok else \
        "STATIC_MISMATCH"
    rep["breaking_off"] = hex(br_off) if br_off is not None else None
    rep["layout"] = {k: hex(v) for k, v in R11.BREAKING_LAYOUT.items()}
    return rep


def mn_ok(m):
    return m in ("lw", "sw")


# ------------------------------------------------------------------ live ----
def live_validate(ev):
    rep = {"mode": "live", "cue": CUE, "ws": WS}
    from ps1play.api import PS1Play
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    P = None
    for _ in range(240):
        P = O.player_ptr(p.mem)
        if P:
            break
        p.wait(30)
    if not P:
        rep["verdict"] = "INCONCLUSIVE: no player pointer"
        return rep
    p.wait(120)
    m, core = p.mem, p.core
    grab = core.frame_rgb

    stable_n, last_y = 0, None
    for _ in range(120):
        y = O.pos_of(m, P)[1]
        stable_n = stable_n + 1 if y == last_y else 0
        last_y = y
        if stable_n >= 45:
            break
        core.run(2, set())
    pos0 = O.pos_of(m, P)
    ev.png("l11_boot_world", grab())
    ev.j({"ev": "settled", "P": hex(P),
          "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos0]})

    wr = L.WorldReader(m)
    wr_info = None
    for _ in range(5):
        try:
            wr_info = wr.discover()
            break
        except RuntimeError as e:
            ev.j({"ev": "world_retry", "err": str(e)[:120]})
            core.run(60, set())
    if wr_info is None:
        rep["verdict"] = "INCONCLUSIVE: WorldReader discovery failed"
        return rep
    rep["world"] = wr_info
    rep["window_at_rest"] = R11.breaking_current(m, P)

    tracker = R11.RepeatLatchTracker(min_live=2)
    probe = R11.make_probe_fn(core, m, P, ev, wr, tracker)
    ref = O.pitch_now(m, P)
    step_raw = int(round(15.0 * L.DEG))
    down_ring, down_deg = R11.nearest_reachable_ring(ref, 90.0, step_raw)
    hor_ring, hor_deg = R11.nearest_reachable_ring(ref, 0.0, step_raw)
    fwd_ring, fwd_deg = R11.nearest_reachable_ring(ref, 20.0, step_raw)
    rep["ring_plan"] = {"ref_deg": round((ref % L.PITCH_MOD) / L.DEG, 2),
                        "down_deg": down_deg, "horizon_deg": hor_deg,
                        "forward_deg": fwd_deg}

    # V1: straight-down known-hit x3 (ALL at the same absolute ring)
    results = []
    for i in range(3):
        pr = probe(pdeg=90.0, target_ring=down_ring, tag=f"d{i}",
                   want_probe_rec=True)
        rec, a = pr["rec"], pr["parse"]
        ok, why = (False, "no live latch")
        if a["live"]:
            ok, why = L.validate_known_hit(a["hit"], rec["pos"],
                                           a["cam_y"])
        a["known_hit"] = {"ok": bool(ok), "why": why}
        cands, agree = R11.agree_with_diff_candidates(
            rec["mid"], rec["base"], P, a["cam_y"], rec["pos"])
        a["diff_cands_n"] = len(cands)
        a["static_in_diff_cands"] = bool(agree)
        if i == 0:
            ev.png("l11_down_view", grab())
        results.append(a)
        core.run(20, set())
    # V0: horizon negative — no latch within reach over the terrain
    pr0 = probe(pdeg=0.0, target_ring=hor_ring, tag="v0",
                want_probe_rec=True)
    v0 = pr0["parse"]
    v0_pass = not v0["live"]
    # V2: forward ~20deg — hit follows the aim (tracker variety)
    pr2 = probe(pdeg=20.0, target_ring=fwd_ring, tag="v2",
                want_probe_rec=True)
    a2 = pr2["parse"]
    ev.png("l11_v2_forward", grab())

    tr = tracker.verdict()
    v1_ok = [bool(r["known_hit"]["ok"]) for r in results]
    rep["validations"] = {
        "v1_aim_deg": [r.get("aim_deg") for r in results],
        "v1_hits": [r.get("hit") for r in results],
        "v1_world_ids": [r.get("world_id") for r in results],
        "v1_known_hit_ok": v1_ok,
        "v1_known_hit_why": [r["known_hit"]["why"] for r in results],
        "v1_world_arbitrated": [r.get("world_arbitrated") for r in results],
        "v1_reset_by_late": [r.get("reset_by_late") for r in results],
        "v1_ticks_grew": [r.get("ticks_grew") for r in results],
        "v1_held_mid": [r.get("held_mid") for r in results],
        "v1_static_in_diff_cands":
            [r.get("static_in_diff_cands") for r in results],
        "v1_pos_blocks": [r.get("pos_blocks") for r in results],
        "v0_negative_pass": bool(v0_pass),
        "v0_window": {k: v0[k] for k in ("hit", "block_ptr", "live")},
        "v2_forward": {k: a2.get(k) for k in ("ok", "hit", "world_id",
                                              "geom", "aim_deg")},
        "tracker": tr,
        "breaking_off": hex(R11.BREAKING_OFF)}
    validated = all(v1_ok) and v0_pass and tr["live"]
    rep["verdict"] = (
        "LATCH_OFFSET_VALIDATED: static window P+0x6C..0x8C is the "
        "CURRENT latch — 3/3 straight-down known-hit (in-column, "
        "world-arbitrated, reset-on-release), horizon negative clean, "
        "tracker live"
        if validated else "LATCH_OFFSET_BROKEN")
    ev.step("validations", rep["validations"])
    ev.finish(rep["verdict"])
    try:
        core.close()
    except Exception:                                    # noqa: BLE001
        pass
    return rep


def main():
    os.makedirs(OUT, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "--static"
    ev = Evid(OUT, "latch_offset")
    ev.jpath = os.path.join(OUT, "r11_latch_offset.jsonl")
    if mode == "--live":
        rep = live_validate(ev)
    else:
        rep = static_extract(ev)
        ev.j({"ev": "static_done", "verdict": rep["verdict"],
              "breaking_off": rep.get("breaking_off")})
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    print("[latch_offset]", mode, rep.get("verdict"))
    return 0 if "EXTRACTED" in rep.get("verdict", "") or \
        "VALIDATED" in rep.get("verdict", "") else 2


if __name__ == "__main__":
    sys.exit(main())

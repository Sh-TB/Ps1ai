#!/usr/bin/env python3
"""r22t3R_zenmai_anchor.py — r22t3-R RELAY: single-boot zenmai response anchor.

HARD-CAP: exactly 1 boot (counter r22t3R_boot_count.json, asserted in-script).
Disc: zenmai_lic_r21b.cue (r21 patch2 = game-side SIO handshake shim, DISCLOSED).

Recon corrections baked in (scratch/r22t3_zenmai/evidence.md Stage 2):
  * menu appears ~f630..f910 (screen mean ~31); boot1's f600 settle hit black
  * default menu cursor = 日本語; ENGLISH is BELOW -> press DOWN (not UP)
  * response-string scans exclude the loaded image (0x10000..0xBA800): static EN
    tables inside the EXE contain "West of House" etc. Require BSS (>0xBA800).
  * story_ram located via z3 header sig14 BSS-hit, else high-mem probe
    (pristine[0x5000:0x5040]) second hit.

Flow: menu detect+settle -> DOWN w/ VLM cursor verify (fallback UP, max 3) ->
START (retry x3) -> opening poll (BSS "West of House"/"Score: 0/0") -> anchors ->
type "look" (corrected T9 chords) -> VLM entry check (advisory) -> dense 1-frame
START submit window -> verify story bufs + 131B response in obuf -> PNG+VLM ->
same for "west" (154B "Forest") -> censuses + 2MB diffs + region dumps ->
report.json. Crash-safe: forensic census/PNG/report on ANY exception.
"""
import gzip
import json
import os
import shutil
import subprocess
import sys
import traceback

import numpy as np
from PIL import Image, ImageDraw

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)
from ps1play.core.host import LibretroCore  # noqa: E402
from ps1play.core.inputmap import (  # noqa: E402
    JP_B, JP_Y, JP_START, JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT,
    JP_A, JP_X, JP_L, JP_R)

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled",
             b"beetle_psx_override_bios": b"openbios"}
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/zenmai_lic_r21b.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WS = "/home/z/my-project/ps1ai/scratch/r22t3_zenmai/relay_ws"
OUT = "/home/z/my-project/ps1ai/scratch/r22t3_zenmai/relay_boot1"
BOOT_STATE = "/home/z/my-project/ps1ai/scratch/r22t3_zenmai/r22t3R_boot_count.json"
BOOT_MAX = 1  # relay task cap

# corrected T9 chords (evidence.md Stage 1; r21 map was wrong)
LETTERS = {
    "l": (JP_DOWN, JP_A),           # row '5jkl', col CIRCLE
    "o": (JP_L, JP_A),              # row '6mno' (L1 bank), col CIRCLE
    "k": (JP_DOWN, JP_X),           # row '5jkl', col TRIANGLE
    "w": (JP_RIGHT, JP_L, JP_Y),    # row '9wxyz' (L1+RIGHT), col SQUARE
    "e": (JP_UP, JP_X),             # row '3def', col TRIANGLE
    "s": (JP_LEFT, JP_L, JP_B),     # row '7pqrs' (L1+LEFT), col CROSS
    "t": (JP_UP, JP_L, JP_X),       # row '8tuv' (L1+UP), col TRIANGLE
}

Z3_HDR_SIG = bytes.fromhex("00774b5450d5389903e602b02c12")   # z3[2:16], rel 119
OPENING_BANNER = b"ZORK I: The Great Underground Empire"
LOOK_RESP = (b"West of House\nYou are standing in an open field west of a white "
             b"house, with a boarded front door.\nThere is a small mailbox here."
             b"\n\n>")
WEST_RESP = (b"Forest\nThis is a forest, with trees in all directions. To the "
             b"east, there appears to be sunlight.\nYou hear in the distance the "
             b"chirping of a song bird.\n\n>")
assert len(LOOK_RESP) == 131 and len(WEST_RESP) == 154
IMAGE_END = 0xBA800          # t_addr(0x80010000)+t_size(0xAA800): image ends here
DYN_END = 0x2C12             # z3 staticmem addr (dynamic memory size)
TEXT_BUF, PARSE_BUF, ECHO_BUF, G0 = 0x27E8, 0x251E, 0x2862, 0x2B0
PARSE_LOOK = bytes.fromhex("0142160401")
PARSE_WEST = bytes.fromhex("014aa50401")

R = {"patch": "r21 padtest SIO handshake shim (disclosed game-side patch, "
              "zenmai_lic_r21b disc)",
     "boot_cap": BOOT_MAX, "recon_basis": "evidence.md Stage 2",
     "phases": {}, "anchors": {}, "verify": {}, "vlm": {}}
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "run_log.txt"), "w")
SNAPS = {}
S = O = SB = HP = None


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n")
    LOG.flush()


def png(tag, label=None):
    arr = core.frame_rgb()
    if arr is not None:
        Image.fromarray(arr).save(os.path.join(OUT, f"{tag}.png"))
        if label:  # labeled copy
            im = Image.fromarray(arr).convert("RGB")
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, im.width, 14], fill=(0, 0, 0))
            d.text((3, 2), label, fill=(255, 255, 80))
            im.save(os.path.join(OUT, f"lbl_{tag}.png"))
    return arr


def census(tag):
    a = core.ram.copy()
    np.savez_compressed(os.path.join(OUT, f"census_{tag}.npz"), ram=a)
    return a


def find(ram: bytes, pat: bytes, limit=16, min_off=0):
    hits, i = [], min_off
    while len(hits) < limit:
        j = ram.find(pat, i)
        if j < 0:
            break
        hits.append(j)
        i = j + 1
    return hits


def find_u16(ram: bytes, chars: str, limit=16, min_off=0):
    arr = np.frombuffer(ram, np.uint16)
    seq = np.array([ord(c) for c in chars], np.uint16)
    w = np.lib.stride_tricks.sliding_window_view(arr, len(seq))
    idx = np.flatnonzero((w == seq).all(axis=1))
    return [int(k) * 2 for k in idx if int(k) * 2 >= min_off][:limit]


def diff_ranges(a, b, min_gap=4, maxr=400):
    d = np.flatnonzero(np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8))
    if len(d) == 0:
        return [], 0
    ranges, s, p = [], int(d[0]), int(d[0])
    for x in d[1:]:
        x = int(x)
        if x - p > min_gap:
            ranges.append((s, p + 1))
            s = x
        p = x
    ranges.append((s, p + 1))
    return ranges[:maxr], int(len(d))


def vlm(paths, prompt, tag, timeout=150):
    args = ["z-ai", "vision", "-p", prompt, "-o",
            os.path.join(OUT, f"vlm_{tag}.json")]
    for p in paths:
        args += ["-i", p]
    try:
        subprocess.run(args, capture_output=True, timeout=timeout)
        d = json.load(open(os.path.join(OUT, f"vlm_{tag}.json")))
        c = str(d["choices"][0]["message"]["content"]).strip()
    except Exception as e:                                    # noqa: BLE001
        log("vlm fail", tag, repr(e))
        c = ""
    R["vlm"][tag] = c
    log(f"VLM[{tag}]:", c[:400].replace("\n", " | "))
    return c


def snap():
    ram = core.ram
    SNAPS[core.frames_run] = {
        "dyn": bytes(ram[S:S + DYN_END]) if S else b"",
        "obuf": bytes(ram[O:O + 4096]) if O else b"",
        "sbuf": bytes(ram[SB:SB + 64]) if SB else b""}
    return core.frames_run


def dump_regions(ram, tag):
    if S:
        gzip.open(os.path.join(OUT, f"story_dyn_{tag}.bin.gz"), "wb").write(
            bytes(ram[S:S + 0x2C40]))
    if O:
        gzip.open(os.path.join(OUT, f"obuf_{tag}.bin.gz"), "wb").write(
            bytes(ram[O:O + 12288]))
    if HP:
        gzip.open(os.path.join(OUT, f"hpool_{tag}.bin.gz"), "wb").write(
            bytes(ram[HP:HP + 98304]))
    if SB:
        open(os.path.join(OUT, f"statusbuf_{tag}.txt"), "wb").write(
            bytes(ram[SB:SB + 49]))


def type_word(word, hold):
    """Corrected T9 chords: row dir held, then face chord, then release."""
    for ch in word:
        btns = set(LETTERS[ch])
        dirb = {b for b in btns if b in (JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT, JP_L)}
        face = btns - dirb
        core.run(2, set())
        core.run(hold, dirb)
        core.run(hold, dirb | face)
        core.run(2, set())
        log(f"  typed {ch!r} f={core.frames_run} hold={hold}")


def dense_submit(label):
    """START edge with 1-frame granularity; response lands in obuf same frame."""
    core.run(1, set()); snap()
    for _ in range(2):
        core.run(1, {JP_START}); snap()
    for _ in range(8):
        core.run(1, set()); snap()
    keys = sorted(SNAPS)
    per = []
    for i in range(1, len(keys)):
        a, b = SNAPS[keys[i - 1]], SNAPS[keys[i]]
        rd = {"f": keys[i]}
        if a["dyn"] and b["dyn"]:
            rd["dyn_ranges"], _ = diff_ranges(a["dyn"], b["dyn"], maxr=24)
        if a["obuf"] and b["obuf"]:
            rd["obuf_ranges"], _ = diff_ranges(a["obuf"], b["obuf"], maxr=12)
        per.append(rd)
    R["phases"][label] = per
    changed = [p["f"] for p in per if p.get("dyn_ranges") or p.get("obuf_ranges")]
    log(f"{label}: changed frames {changed[:8]}")
    return changed


def save_snaps(tag):
    json.dump({str(k): {kk: vv.hex() for kk, vv in v.items()}
               for k, v in SNAPS.items()},
              open(os.path.join(OUT, f"snap_{tag}.json"), "w"))
    SNAPS.clear()


def forensic(tag):
    """Crash forensics: census + PNG + report no matter what (1-boot task)."""
    try:
        np.savez_compressed(os.path.join(OUT, f"census_{tag}.npz"),
                            ram=core.ram.copy())
        png(f"crash_{tag}", f"FAIL {tag} f={core.frames_run}")
        R["crash"] = {"tag": tag, "frame": core.frames_run}
        json.dump(R, open(os.path.join(OUT, "report.json"), "w"), indent=1,
                  ensure_ascii=False, default=str)
    except Exception as e:                                    # noqa: BLE001
        log("forensic dump failed", repr(e))


# ---- boot hard-cap -----------------------------------------------------------
boots = 1
if os.path.exists(BOOT_STATE):
    boots = json.load(open(BOOT_STATE))["boots"] + 1
assert boots <= BOOT_MAX, f"relay boot cap reached ({boots - 1}/{BOOT_MAX})"
json.dump({"boots": boots, "max": BOOT_MAX}, open(BOOT_STATE, "w"))
log(f"RELAY BOOT {boots}/{BOOT_MAX} (hard-cap asserted)")

WS_ = os.path.join(OUT, "ws_system")
os.makedirs(WS_, exist_ok=True)
shutil.copyfile("/home/z/my-project/ps1ai/third_party/openbios/openbios.bin",
                os.path.join(WS_, "openbios.bin"))
core = LibretroCore(CORE, WS_, os.path.join(OUT, "ws_saves"),
                    var_overrides=OVERRIDES)
core.load_game(CONTENT)

try:
    # ---- P0: menu detect (mean 3..60 stable; black=0, license=~104 excluded) --
    menu_f = None
    stable = 0
    while core.frames_run < 3600:
        core.run(10, set())
        arr = core.frame_rgb()
        m = float(arr.mean()) if arr is not None else 0.0
        stable = stable + 1 if (3.0 < m < 60.0) else 0
        if stable >= 3 and core.frames_run > 300:
            menu_f = core.frames_run - 30
            break
    assert menu_f is not None, "menu never appeared (3600f)"
    png("p0_menu", f"menu f={core.frames_run}")
    log("P0 menu visible ~f", menu_f, "(png f", core.frames_run, ")")

    # settle: wait for the menu scroll animation to pause
    core.run(90, set())
    last = -1.0
    calm = 0
    for _ in range(40):
        core.run(10, set())
        arr = core.frame_rgb()
        m = float(arr.mean()) if arr is not None else last
        calm = calm + 1 if abs(m - last) < 1.5 else 0
        last = m
        if calm >= 3:
            break
    log("menu settled f=", core.frames_run)

    # opening already running? (menu detector can fire on dark screens)
    ram0 = core.ram.tobytes()
    if find(ram0, b"West of House", min_off=IMAGE_END):
        log("opening ALREADY running at menu-detect f", core.frames_run)
        R["phases"]["menu_skipped_opening_live"] = True
    else:
        # ---- P1: select ENGLISH (DOWN from 日本語; VLM-verified, fallbacks) ----
        sel = "unverified"
        for attempt, (key, kname, hold) in enumerate(
                [(JP_DOWN, "DOWN", 4), (JP_UP, "UP", 4), (JP_DOWN, "DOWN6", 6)]):
            core.run(2, set())
            core.run(hold, {key})
            core.run(50, set())
            tag = f"p1_select_{attempt}_{kname.lower()}"
            png(tag, f"after {kname} f={core.frames_run}")
            c = vlm([os.path.join(OUT, f"{tag}.png")],
                    "PS1 language menu with rows '日本語' (Japanese) and 'ENGLISH'. "
                    "Which row has the selection cursor '>' or highlight on it "
                    "right now? Answer exactly one word: NIHONGO or ENGLISH or "
                    "UNCLEAR.", f"cursor_{attempt}")
            head = c.upper()[:80]
            if "ENGLISH" in head and "NIHONGO" not in head:
                sel = f"english_via_{kname}"
                break
            if "UNCLEAR" in head or c == "":
                sel = f"unclear_after_{kname}"
                continue
            sel = f"nihongo_after_{kname}"
        R["phases"]["menu_select"] = sel
        log("P1 selection:", sel)

        # ---- P2: START -> opening (retry x3; later STARTs harmless if clen==0) --
        opening_f = None
        for attempt in range(3):
            core.run(2, set())
            core.run(4, {JP_START})
            for _ in range(120):
                core.run(10, set())
                ramb = core.ram.tobytes()
                if find(ramb, b"West of House", min_off=IMAGE_END) or \
                   find(ramb, b"Score: 0/0", min_off=IMAGE_END):
                    opening_f = core.frames_run
                    break
            if opening_f:
                break
            log(f"START attempt {attempt + 1}: no opening, retrying")
        assert opening_f is not None, "opening never appeared after 3 STARTs"
    R["phases"]["opening_f"] = opening_f
    core.run(150, set())                       # opening scroll settle
    A = census("pre_look")
    png("p2_opening", f"opening f={core.frames_run}")
    log("P2 opening confirmed f=", opening_f, "; census at f", core.frames_run)
    try:                                       # insurance checkpoint
        st = core.serialize()
        open(os.path.join(OUT, "state_opening.bin"), "wb").write(st)
        log("savestate", len(st), "bytes")
    except Exception as e:                     # noqa: BLE001
        log("savestate failed", repr(e))

    # ---- anchors ----------------------------------------------------------------
    ram_b = A.tobytes()
    P = None
    sig_hits = find(ram_b, Z3_HDR_SIG)
    log("z3 sig14 hits:", [hex(h) for h in sig_hits])
    bss_sig = [h for h in sig_hits if h > IMAGE_END]
    if bss_sig:
        S = bss_sig[0] - 2
    else:
        S = None
    for h in sig_hits:
        if h == 0xA4FA2:
            P = h - 2
    if S is None and P is not None:
        for off in (0x5000, 0x8000, 0x3000):
            probe = ram_b[P + off:P + off + 64]
            h2 = [h for h in find(ram_b, probe)
                  if not (P <= h < P + 0x2C40)]
            log(f"highmem probe z3[{off:#x}] hits:", [hex(h) for h in h2])
            if len(h2) == 1 and h2[0] > IMAGE_END:
                S = h2[0] - off
                break
    if S is not None:
        assert ram_b[S:S + 2] == b"\x03\x00", "story_ram version bytes"
        R["anchors"].update({
            "story_ram": hex(0x80000000 + S),
            "textbuf": hex(0x80000000 + S + TEXT_BUF),
            "parsebuf": hex(0x80000000 + S + PARSE_BUF),
            "echobuf": hex(0x80000000 + S + ECHO_BUF),
            "globals_G0": hex(0x80000000 + S + G0)})
        log("story_ram @", hex(S), "VA", hex(0x80000000 + S))
    else:
        log("story_ram NOT FOUND — degraded anchors (obuf/statusbuf only)")
    ban = [h for h in find(ram_b, OPENING_BANNER) if h > IMAGE_END]
    O = ban[0] if ban else None
    if O is not None:
        R["anchors"]["obuf"] = hex(0x80000000 + O)
        log("obuf @", hex(O), "head:", ram_b[O:O + 80])
    sc = [h for h in find(ram_b, b"Score: 0/0") if h > IMAGE_END]
    if sc:
        w = ram_b.rfind(b"West of House", max(0, sc[0] - 40), sc[0])
        SB = w if w >= 0 else sc[0] - 20
        R["anchors"]["statusbuf"] = hex(0x80000000 + SB)
        log("statusbuf @", hex(SB), ":", ram_b[SB:SB + 49])
    hp = find_u16(ram_b, "West of House", min_off=IMAGE_END)
    HP = hp[0] if hp else None
    if HP:
        R["anchors"]["hpool_hit"] = hex(0x80000000 + HP)
        log("hpool glyph hit @", hex(HP))
    if S:
        log("textbuf pre :", ram_b[S + TEXT_BUF:S + TEXT_BUF + 12].hex())
        log("parse  pre :", ram_b[S + PARSE_BUF:S + PARSE_BUF + 8].hex())
        log("G0 pre     :", ram_b[S + G0:S + G0 + 2].hex())
    R["anchors"]["pristine_story"] = (hex(0x80000000 + P)
                                      if P is not None else None)
    R["phases"]["look_resp_count_pre"] = len(find(ram_b, LOOK_RESP,
                                                  min_off=IMAGE_END))
    R["phases"]["west_resp_count_pre"] = len(find(ram_b, WEST_RESP,
                                                  min_off=IMAGE_END))
    R["phases"]["statusbuf_pre"] = (ram_b[SB:SB + 49].decode("latin1")
                                    if SB else None)
    dump_regions(A, "pre_look")

    # ---- look (retry: garbage-submit clears entry, retype with longer hold) ----
    look_ok = False
    look_new_hit = None
    E = core.ram
    for rnd, hold in enumerate((2, 4, 6), start=1):
        if rnd > 1:                    # submit clears entry (error or no-op)
            core.run(2, set()); core.run(4, {JP_START}); core.run(120, set())
            log(f"look round {rnd}: entry cleared via submit")
        type_word("look", hold)
        B = census(f"pre_submit_look_r{rnd}")
        dump_regions(B, f"pre_submit_look_r{rnd}")
        png(f"p3_look_typed_r{rnd}", f"look typed r{rnd} f={core.frames_run}")
        vlm([os.path.join(OUT, f"p3_look_typed_r{rnd}.png")],
            "Zork I PS1 screen, bottom entry line starts with '>'. Transcribe "
            "EXACTLY the characters after '>' on the bottom line (English "
            "letters, kana, or empty). Answer as JSON: {\"entry\":\"...\"}",
            f"entry_look_r{rnd}")
        changed = dense_submit(f"p4_look_r{rnd}_frames")
        core.run(200, set())
        C = census(f"post_look_r{rnd}")
        cb = C.tobytes()
        pre = find(B.tobytes(), LOOK_RESP, min_off=IMAGE_END)
        post = find(cb, LOOK_RESP, min_off=IMAGE_END)
        new = [h for h in post if h not in pre]
        v = {"round": rnd, "hold": hold, "changed_frames": changed[:8],
             "pre_hits": [hex(h) for h in pre],
             "post_hits": [hex(h) for h in post],
             "new_hit": hex(new[0]) if new else None,
             "new_hit_frame": core.frames_run}
        if S:
            v["textbuf"] = cb[S + TEXT_BUF:S + TEXT_BUF + 8].decode(
                "latin1", "replace")
            v["textbuf_ok"] = cb[S + TEXT_BUF + 1:S + TEXT_BUF + 6] == b"look\x00"
            v["parse"] = cb[S + PARSE_BUF:S + PARSE_BUF + 6].hex()
            v["parse_ok"] = cb[S + PARSE_BUF + 1:S + PARSE_BUF + 6] == PARSE_LOOK
            v["echo"] = cb[S + ECHO_BUF:S + ECHO_BUF + 6].decode("latin1",
                                                                 "replace")
            v["echo_ok"] = cb[S + ECHO_BUF:S + ECHO_BUF + 4] == b"look"
            v["G0"] = cb[S + G0:S + G0 + 2].hex()
            dd, dn = diff_ranges(B.tobytes()[S:S + DYN_END],
                                 cb[S:S + DYN_END], maxr=40)
            v["story_dyn_diff_ranges"] = dd[:24]
            v["story_dyn_diff_bytes"] = dn
        if SB:
            v["statusbuf"] = cb[SB:SB + 49].decode("latin1", "replace")
        if HP:
            v["hpool_new_glyph_hits"] = len([h for h in find_u16(
                cb, "West of House", min_off=IMAGE_END) if h > HP + 4096])
        R["verify"][f"look_r{rnd}"] = v
        log(f"LOOK r{rnd}:", json.dumps(v, default=str)[:1400])
        if new:
            look_ok = True
            look_new_hit = new[0]
            R["verify"]["look"] = v
            png("p4_look_response", f"look response f={core.frames_run}")
            break
        log(f"look r{rnd}: 131B signature NOT found; retries left", 3 - rnd)

    R["verify"]["look_signature_found"] = look_ok
    R["verify"]["look_sig_addr"] = (hex(0x80000000 + look_new_hit)
                                    if look_new_hit else None)
    save_snaps("look")

    # ---- west ---------------------------------------------------------------------
    west_ok = False
    west_new_hit = None
    for rnd, hold in enumerate((2, 4), start=1):
        if rnd > 1:
            core.run(2, set()); core.run(4, {JP_START}); core.run(120, set())
        type_word("west", hold)
        D = census(f"pre_submit_west_r{rnd}")
        dump_regions(D, f"pre_submit_west_r{rnd}")
        png(f"p5_west_typed_r{rnd}", f"west typed r{rnd} f={core.frames_run}")
        changed = dense_submit(f"p6_west_r{rnd}_frames")
        core.run(200, set())
        E = census(f"post_west_r{rnd}")
        eb = E.tobytes()
        pre = find(D.tobytes(), WEST_RESP, min_off=IMAGE_END)
        post = find(eb, WEST_RESP, min_off=IMAGE_END)
        new = [h for h in post if h not in pre]
        v = {"round": rnd, "hold": hold, "changed_frames": changed[:8],
             "pre_hits": [hex(h) for h in pre],
             "post_hits": [hex(h) for h in post],
             "new_hit": hex(new[0]) if new else None,
             "new_hit_frame": core.frames_run}
        if S:
            v["textbuf"] = eb[S + TEXT_BUF:S + TEXT_BUF + 8].decode(
                "latin1", "replace")
            v["textbuf_ok"] = eb[S + TEXT_BUF + 1:S + TEXT_BUF + 6] == b"west\x00"
            v["parse"] = eb[S + PARSE_BUF:S + PARSE_BUF + 6].hex()
            v["parse_ok"] = eb[S + PARSE_BUF + 1:S + PARSE_BUF + 6] == PARSE_WEST
            v["echo_ok"] = eb[S + ECHO_BUF:S + ECHO_BUF + 4] == b"west"
            v["G0_pre_post"] = (D[S + G0:S + G0 + 2].hex(),
                                eb[S + G0:S + G0 + 2].hex())
        if SB:
            v["statusbuf"] = eb[SB:SB + 49].decode("latin1", "replace")
            v["statusbuf_has_Forest"] = b"Forest" in eb[SB:SB + 49]
        R["verify"][f"west_r{rnd}"] = v
        log(f"WEST r{rnd}:", json.dumps(v, default=str)[:1400])
        if new:
            west_ok = True
            west_new_hit = new[0]
            R["verify"]["west"] = v
            png("p6_west_response", f"west response f={core.frames_run}")
            break
    R["verify"]["west_signature_found"] = west_ok
    R["verify"]["west_sig_addr"] = (hex(0x80000000 + west_new_hit)
                                    if west_new_hit else None)
    save_snaps("west")
    dump_regions(E, "final")
    R["phases"]["total_frames"] = core.frames_run

    # ---- VLM corroboration ----------------------------------------------------------
    vlm([os.path.join(OUT, "p2_opening.png")],
        "Transcribe ALL text on this Zork I PS1 screen including the top status "
        "bar and the bottom entry line.", "opening")
    if look_ok:
        vlm([os.path.join(OUT, "p4_look_response.png")],
            "Transcribe ALL text on this Zork I PS1 screen including the top "
            "status bar and the bottom entry line.", "look_response")
    if west_ok:
        vlm([os.path.join(OUT, "p6_west_response.png")],
            "Transcribe ALL text on this Zork I PS1 screen including the top "
            "status bar and the bottom entry line. What is the room name in the "
            "status bar?", "west_response")

    json.dump(R, open(os.path.join(OUT, "report.json"), "w"), indent=1,
              ensure_ascii=False, default=str)
except Exception:
    log("RELAY BOOT FAILED:")
    log(traceback.format_exc())
    forensic("exception")
    raise
finally:
    try:
        core.shutdown()
    except Exception as e:                                    # noqa: BLE001
        log("shutdown:", repr(e))
    LOG.close()

print("relay boot done:", json.dumps(
    {"look": look_ok, "west": west_ok,
     "look_addr": R["verify"].get("look_sig_addr"),
     "west_addr": R["verify"].get("west_sig_addr"),
     "frames": R["phases"].get("total_frames")}), flush=True)

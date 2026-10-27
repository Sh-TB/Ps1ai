#!/usr/bin/env python3
"""r21_closeout.py — orchestrator close-out for the two deadline-hit trains (r21t3, r21t5).

1. Build docs/evidence_gifs/r21t5_airhockey_gates.gif from scratch/r21t5_airhockey/gif_frames/
2. Re-add the autogaz r21t2 entry (lost to a concurrent-manifest write race) and add the
   zenmai (r21t3) + air_hockey (r21t5) entries to data/homebrew/manifest.json round21_addendum.
"""
import glob
import json
import os
import re

import PIL.Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# ---------------------------------------------------------------- 1. GIF
frames = sorted(glob.glob("scratch/r21t5_airhockey/gif_frames/f*.png"),
                key=lambda p: int(re.search(r"f(\d+)", p).group(1)))
assert frames, "no gif frames found"
ims = [PIL.Image.open(p).convert("P", palette=PIL.Image.ADAPTIVE) for p in frames]
out = "docs/evidence_gifs/r21t5_airhockey_gates.gif"
os.makedirs(os.path.dirname(out), exist_ok=True)
ims[0].save(out, save_all=True, append_images=ims[1:], duration=90, loop=0, optimize=True)
size = os.path.getsize(out)
print(f"GIF {out}: {len(ims)} frames, {size} bytes")

# ------------------------------------------------------------ 2. manifest
MP = "data/homebrew/manifest.json"
man = json.load(open(MP))
r21 = man.setdefault("round21_addendum", {})

r21["autogaz_input"] = {
    "date": "2026-10-28",
    "verdict": "INPUT_RESPONSIVE — PROVEN (upgrades r20 BOOTED_TITLE / INPUT_UNPROVEN)",
    "root_cause": ("r20's sweep never pressed ps1play 'B' = PSX CROSS, the only acting "
                   "button at state 0; autogaz is a 4-state meme slideshow "
                   "(CIRCLE acts only at state 3, unreachable without CROSS)"),
    "evidence_chain": ("boot2 f1301 CROSS held -> game padbuf u32 @0x800BE548 flips "
                       "0xFFFFFFFF->0xFFFFFFBF same frame; state @0x800BC7EC 0->1->2; "
                       "screen MAD 121.3->133.7 neutral->smiling meme (VLM); f1778 "
                       "state 2->3 at timerVal @0x800BC7F0 == 476 exactly (source const); "
                       "f1779 CIRCLE -> state 3->0, screen MAD 0.0 vs baseline = REVERSAL "
                       "proven; SQUARE probe no-op (source-consistent)"),
    "re_findings": ("PadRead @0x80017a88 returns ~(u32)@0x800BE548 inverted/active-high; "
                    "andi 0x40=CROSS, andi 0x20=CIRCLE; Timer @0x80010b18=476; PadInit "
                    "@0x80017a3c via B0-stubs (corrects r20 'zero BIOS calls' scan "
                    "artifact); kernel padbuff 0xB008 is static-init only, never flips - "
                    "live buffer is the game's libpad @0x800BE548"),
    "runs": "2/2 boots used",
    "evidence": "scratch/r21t2_autogaz/ (6.6MB: evidence.md, report.json, 31 PNGs, vlm_stages.json, RAM dumps)",
    "scripts": "scripts/r21t2_re_scan.py, r21t2_autogaz_input.py, r21t2_autogaz_input2.py",
}

r21["zenmai_input"] = {
    "date": "2026-10-28",
    "verdict": ("INPUT_RESPONSIVE at menu level, under a DISCLOSED game-side SIO "
                "handshake patch; RUNNING not claimed (command->world response unproven)"),
    "root_cause": ("zenmai pad_exchange() bit-bangs SIO with NO dummy JOY_DATA read; "
                   "beetle/mednafen arms ReceivePending exclusively on a JOY_DATA READ "
                   "(frontio.c) -> zenmai's 2000-iter wait on STAT&2 times out on byte 0 "
                   "-> pad_read()==-1 forever (source-verified vs plat_ps1.c v1.5.0)"),
    "patch": ("patch1 @VA 0x8001B370 dummy-read (input stayed dead, CTRL=0x1003 no RXEN); "
              "patch2 grafts the r20-verified padtest recipe: CTRL=0 -> 0x1007 "
              "(TXEN|DTR|RXEN) -> dummy read drain+arm -> TX 01/42/00/00/00 -> "
              "RX ff/41/5A/SW1/SW2"),
    "evidence_chain": ("boot2: UP pulse screen MAD 7.14 (cursor); START @f1152 menu -> "
                       "next state (VLM); per-keystroke typing l/o/o/k + w/e/s/t + l/o/o/k "
                       "with submit; responses 0 RAM-delta bytes, Z-machine completion "
                       "buffer not found -> command->world loop UNPROVEN"),
    "runs": "2/2 boots used (boot1 patch1 dead, boot2 patch2 responsive)",
    "evidence": "scratch/r21t3_zenmai/ (evidence.md, report.json, 28 PNGs, VLM jsons, ram npys)",
    "scripts": "scripts/r21t3_zenmai_patch.py, r21t3_zenmai_patch2.py, r21t3_zenmai_input2.py, r21t3_zenmai_input3.py",
    "close_out": "orchestrator close-out (sub-agent hit deadline pre-worklog; graded from disk)",
}

r21["airhockey_gates"] = {
    "date": "2026-10-28",
    "verdict": "RUNNING (upgrades r20 TITLE_INTERACTIVE)",
    "button_bitmap": ("u16 BE active-low @0x09FF5A proven per button, 3f pulses, "
                      "pad_flip_ok all: SELECT 0xFFFE/START 0xFFF7/UP 0xFFEF/"
                      "DOWN 0xFFBF/LEFT 0xFF7F (fixes r20's unverified mask word)"),
    "gate_map": ("title -START-> GAME START highlighted -CROSS-> Player Select "
                 "(Thunder Boy, 1P) -CROSS-> confirm -CIRCLE-> loading -> FIGHT ME! -> "
                 "LIVE_MATCH (VS screen THUNDER BOY vs LITTLE MANIA); all legal inputs, "
                 "VLM-gated every step"),
    "paddle_candidates": ("0x800A148A sL+63/sR-63 anti-symmetric (0->64); 0x800A148E "
                          "sL+46/sR-74; run4 corr 0.555 @0x800A14F8 - candidates only, "
                          "not VLM-anchored -> PLAYING not claimed"),
    "runs": ("4-5 boots - EXCEEDED the 2-boot cap (disclosed); deadline hit "
             "pre-close-out; graded from disk by orchestrator"),
    "evidence": "scratch/r21t5_airhockey/ (evidence.md, run/run4/run5 logs, 34 VLM jsons, labeled PNGs, gif_frames x47)",
    "scripts": "scripts/r21t5_airhockey_causality.py, _run3.py, _run4.py, _run5.py",
    "gif": "docs/evidence_gifs/r21t5_airhockey_gates.gif",
}

json.dump(man, open(MP, "w"), indent=2, ensure_ascii=False)
open(MP, "a").write("\n")
print("manifest round21_addendum keys:", list(r21.keys()))

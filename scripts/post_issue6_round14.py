#!/usr/bin/env python3
"""post_issue6_round14.py — the honest round-14 report on Issue #6."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req

REPO = "Sh-TB/Ps1ai"
BODY = """## Round 14 — the honest correction + REAL gameplay (user was right)

### 1. The round-13 showcase GIF is RETRACTED

The user audited `hello_pong_complete_gameplay.gif` and called it out: *"the ball just moves — nobody is playing."* A frame-by-frame re-audit ([`scripts/audit_pong_gif.py`](../tree/main/scripts/audit_pong_gif.py)) confirms every word:

| metric | r13 "gameplay" GIF | reality |
|---|---|---|
| player-paddle y-range | [160, 160] | **never moved (std 0.0)** |
| paddle move-steps (>4px) | **0** | decorative wiggle was dead code (`wig_fn` offsets 80..340 vs per-batch `k` in 0..59 — never fired) |
| ball interception rate | **0%** | mean paddle-ball distance 64px |
| the "5-x win" | zero-input walkover | beetle reports 2 pads -> the game's AI never activates -> the right paddle is a static dummy |

**Running ≠ playing.** The r11/r12 "WIN_CAUSAL" claims on this game are reclassified: they measured the walkover, not play. The criticism is accepted in full.

### 2. REAL play, same game, this round — GIF: https://h.uguu.se/VmqXgChs.gif

[`scripts/r14_hellopong_real.py`](../tree/main/scripts/r14_hellopong_real.py):
- **The game's own AI activated**: libretro port 1 disconnected (`set_port_device(RETRO_DEVICE_NONE, port=1)`) -> upstream `AI for right paddle if no controller` runs (verified: 38 tracking events in 240 frames, right paddle follows the ball).
- **A 60 Hz closed-loop servo** drives the left paddle (screen ball centroid + paddle row -> UP/DOWN).
- Result over 9,000 captured frames: **117 paddle move-steps, genuine catches (continuous window @f2004: ball y=172 inside paddle span [151,211]), 0 misses, RAM-anchored score 0x1FFEB4 = 0-0 the whole run** — a real, endless rally against the game's own AI. Both paddles visibly track the ball the entire GIF.

### 3. Why there is no "WIN 5-x" — the AI is unbeatable by design

From the upstream source ([`src/main.c`](../blob/main/docs/evidence/round14/hellopong_upstream_main.c), MIT):
- AI paddle speed = `PADDLE_SPEED-1` = **3 px/frame** — exactly the ball's clamped max `|vel_y|` = **3**
- deadband ±10 px, paddle 60 px tall, and the ball sits inside the paddle plane for ~10 frames
- No return angle can outrun it (aim control exists — `vel_y += hit_pos/15` — but the ceiling equals the AI's speed). Winning 5-x vs this AI is impossible; **every 5-x on this game is a static-dummy walkover.** Honest verdict: `REAL_PLAY_ETERNAL_RALLY` (returns + 0 misses vs the game's own AI).

### 4. psxBreakout (the new tiny game): boot campaign, status BLOCKED

- **OpenBIOS single-read cap measured**: `loadExe()` issues one `dev_cd_read()` for the whole exe body and ignores failures; the kernel CD path delivers at most **16 sectors (0x8000 B) per call** (empirical cliff: t_size 0x8000 boots fine, 0x9000 truncates at exactly 32,768). cs50x.exe needs 38 sectors.
- A hand-assembled, capstone-verified **stage-1 loader** (≤2 KB, spin-flag + self-copy designs) was built and tested through 5 disc recipes (r14_stage1*, scratch, padloader, exploit v1/v2).
- **Open anomaly**: the kernel boot phase serves *stale hello_pong_lic.bin original bytes* for some sectors (root/CNF/exe-header show hello_pong's original values regardless of the on-disc bytes) while other sectors (e.g. LBA 27) arrive real. LD_PRELOAD syscall tracing + atime forensics prove the emulator process opens **only** the target image; the stale bytes exist nowhere on disk or in the core. The psyqo shell (disc checker) reads the real disc; the kernel phase does not. Full saga + repro: [`docs/evidence/round14/psxbreakout_boot_saga.txt`](../blob/main/docs/evidence/round14/psxbreakout_boot_saga.txt).
- Next levers: instrument beetle-psx itself; minimal-repro issue upstream.

### 5. Housekeeping

- Commit: `1a3b1d8` (pushed via the Git Data API — the fine-grained token's git-HTTPS path refuses while Contents RW works over REST).
- Evidence: `docs/evidence/round14/` (audit record, match report, AI-tracking PNG, catch-window frames, boot saga, upstream source copy).
- No game bytes in VCS; suite untouched (additive scripts only).
"""


def main():
    s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
               payload={"body": BODY})
    print("status:", s)
    print("comment:", (d or {}).get("html_url") or str(d)[:200])


if __name__ == "__main__":
    main()

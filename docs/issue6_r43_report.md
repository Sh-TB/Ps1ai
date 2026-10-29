# Issue #6 — R43 report (the 40% track, mspsx): the recorded 1-boot win regression — VERIFIED, deterministic parity with the r35 win

Commit at execution: `3522ef2` (the R42 60%-track round) · script `scripts/r43_mspsx_regression.py` · evidence `data/games/homebrew/mspsx/r43/` (report + boot ledger cap 1/1) · win PNG local-only (`scratch/r43_mspsx/r43_mspsx_win.png`, game bytes never committed).

## What ran

The mspsx capsule's recorded lever — *"next mspsx round = the r35 win regression, 1 boot, when the 60/40 budget allocates it"* — executed exactly as recorded:

1. **Disc rebuild disclosed first**: the `mspsx_lic` disc was absent (the documented filesystem rollback had removed `patched/` for this title). Per the internet-first rule the pristine v0.1 release was **re-fetched from upstream** (`github.com/AcidGunner/MSPSX` release v0.1) and **sha256-verified byte-identical** to the r22/r23-verified pristine (`d35a189b…a4c5fa`, 117,891,648 B); the licensed image was rebuilt with **16 license sectors from the user's own retail MSX disc**, EXE payload untouched (`scripts/r29t0_mspsx_asset.py`, zero boots).
2. **1 cold boot** → title wait (pad live at f=542) → START → fresh board at f=605 (BOARD nonzero + CTRLDIS 0).
3. **The r35c adaptive reveal loop** (RAM board decode → nearest unrevealed safe cell, zero-adjacency floods preferred → verified taps → CROSS 40f hold → per-click REVT/flood verification, decode-bug abort armed).

## Oracle result — the capsule oracle held exactly

| metric | r35 baseline (docs/issue6_r35_report.md) | R43 regression |
|---|---|---|
| clicks | 59 | **59** |
| swallowed taps | 0 | **0** |
| navigation failures | 0 | **0** |
| sim fallbacks | — | **0** |
| REVT trace | 0→160 monotone | **0→160 monotone** |
| final board | revealed 160 / mines 32 | **revealed 160 / mines 32 / auto-flagged 32** |
| win watch | 180f frame-diff + RAM window | **180f, max_frame_diff 4.254** + RAM window (`0x18cd8=160`, `0x18cdc=160`, flags word set) |

**`WIN_REGRESSION_VERIFIED`** — deterministic parity, click-for-click, with the first complete board win in project history. The intake-calibration benchmark role stands re-verified on the current core/build.

## Capsule + bookkeeping

- mspsx capsule **+1 event** (status VERIFIED, the rebuild disclosure carried inside the event); `next_experiment` replaced: **no open lever** — the game is the intake-calibration benchmark and the r35 recipe stays the reference 1-boot regression harness for future core/build changes.
- Boot ledger cap 1/1, disclosed pre-run; the disc rebuild is outside the boot count (zero boots, all offline) and is disclosed here per the license policy (game bytes and license sectors stay out of the repo).

## Internet-first (the golden rule)

The upstream release re-fetch **is** the internet step of this round: the exact release asset was pulled, size- and sha-verified against the recorded pristine values before any boot — no drift between upstream v0.1 and the verified baseline.

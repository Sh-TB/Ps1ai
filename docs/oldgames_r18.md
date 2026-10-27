# Old-games track, round 18 — boot ladder measured, honest RUNNING

Games: `Ballistic [U] [SLUS-00966]`, `Air Hockey (USA) [SLUS-01467]`
(both ingested round 16; both dumps verified this round:
`Sony Computer` license string present, ballistic PVD = `CD001 PLAYSTATION`).

## What round 18 measured (scripts + evidence)

- `scripts/oldgames_r18_probe.py` → boot + 5-button census at ~f900:
  both games render (640×472 and mode switches), **all button diffs = 0**.
- `scripts/oldgames_r18_stallcheck.py` (ballistic, fresh workspace, 5000f,
  PNG every 500f): the screen is NOT static —
  f620 dark quad → f1120 Mitchell "eO" logo → f1620 **INFOGRAMES publisher
  screen** (readable: "Ballistic™ is a trademark of Infogrames North America.
  © 1999 Mitchell Corporation") → f2120+ black (CD load) → black through
  f4620. Verdict line: SLOW_INIT.
- `scripts/oldgames_r18_bootfull.py` (11,200f ladder + "stable state" census):
  deltas 0 from f4000 — the census keeps landing in static logo/load phases
  where the game does not poll the pad. No input-responsive state found
  automatically this round.

## Honest verdict

- Both discs: **verified retail dumps** (license + PVD present), boot
  sequence **advances through publisher logos into a long load**, then sits
  in static phases. No PLAYING claim. Status: **BOOT_SEQUENCE_MEASURED,
  TITLE_NOT_REACHED** under beetle 0.9.44 headless.
- Suspects for r19: (a) even longer boot (some budget titles load 15-30 s),
  (b) census at the exact title frame via manual PNG reading, (c) disc-access
  timing differences headless vs realtime, (d) interference from concurrent
  long sessions (a background filesystem cleanup was running during this
  round's probes).
- The r16 "BOOTED" verdict for ballistic was RAM-churn-based, not visual —
  this round corrects the record: the screen path is measured above.

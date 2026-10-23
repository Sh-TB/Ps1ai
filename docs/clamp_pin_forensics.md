# Village-Section Pin (D7) — Forensics Session 2026-10-24

The declared session-2 follow-up ("with the FIXED u32 reader, diff the
camera-adjacent globals between a clamped walk and a pre-clamp walk to
find the LIMIT variable's writer") executed, plus the poke and
behavioural matrix follow-through. **Bottom line: the pin at px 1163 is
a section state-machine behaviour, NOT a static limit constant in
RAM; the legitimate lift-condition remains open** — but six structural
facts are now instrument-established, and one long-standing number
mystery (the "992 pin") is resolved.

Evidence tree (local, never committed):
`/home/z/my-project/work/msx_recomp/evidence/{clamp_globals,mosque_gate,pin_matrix}/`.
Scripts committed: `scripts/msx_clamp_globals_diff.py`,
`scan_eb598_refs.py`, `analyze_clampdiff3.py`, `analyze_clamp_snap.py`,
`msx_limit_poke.py`, `msx_mosque_gate_test.py`, `msx_pin_matrix.py`,
`msx_deep_left.py`, `print_clamp_traj.py`.

## Method summary

1. **clampdiff1/2/3** — disclosed hp-freeze reach (the heli-ladder
   precedent) from mission start to the px-1163 pin; per-10f word
   windows + full-RAM snapshots at pre-clamp (A, px 715), pin arrival
   (B, px 1163) and pinned (C, +480f). Full-RAM numpy diffing with
   pin-boundary-aware classification (followers / freezers / flips).
2. **EXE reference scan** — capstone linear decode of the canonical
   620,544-B text (155,136 instructions, skipdata for embedded data)
   with lui+addiu/ori address-materialization tracking, targeting the
   scroll word 0x800EB598, the player anchor 0x800CA2E0 and the
   window-flip addresses.
3. **Limit poke** (DISCLOSED exploration write, three arms from the
   same pin-arrival savestate `clamp0`): candidate limit, neighbour
   control, no-poke control.
4. **Pin matrix** (clean, per-frame, death-episode accounting): P pure
   hold-right / R death+respawn / L shallow-left, all from `clamp0`.
5. **Deep-left arm** (D): the truck-hop gait toward the 660-880 zone.
6. **Mosque gate test** (D6 connection): from `clamp0`, grenade volley
   to the +800&0x20 mosque-kill signature vs a no-volley control, then
   right-traversal check + faller census.

## Instrument-established findings

| # | Finding | Evidence |
|---|---------|----------|
| F1 | **No separate camera stall.** The scroll-struct word `0xEB598` (16.16 fixed) FOLLOWS the player the whole way (`player−2.5…+1`) and pins at `0x048BFFFF` = 1163.99998 exactly when the player pins at 1163. There is no camera word stalling at ~988 in this boot path. The historical "988/992" figures are the **checkpoint respawn px (992)** and the truck pin — the long-standing number mystery is resolved as respawn geometry, not camera logic | clampdiff2/3 trajectories (`print_clamp_traj.py`); `analysis.json` named/extras |
| F2 | `0xEB598` is a **render-side copy struct** written from a source struct (`$s1`): copy sites at `0x80022894`, `0x80022A38`, `0x80023138`, `0x80023324`, `0x800233AC` (+4/+8/+0xC fields, flags u16 @+0x38 with `ori 1`, state word @+0x5C). The clamp decision lives upstream of these copies | `scan_eb598_refs.py` -> `eb598_refs.json` (8 sites, with ±6-insn context) |
| F3 | **Pin state machine visible in RAM**: at pin arrival the player-struct function pointers flip (`0xCA268: 0x80034ddc→0x80032d28`, `0xCA2A0: 0x800b860c→0x800b83e0` — the latter in overlay/heap code), a state word goes 10→1 (`0xCA2A4`), and the struct +8 field (`0xEB5A0`) drops 3.0→0.0 | clampdiff3 FLIP/FREEZE lists (`analyze_clampdiff3.py`) |
| F4 | **No limit constant in RAM**: u32 16.16 candidates in [1140..1190] px are only low-RAM garbage; values 0x048C0000/0x048BFFFF/0x048B0000 appear NOWHERE (0 hits); u16 1164 has exactly ONE hit at `0x8DBF8` — which is **reused runtime data** (the .full file holds a `sw` instruction at that VA; the region is repurposed after init) | `analyze_clampdiff3.py` output; disasm of 0x8008DBF0-0x8008DC0C |
| F5 | **Poke test NEGATIVE** (disclosed): `u16@0x8DBF8 1164→2000` did not lift the pin (nor the neighbour/no-poke controls; all three max_px = 1163). The value is therefore one-shot-copied at section init or not the governing limit | `msx_limit_poke.py` -> `report_limit_poke.json` |
| F6 | **Pin matrix (clean)**: P_pure — pin stable for 20 chunks; L_leftwalk (to px 1100, before the truck) — no change, still pinned; R_respawn — **119 death episodes**: death at the clamp respawns at 992 INSIDE the truck kill zone -> instant re-death loop. This resolves commit b283b19's "walk_right control dies truck-pinned at 992" as the respawn+truck loop, not a new wall | `msx_pin_matrix.py` -> `report.json`, per-arm traces |
| F7 | **The hp-freeze does NOT protect against one-shots** (truck ram −291 ≥ current hp lands after the freeze write within the same frame): the deep-left arm died at the truck (~1126) despite the disclosed freeze + hop gait. Design consequence for survival policy: vs one-shot threats only distance/timing helps, never HP tricks | `msx_deep_left.py` log + rows |
| F8 | The mosque-gate arms' max_px 1483/1486 spikes are **NOT traversal evidence** (no sustained >=1180 run; the arms were tangled by a corridor death that appears to have triggered a FULL MISSION RESTART — score reset 0, px ~120, grenades 10). No traversal claim is made | `msx_mosque_gate_test.py` reports + rows |
| F9 | **D6 progress**: the +800&0x20 mosque-kill signature reproduced cleanly in one volley campaign (score_delta = exactly 800); the post-kill faller poll recorded **0 events** — suggestive but a single poll; the sustained rain-quiet measurement is still owed. D6 remains open, now with a +1 reproduction of the kill itself | `mosque_gate/report.json` (kill arm), `trace_kill.jsonl` score events |
| F10 | **EXE ground truth for future RE**: the `.full` text is PLAIN LITTLE-ENDIAN (validated by the sane prologue at the real entry pc0 `0x80082A44` — a byteswap hypothesis was tested and rejected); capstone needs `skipdata=True` for embedded data words; the ROOT-chain VA `0x80012814` is a POINTER TABLE (`0x8007C38C` ×7), not code — session-2's "generic ROOT chain" reading is consistent | disasm excerpts in this session's log |

## Verdict

- D7 (scroll clamp / stage-completion) stays **BLOCKED** as a root
  blocker, now with a much sharper shape: the pin is enforced by the
  section state machine (function-pointer flips F3), there is no
  static limit constant to freeze (F4/F5), and the only observed
  pass-past-1163 states are unreproducible chaos (F8). The next
  concrete experiments: (a) trace the flipped handlers
  `0x80032d28` / `0x800b83e0` and the camera-copy source struct to
  find the clamp comparison; (b) retry the deep-left traverse with a
  truck-phase-aware strategy (the truck script phase varies per boot —
  the checkpoint-phase variance applies here too); (c) the
  mission-restart path (F8) deserves one clean probe: does a restart
  skip the completed part of the section?
- D6 gains a +1 kill-signature reproduction and a 0-faller post-kill
  poll (unsustained). The kill itself is now cheap and reliable from
  `clamp0` via the lob campaign.
- Enemy-awareness scope (the Coder-2 acceptance criteria) is untouched
  by any of this: the 8-case suite + live series stand as delivered.

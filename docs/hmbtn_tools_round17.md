# Harvest Moon: Back to Nature — community tools deep test (round 17)

Round 16 audited the five GitHub repos and built our own decorpus tool
(`hmbtn_text.py`). Round 17 goes one level deeper: it **executes the
community tools themselves** and — the centerpiece — **builds the matching
decompilation** on this sandbox, disc-free. Repo status after this round:
every tool that can run without the user's disc has been run, and the decomp
compiles to the byte-identical game binaries.

## What was tested (coalslav/hmbtn-decomp, CC0-1.0)

Driver: `scripts/r17_hmbtn_tooltest.py` (committed; synthetic fixtures only).
Report: `scratch/r17_hmbtn_tools/report.json` (local; facts only).

| # | tool | test | verdict |
|---|------|------|---------|
| 1 | `tools/afile.py` | synthetic A_FILE.BIN/HDT (3 members, sector-aligned) unpack → members bit-exact; pack → container bit-exact | **PASS** (round-trip both directions) |
| 2 | `tools/psx_disc.py extract` | OUR OWN Metal Slug X (USA) retail disc → 355 files extracted, SYSTEM.CNF + license_data.dat + `SLUS_012.12` (622,592 B = 2048 header + 620,544 code) | **PASS** (output local-only) |
| 3 | `tools/ps_x_exe.py` (PsxExeHeader.parse, imported) | parsed the extracted MSX EXE: pc0 `0x80082A44`, text_size 620,544, text_addr `0x80010000`, marker "Sony Computer Entertainment Inc. for North America area" — **all three cross-check our independent `disc_intake` anchor exactly** | **PASS_CROSS_CHECK** |
| 4 | `tools/psx_disc.py build` | synthetic mini-layout (mkpsxiso subset: identifiers+dates, license 12×2336, default_attributes) → 56,448-byte image; PVD volume id at LBA 16; content present; re-extract with the same tool bit-exact | **PASS** (round-trip) |

Cross-tool note: their PS-X EXE parser and their disc extractor agree with our
independent round-16 `disc_intake.py` on the MSX anchor (pc0/t_size) — two
unrelated codebases, one measured fact.

## The centerpiece: the matching decomp builds byte-identically, disc-free

`hmbtn-decomp`'s README says: without `-DORIGINAL_DISC` it "builds and checks
only the 14 code binaries, which needs no game data". We ran exactly that:

```
cmake -S hmbtn-decomp -B build -G Ninja \
  -DPSX_GCC_DIR=<wrap> -DPSYQ_SDK_DIR=<psyq-4.7> -DPSYQ_INCLUDE_DIR=<headers>
cmake --build build --target check
→ SLUS_011.15: OK … 31_gf_mcard.bin: OK
→ "all 14 files match the original"
```

The EXE (`SLUS_011.15`) **and all 13 overlays** compile from the community C
source to SHA-1-verified byte-identical binaries. Toolchain, pinned and
SHA-256-verified per the repo's Dockerfile: GCC 2.95.2-psx (decompals
0.17), PSY-Q Runtime Library 4.7, `binutils-mips-linux-gnu` 2.44, maspsx
(their vendored copy), cmake 3.31.6 + ninja 1.13.2.

### Sandbox adaptations (all local, documented, none touch the decomp source)

1. **qemu-i386 wrappers for cpp+cc1.** The 1999 i386 static toolchain
   binaries get `SIGSYS` ("Bad system call") from this sandbox's seccomp
   profile when run natively; qemu-i386 10.0.13 (extracted from the Debian
   `qemu-user` package, no root needed) translates their old syscalls in
   userspace. `cpp` and `cc1` run at full fidelity under the wrapper.
2. **tmpfs source tree.** cpp 2.95.2's `stat()` returns `EOVERFLOW` ("Value
   too large for defined data type") on the overlayfs 64-bit inode numbers;
   sources + PSY-Q headers live on `/dev/shm` (small sequential inodes).
   The build OUTPUT stays on the overlayfs — `as`/`ld`/`objcopy` are modern
   native binaries and unaffected.
3. **`psx_cc.py` depfile synthesis (LOCAL copy only, backup `.orig`).**
   cpp's `-M/-MD` dependency modes are also seccomp-blocked natively, so the
   local driver synthesizes the ninja depfile from the source's recursive
   quote-includes. (Under qemu the original `-MD` path may well work; the
   synthesis was already in place and is strictly output-neutral — depfiles
   never enter the binaries.)
4. **`LD_LIBRARY_PATH`** for the extracted binutils' `libopcodes/libbfd`.

Build evidence: `scratch/r17_hmbtn_tools/build_report.json` +
`build_check_full.log` (14 × OK + the final line). The built binaries stay
in `external_audit/` (local) — game bytes never enter the repo.

## What this unlocks (and what remains disc-gated)

* The complete build/verify path of the farming game's community toolchain
  is **proven runnable in this exact sandbox** — when the user's SLUS-01115
  disc arrives, nothing blocks `A_FILE.BIN` extraction (afile.py tested),
  decorpus extraction at full corpus scale (our `hmbtn_text.py corpus` mode),
  the modkit build, or a license-patched boot of the community-built EXE
  through the standard homebrew route.
* Still disc-gated (honest list): dialogue/story extraction from
  `messege0..4.bin` (needs the disc's A_FILE.BIN), disc-image reconstruction
  (`psx_disc.py build` with the real layout), HMBTN-Recomp runtime
  (bring-your-own-disc), modkit `hm.py build <mod> <base>` (base = the
  user's image).

## Other repos (re-verified this round)

Clones refreshed under `external_audit/hmbtn/` (local):
`hmbtn-decomp` (built — above), `backtonature-decompiled`,
`HarvestMoonBTN-Recomp`, `hmbtn-modkit`, `EVENT-EDITOR`. The latter four
remain bring-your-own-disc for anything executable; their round-16 audit
rows stand unchanged.

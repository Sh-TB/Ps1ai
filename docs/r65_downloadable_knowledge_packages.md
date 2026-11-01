# R65 Downloadable Knowledge Packages — the `.ps1game` system

Round: **R65** · Part B + Part H deliverable.

## 0. The product rule

**A user can download ONE game's knowledge file, provide their own legal
copy of that game, install the package, test compatibility and gameplay,
and use the game-specific autonomous player where it is verified —
without repeating that game's reverse engineering.**

Every game has its own independent intelligence; PS1Play is the common
engine that runs them. No package contains, references or depends on
another game's knowledge (enforced by test:
`tests/test_r65_packages.py::test_no_cross_game_references`).

## 1. The format

`<game_id>.ps1game` — a deflated ZIP with a validated `manifest.json`
(schema `ps1play.game-package/1`):

```
manifest.json        schema, package{id,version,maturity}, runtime compat,
                     game_identity{serial,region,revision}, contents[
                       {path, sha256, bytes, role}...], capabilities,
                     legal{assets_included:false, user_must_provide},
                     integrity{manifest_sha256}
plugin/…             the game's adapter (+ policy) sources
knowledge/…          RE knowledge, disc pin, records, evidence
tools/…              where the user flow needs them (e.g. BuzzyBee's
                     build-your-own-disc recipes)
tests/…              the game's contract tests
README.md            identity, legal notes, quick start, records,
                     known limitations
```

Every content file is pinned by SHA-256 in the manifest; the manifest is
pinned by its own `integrity.manifest_sha256` over the canonical body;
the archive is pinned by the `.sha256` sidecar. Validation recomputes
everything.

### Security rules (all enforced, loud failures)

* ZIP entries: relative paths only — absolute paths, backslashes,
  drive letters, `..` traversal, colon parts: rejected (tested).
* Size caps: 64 MiB per entry, 128 MiB per archive, 4096 entries.
* Installation NEVER executes package code; files are unpacked into
  `<root>/<game_id>/<version>/` only — never over another game's tree
  (tested); an existing same-version install requires `--force`.
* No commercial ISOs, BIOS files or copyrighted assets inside packages —
  the `legal` section names exactly what the user must provide, and the
  runtime verifies the user's disc by SHA-256 at play time.

## 2. The maturity ladder (honest, per package)

`EXPERIMENTAL → BOOT_VERIFIED → INPUT_VERIFIED → GAMEPLAY_VERIFIED →
PARTIAL_AUTONOMOUS_PLAYER → OBJECTIVE_VERIFIED →
FULL_GAME_COMPLETION_VERIFIED`

A package may be useful before full completion; the level must describe
the actual evidence.

## 3. The packages (this release)

| package | version | maturity | autonomous play | contents |
|---|---|---|---|---|
| `flappybird.ps1game` | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (the R61 frozen champion) | adapter, frozen policy package (ONNX + authority manifest), perception module, disc pin, R61+R65 records, 5 test files |
| `tetrade.ps1game` | 1.1.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (anchor-corrected Dellacherie, mean 23.83 lines/life) | adapter, policy, the 28/28 anchor table, evidence records, disc pin, 2 test files |
| `buzzybee.ps1game` | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (bot_policy8, score law EXACT) | adapter, policy, provenance capsule, disc-build tools, disc pin, records, 2 test files |
| `metal_slug_x.ps1game` | 0.1.0 | INPUT_VERIFIED | NO (diagnostic knowledge) | capsule, entity/death-path/map/route knowledge, truck-blocker record, disc pin |

Exact SHA-256 values are pinned in `reports/r65_summary.json`, the
release's `SHA256SUMS.txt`, and each package's sidecar. The release link
is in the repository's Releases page (tag `r65`).

## 4. The user workflow (Part H)

```bash
python3 -m ps1play knowledge list                # what exists / installed
python3 -m ps1play knowledge export flappybird   # build (or download)
python3 -m ps1play knowledge validate ./flappybird.ps1game
python3 -m ps1play knowledge install ./flappybird.ps1game
python3 -m ps1play knowledge show flappybird     # manifest summary
python3 -m ps1play test flappybird               # the package's tests
python3 -m ps1play play flappybird               # autonomous play
python3 -m ps1play play flappybird --record      # + GIF evidence
```

What the system distinguishes (never conflated):

* **Package installed** — validation passed, files on disk.
* **Game identity matched** — the runtime's preflight verifies the
  user's disc SHA-256 against the package pin (a mismatch is an
  `AssetError`, never a warning).
* **Game booted / ready** — the adapter's verified ready state.
* **Controller responsive** — the adapter's input causality evidence.
* **Gameplay state detected** — the observation vector's state fields.
* **Automated test passed** — `knowledge test`'s pytest exit code.
* **Objective completed** — only where a package's records claim it
  (none of the R65 packages claim a full-game completion; the ladder
  says exactly why).

For a game not yet fully automated (metal_slug_x) the package provides
diagnostics and knowledge, not a play command — `test_command: null`,
`play_command: null` are honest fields in its capabilities.

## 5. Clean-environment installation proof

The install path was exercised outside the developer workspace
state: packages were exported to a scratch directory, validated,
installed into a fresh `--root` (`/tmp/r65_install`), re-validated from
disk (every file's sha256 recomputed and matched), the reinstall-without-
force rejection proven, and another game's tree proven untouched
(`tests/test_r65_packages.py::TestInstall`). The CLI lifecycle
(`list → export → validate → install`) was run through the actual
`python3 -m ps1play` entry point this round. The GitHub release adds the
final portability proof: the assets are downloaded from the release and
re-validated before the download claim is made.

## 6. Portability honesty

* Linux/x86-64 CPU-only: verified (this is the platform every record
  was made on; beetle + OpenBIOS; the exact core binary is pinned in
  the runtime manifest of every run).
* Windows/macOS: NO claims — untested. The core binary and the ctypes
  wrapper are platform-specific.
* The user's own disc: FlappyBirdPSX is free homebrew (Unlicense, direct
  download); Tetrade is free homebrew (MIT) needing a LOCAL
  license-patched image built from the user's own retail disc
  (`scripts/make_homebrew_lic.py` recipe, documented in the package
  README); BuzzyBee needs the upstream EXE + the user's own license
  sectors (tools included in the package); Metal Slug X is commercial —
  the user must own the disc and verify its hash.

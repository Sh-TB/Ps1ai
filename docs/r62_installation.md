# R62 Installation Guide

## Requirements

- Linux x86-64 (the libretro core is a Linux shared object; other
  OSes are NOT tested — see the portability note at the bottom).
- Python 3.11+ (tested on 3.12).
- CPU-only: no GPU, no X11, no audio needed. ~300 MB free RAM.
- No network access is needed at runtime (assets verified locally).

## 1. Install the runtime

From the repository root:

```bash
pip install -r requirements-r62.txt
```

(`numpy==2.1.3`, `onnxruntime==1.19.2`, `pillow` for screenshots —
all free/open-source. `onnxruntime` is only needed by the policy
package; `pillow` only if you use `--record/--screenshot`.)

## 2. Assets — where they come from and how they are verified

| Asset | Source | Verified by |
| --- | --- | --- |
| FlappyBirdPSX v0.1.0 ISO | `https://github.com/IcePanorama/FlappyBirdPSX/releases/download/v0.1.0/flappybirdpsx-v0.1.0.iso` (Unlicense homebrew) | SHA256 `b45871d3…` — hard-checked at preflight against the exact build every R59/R61 record used |
| OpenBIOS | committed: `third_party/openbios/openbios.bin` | SHA256 recorded in the runtime manifest |
| beetle PSX core | `ps1play/labconfig.py` resolution (`.autolab_config.json` / `M1_CORE`) | path + SHA256 in the runtime manifest |
| the frozen policy | committed: `deployment/flappybird_policy/models/r60_soup_e6a010.onnx` | SHA256 `4dd592a7…` hard-checked against `data/learn/FINAL_MODEL_MANIFEST.json` |

Place the ISO anywhere and pass `--config` with `iso_path`, or use
the default location `/home/z/my-project/emu/games_homebrew/
flappybird.cue` (a cue file whose `FILE` entry points at the ISO;
the cue is resolved and the IMAGE is hashed).

A wrong/mismatched asset fails fast with exit code 3 and an
actionable message — the runtime never boots on unverified content.

## 3. Verify the installation

```bash
python3 -m ps1play --help                       # CLI up
python3 -m ps1play verify --profile final       # the full release gate
```

## 4. First run

```bash
python3 -m ps1play play flappybird
```

default: ONE episode, seed k=6, 10,000-frame budget, 300 s run
budget — a bounded, safe demo. Results land in
`scratch/r62/run_<UTC timestamp>/`.

## Portability note (honest)

Tested on Linux/x86-64 only (the CI machine and dev containers).
Windows/macOS are untested: the core path, the ctypes frontend and
the workspace layout are Linux-flavored. Porting work would start
from `ps1play/labconfig.py` (core resolution) and
`ps1play/core/host.py` (ctypes loading). Do not assume portability
without running the release gate on the target OS.

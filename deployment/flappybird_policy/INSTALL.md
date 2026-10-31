# INSTALL.md — clean-room installation

## Requirements

- Linux (tested on Ubuntu-class x86-64; other OSes are NOT claimed —
  see KNOWN_LIMITATIONS.md), Python ≥ 3.10
- pip with access to PyPI (or a local wheel mirror)
- ~120 MB free (onnxruntime + numpy wheels)

## Steps

```bash
# 1. get the package directory (copy it out of the repository — it is
#    self-contained: code + model + manifest)
cp -r <repo>/deployment/flappybird_policy /somewhere/clean/

# 2. fresh environment (recommended)
python3 -m venv /somewhere/clean/venv
source /somewhere/clean/venv/bin/activate

# 3. install ONLY the pinned runtime dependencies
cd /somewhere/clean/flappybird_policy
pip install -r requirements.txt      # onnxruntime==1.19.2, numpy==2.1.3

# 4. verify the installation
python3 -m flappybird_policy         # exits 0, prints SMOKE PASS
PYTHONPATH=. python3 examples/minimal_example.py
```

`python3 -m flappybird_policy` verifies: manifest parsing, model hash
binding, session init, strict input validation, batch and single
inference, and clean shutdown. Exit code 0 = usable.

## Verifying what you got

The loaded policy exposes its identity:

```python
policy.identity()
# {'model_sha256': '4dd592a7118a5c4de7b44166b42b8d09'
#                  'd53fbb59330d36d0ba2746393dc11044', ...}
```

The ONLY valid model sha256 is
`4dd592a7118a5c4de7b44166b42b8d09d53fbb59330d36d0ba2746393dc11044`.
`load_policy()` refuses to run a model whose hash does not match the
manifest (`MODEL HASH MISMATCH`).

## Installing without network

Copy the wheels of `onnxruntime==1.19.2` and `numpy==2.1.3` for your
platform, then `pip install --no-index --find-links <wheels> -r
requirements.txt`.

## Uninstall / cleanup

Delete the directory and the venv. The package writes nothing to disk
(inference is in-memory; logs are the caller's responsibility).

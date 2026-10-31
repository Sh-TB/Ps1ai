# flappybird_policy — the final FlappyBirdPSX policy, ready to run

This directory is the **independent deployment package** for the final
trained FlappyBirdPSX policy (R61). It contains everything needed to
load the model, verify it, and produce legal actions — with no access
to the training implementation.

## What's inside

```
flappybird_policy/            the Python package (numpy + onnxruntime only)
├── policy.py                 load_policy / predict / predict_batch / reset / close
├── schema.py                 the enforced 10-feature input contract
├── __main__.py               CLI smoke test:  python3 -m flappybird_policy
└── version.py                package version
models/
├── r60_soup_e6a010.onnx      the final model (7,182 bytes, opset 17)
├── r60_soup_e6a010.onnx.json the artifact sidecar (provenance + parity)
└── FINAL_MODEL_MANIFEST.json the authoritative manifest (hashes bound)
examples/minimal_example.py   the smallest runnable consumer
requirements.txt              pinned runtime dependencies
INTERFACE.md                  the full perception-to-action contract
INSTALL.md                    clean-room installation
MODEL_CARD.md                 what the model is / is not
KNOWN_LIMITATIONS.md          honest limits and failure cases
TROUBLESHOOTING.md            common errors and fixes
REUSE_BOUNDARY.md             what ports to another game and what doesn't
```

## 60-second start

```bash
pip install -r requirements.txt
python3 -m flappybird_policy                 # verify + smoke test
PYTHONPATH=. python3 examples/minimal_example.py
```

## Minimal API

```python
import numpy as np
from flappybird_policy import load_policy

policy = load_policy()                       # verifies every hash
obs = np.zeros(10, dtype=np.float32)         # RAW v7 vector, see INTERFACE.md
obs[0] = 97.9                                # bird y
action = policy.predict(obs)                 # "HOVER" | "FLAP"
policy.close()
```

The observation is the RAW 10-feature v7 decision vector — the graph
normalizes internally. Feature order, units, sentinels and enforced
ranges: `INTERFACE.md` (enforced by `schema.py`; invalid input raises,
nothing is silently coerced).

## What this package does NOT do

It does not see the game. The perception state machine (frames → the
10-feature vector) is a host-side adapter documented in
`INTERFACE.md`; driving the real emulator end-to-end is demonstrated
by the repository's `scripts/r61e_deploy_loop.py` (kept out of this
package on purpose — it depends on the emulator host).

## Verification status (R61)

- 220,522-vector 3-way parity: numpy reference == onnxruntime ==
  this package, max |Δlogit| 0.0, argmax 100%.
- Real-emulator reproduction: all 7 family seeds byte-exact through
  this package; 30 fresh pre-registered seeds × 2 reps, reps
  byte-identical.
- Clean-room install from a fresh venv: PASS.

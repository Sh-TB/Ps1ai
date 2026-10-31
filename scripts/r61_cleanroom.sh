#!/usr/bin/env bash
# r61_cleanroom.sh — R61 Section 11: install and use the deployment
# package from a FRESH venv with NO access to the training environment.
# The clean room gets ONLY: the package tree + requirements.txt.
set -u
set -e
CLEAN=/tmp/r61_cleanroom
VENV=/tmp/r61_cleanvenv
rm -rf "$CLEAN" "$VENV"
mkdir -p "$CLEAN"
cp -r /home/z/my-project/ps1ai/deployment/flappybird_policy "$CLEAN/"
echo "== clean room contents =="
find "$CLEAN" -type f | sort

python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip 2>&1 | tail -1 || true
echo "== installing ONLY the pinned runtime deps =="
"$VENV/bin/pip" install -q -r "$CLEAN/flappybird_policy/requirements.txt"
"$VENV/bin/pip" list | grep -i "onnxruntime\|numpy"

echo "== 1. CLI smoke test =="
cd "$CLEAN/flappybird_policy"
"$VENV/bin/python" -m flappybird_policy | tail -n 2

echo "== 2. minimal example =="
PYTHONPATH=. "$VENV/bin/python" examples/minimal_example.py

echo "== 3. API surface + batch + lifecycle =="
"$VENV/bin/python" - <<'EOF'
import sys
import numpy as np
sys.path.insert(0, ".")
from flappybird_policy import load_policy

p = load_policy()
x = np.zeros(10, dtype=np.float32); x[0] = 97.9
assert p.predict(x) in ("HOVER", "FLAP")
b = np.repeat(x.reshape(1, -1), 7, axis=0)
assert len(p.predict_batch(b)) == 7
p.reset(); p.close()
print("API PASS")
EOF

echo "== 4. version reporting =="
"$VENV/bin/python" -c "
import sys; sys.path.insert(0, '/tmp/r61_cleanroom/flappybird_policy')
import flappybird_policy
print('package version:', flappybird_policy.PACKAGE_VERSION)
p = flappybird_policy.load_policy()
i = p.identity()
print('model sha256:', i['model_sha256'][:16], '(verified)')
assert i['model_sha256'].startswith('4dd592a7118a5c4d')
print('VERSION REPORTING PASS')
"
echo "CLEANROOM PASS"

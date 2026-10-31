"""__main__.py — the command-line smoke test of the deployment package.

Usage (from the package root deployment/flappybird_policy/):
    python3 -m flappybird_policy                     # default self-test
    python3 -m flappybird_policy --model PATH --manifest PATH
    python3 -m flappybird_policy --example-vector    # print a sample

Exit 0 = the package loaded the verified model, validated inputs, ran
inference, and produced a legal action. Exit 1 = any failure (with a
precise message). This entry point never imports the training code.
"""
import argparse
import json
import sys

import numpy as np

from .policy import load_policy
from .schema import FEATURE_NAMES, N_FEATURES


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="flappybird_policy",
        description="Smoke-test the final FlappyBirdPSX ONNX policy "
                    "(independent deployment package)")
    ap.add_argument("--model", default=None,
                    help="path to the ONNX artifact "
                         "(default: the shipped models/ copy)")
    ap.add_argument("--manifest", default=None,
                    help="path to FINAL_MODEL_MANIFEST.json "
                         "(default: the shipped models/ copy)")
    ap.add_argument("--example-vector", action="store_true",
                    help="print one valid example vector and exit")
    a = ap.parse_args(argv)

    if a.example_vector:
        v = np.zeros(N_FEATURES, dtype=np.float32)
        v[FEATURE_NAMES.index("by")] = 97.9
        v[FEATURE_NAMES.index("since_flap")] = 12.0
        v[FEATURE_NAMES.index("since_gap")] = 8.0
        print(json.dumps(dict(zip(FEATURE_NAMES, map(float, v)))))
        return 0

    pol = load_policy(model_path=a.model, manifest_path=a.manifest)
    ident = pol.identity()
    print("model      :", ident["model_path"])
    print("model sha  :", ident["model_sha256"])
    print("manifest   :", ident["manifest_path"])
    print("checkpoint :", ident["source_checkpoint"])

    rng = np.random.default_rng(7)
    x = np.asarray(
        [97.9, 0.0, 98.5, 32.7, 66.5, 130.5, 0.0, 12.0, 98.8, 8.0],
        dtype=np.float32)
    act = pol.predict(x)
    batch = np.repeat(x.reshape(1, -1), 5, axis=0)
    jitter = rng.standard_normal(batch.shape).astype(np.float32) * 0.01
    jitter[:, 6:] = 0.0  # the history counters are exact integers
    batch = (batch + jitter).astype(np.float32)
    acts = pol.predict_batch(batch)
    lg = pol.logits_batch(x.reshape(1, -1))[0]

    print("predict    :", act)
    print("batch      :", acts)
    print("logits     :", [round(float(v), 6) for v in lg])
    legal = set(pol.classes)
    ok = act in legal and set(acts) <= legal and pol.n_calls == 3
    print("identity   :", json.dumps(ident, indent=1)[:400])
    pol.close()
    print("SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

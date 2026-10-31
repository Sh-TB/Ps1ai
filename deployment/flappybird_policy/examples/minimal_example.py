"""minimal_example.py — the smallest possible use of the final policy.

Run from deployment/flappybird_policy/:
    python3 examples/minimal_example.py

This is a complete, runnable consumer: it imports ONLY this package
(no training code), loads the shipped verified model, and asks for one
action on a hand-built observation.
"""
import numpy as np

from flappybird_policy import load_policy  # noqa: E402


def main():
    policy = load_policy()

    # The RAW v7 decision vector (10 float32 values — the graph
    # normalizes internally). Feature order:
    # by, vy, gc, dx, g0, g1, flap_run, since_flap, last_gc, since_gap
    observation = np.asarray(
        [97.9, -2.0, 98.5, 32.7, 66.5, 130.5, 0.0, 12.0, 98.8, 8.0],
        dtype=np.float32)

    action = policy.predict(observation)
    print("action:", action)          # "HOVER" or "FLAP"
    print("model :", policy.model_sha256[:16], "(verified vs manifest)")

    policy.close()


if __name__ == "__main__":
    main()

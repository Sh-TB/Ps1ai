"""policy.py — TinyMLP (numpy-only) + the artifact format.

CPU-only, no training framework: forward/backward/Adam in numpy.
The artifact is a single .npz containing ONLY float32 arrays + a small
json meta (architecture, normalization, class order, dataset digest).
Target: <= 4 MiB per artifact (measured in tests).

The SAME forward pass code path serves training and the final
visual-only inference (visual_only.py re-implements forward identically
in the boundary-clean module; tests assert numerical equality between
the two implementations on random inputs — one model, two readers,
no hidden pathway).
"""
import hashlib
import json
import os
import time

import numpy as np


def artifact_path_ok(path, max_bytes=4 * 1024 * 1024):
    return os.path.getsize(path) <= max_bytes


class TinyMLP:
    """n_in -> ReLU(hidden) -> linear(n_out)."""

    def __init__(self, n_in, hidden, n_out, seed=0):
        rng = np.random.default_rng(seed)
        self.n_in, self.hidden, self.n_out = n_in, hidden, n_out
        # He init
        self.W1 = (rng.standard_normal((n_in, hidden))
                   * np.sqrt(2.0 / n_in)).astype(np.float32)
        self.b1 = np.zeros(hidden, dtype=np.float32)
        self.W2 = (rng.standard_normal((hidden, n_out))
                   * np.sqrt(2.0 / hidden)).astype(np.float32)
        self.b2 = np.zeros(n_out, dtype=np.float32)

    # ---- forward (THE canonical implementation) ----
    def forward(self, x):
        x = np.asarray(x, dtype=np.float32)
        h = np.maximum(x @ self.W1 + self.b1, 0.0)
        return h @ self.W2 + self.b2, h

    def predict(self, x):
        out, _ = self.forward(x)
        return out

    # ---- training (mini-batch Adam, MSE or CE-over-logits) ----
    def fit(self, X, Y, epochs=60, batch=64, lr=2e-3, wd=1e-5,
            classification=False, seed=0, verbose=False,
            class_weights=None, sample_weights=None):
        X = np.asarray(X, dtype=np.float32)
        Y = np.asarray(Y, dtype=np.float32)
        cw = None
        if class_weights is not None:
            cw = np.asarray(class_weights, dtype=np.float32)
        sw = None
        if sample_weights is not None:
            sw = np.asarray(sample_weights, dtype=np.float32)
        rng = np.random.default_rng(seed)
        m = [np.zeros_like(w) for w in
             (self.W1, self.b1, self.W2, self.b2)]
        v = [np.zeros_like(w) for w in m]
        b1c, b2c, eps = 0.9, 0.999, 1e-8
        step = 0
        n = len(X)
        for ep in range(epochs):
            idx = rng.permutation(n)
            for s in range(0, n, batch):
                b = idx[s:s + batch]
                xb, yb = X[b], Y[b]
                out, h = self.forward(xb)
                if classification:
                    z = out - out.max(axis=1, keepdims=True)
                    ez = np.exp(z)
                    p = ez / ez.sum(axis=1, keepdims=True)
                    cls = yb.argmax(1).astype(int)
                    dlogit = p
                    dlogit[np.arange(len(b)), cls] -= 1
                    if cw is not None:
                        dlogit *= cw[cls][:, None]
                    if sw is not None:
                        dlogit *= sw[b][:, None]
                    loss = -np.log(p[np.arange(len(b)), cls] + 1e-9).mean()
                else:
                    dlogit = 2.0 * (out - yb) / len(b)
                    loss = float(((out - yb) ** 2).mean())
                dW2 = h.T @ dlogit + wd * self.W2
                db2 = dlogit.sum(0)
                dh = dlogit @ self.W2.T
                dh = dh * (h > 0)
                dW1 = xb.T @ dh + wd * self.W1
                db1 = dh.sum(0)
                step += 1
                for pi, (g, p_) in enumerate(zip(
                        (dW1, db1, dW2, db2),
                        (self.W1, self.b1, self.W2, self.b2))):
                    g = np.asarray(g, dtype=np.float32)
                    m[pi] = b1c * m[pi] + (1 - b1c) * g
                    v[pi] = b2c * v[pi] + (1 - b2c) * (g * g)
                    mh = m[pi] / (1 - b1c ** step)
                    vh = v[pi] / (1 - b2c ** step)
                    p_ -= lr * mh / (np.sqrt(vh) + eps)
            if verbose and (ep + 1) % 10 == 0:
                print(f"  epoch {ep+1}/{epochs} loss={loss:.5f}",
                      flush=True)
        return self

    # ---- artifact ----
    def save_artifact(self, path, meta):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": self.b2,
        }
        np.savez_compressed(path, **payload)
        js = path + ".json"
        full_meta = {
            "arch": {"n_in": self.n_in, "hidden": self.hidden,
                     "n_out": self.n_out},
            "format": "tinymlp-npz-v1",
            "created": time.time(),
            **meta,
        }
        with open(js, "w") as f:
            json.dump(full_meta, f, indent=2)
        return {"npz": path, "json": js,
                "npz_bytes": os.path.getsize(path),
                "sha256": _f_sha(path)}

    @classmethod
    def load_artifact(cls, path):
        """Loads ONLY the npz weights + meta json. Fresh-process safe:
        no ps1play import, no dataset access (see visual_only.Brain)."""
        z = np.load(path)
        js = path + ".json"
        meta = {}
        if os.path.exists(js):
            with open(js) as f:
                meta = json.load(f)
        arch = meta.get("arch", {})
        net = cls(int(arch.get("n_in", z["W1"].shape[0])),
                  int(arch.get("hidden", z["W1"].shape[1])),
                  int(arch.get("n_out", z["W2"].shape[1])))
        net.W1 = z["W1"].astype(np.float32)
        net.b1 = z["b1"].astype(np.float32)
        net.W2 = z["W2"].astype(np.float32)
        net.b2 = z["b2"].astype(np.float32)
        return net, meta


def _f_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

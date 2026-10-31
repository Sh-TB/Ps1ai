"""policy.py — the independent ONNX inference consumer.

Loads the frozen ONNX artifact under the authority of the committed
FINAL_MODEL_MANIFEST.json, verifies every hash at load time, and serves
deterministic legal actions. This file is deliberately self-contained:
numpy + onnxruntime are its only imports; no training, teacher or
dataset module is reachable from here.

Contract
--------
load_policy(model_path=None, manifest_path=None)
    -> FlappyBirdPolicy
    Both paths default to the models shipped inside this package.
    Raises ModelLoadError / ManifestError with precise messages on any
    inconsistency (missing file, hash mismatch, wrong manifest fields).

policy.predict(observation) -> "HOVER" | "FLAP"
    observation: numpy float32 array of shape (10,) — the RAW v7
    decision vector (the graph normalizes internally). Strict
    validation; raises InputValidationError on any violation.

policy.predict_batch(observations) -> list of actions
    observations: numpy float32 array of shape (N, 10).

policy.logits_batch(observations) -> (N, 2) float32
    Diagnostic access to the raw logits (used by the parity suite).

policy.reset()   — lifecycle: clears per-call statistics; the policy
                   itself is stateless between calls (perception state
                   lives in the host adapter, see INTERFACE.md).
policy.close()   — releases the ONNX session; later calls raise.

Determinism: the same float32 input yields the same action for the
lifetime of the process (CPUExecutionProvider, single-threaded session).
ArgMax semantics are first-max (select_last_index=0) — a tie resolves
to HOVER, matching the reference numpy argmax.
"""
import hashlib
import json
import os

import numpy as np

from .schema import (  # noqa: F401
    CLASS_NAMES,
    FEATURE_NAMES,
    N_FEATURES,
    InputValidationError,
    validate_batch,
    validate_observation,
)
from .version import PACKAGE_VERSION


class PolicyError(RuntimeError):
    """Base class for all deployment-package errors."""


class ModelLoadError(PolicyError):
    """The ONNX artifact could not be loaded."""


class ManifestError(PolicyError):
    """The manifest is missing, malformed or does not match the model."""


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = os.path.join(
    _PKG_DIR, os.pardir, "models", "r60_soup_e6a010.onnx")
DEFAULT_MANIFEST = os.path.join(
    _PKG_DIR, os.pardir, "models", "FINAL_MODEL_MANIFEST.json")


def load_policy(model_path=None, manifest_path=None):
    """Load and verify the final policy. See module docstring."""
    return FlappyBirdPolicy(
        model_path=model_path, manifest_path=manifest_path)


class FlappyBirdPolicy:
    """The final FlappyBirdPSX decision function, ONNX-backed."""

    def __init__(self, model_path=None, manifest_path=None):
        self.model_path = os.path.abspath(model_path or DEFAULT_MODEL)
        self.manifest_path = os.path.abspath(
            manifest_path or DEFAULT_MANIFEST)
        if not os.path.isfile(self.model_path):
            raise ModelLoadError(
                f"model file not found: {self.model_path} — pass "
                "model_path=... or reinstall the package models/ "
                "directory")
        if not os.path.isfile(self.manifest_path):
            raise ManifestError(
                f"manifest file not found: {self.manifest_path} — the "
                "policy refuses to load an unmanifested model")
        try:
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
        except (OSError, ValueError) as e:
            raise ManifestError(
                f"manifest unreadable: {self.manifest_path} ({e})")
        self.manifest_sha256 = _sha256_file(self.manifest_path)
        self.model_sha256 = _sha256_file(self.model_path)

        # -- manifest/model binding (fail loudly on any mismatch) -----
        art = self.manifest.get("onnx_artifact")
        if not isinstance(art, dict) or "sha256" not in art:
            raise ManifestError(
                "manifest has no onnx_artifact.sha256 — wrong file?")
        if art["sha256"] != self.model_sha256:
            raise ManifestError(
                "MODEL HASH MISMATCH: manifest binds sha256 "
                f"{art['sha256']} but the model file hashes to "
                f"{self.model_sha256}. Never run an unverified model.")
        arch = self.manifest.get("architecture")
        if not arch or arch.get("n_in") != N_FEATURES:
            raise ManifestError(
                "manifest architecture disagrees with the package "
                f"schema (n_in={N_FEATURES})")
        self.classes = list(self.manifest.get("output_schema", {})
                            .get("logits", {}).get("order")
                            or CLASS_NAMES)
        if self.classes != CLASS_NAMES:
            raise ManifestError(
                f"manifest class order {self.classes} != "
                f"{CLASS_NAMES} — refusing a different action mapping")
        self.feature_names = [f["name"] for f in
                              self.manifest.get("input_schema", {})
                              .get("features", [])]
        if self.feature_names and self.feature_names != FEATURE_NAMES:
            raise ManifestError(
                "manifest feature order disagrees with the package "
                "schema")

        # -- the session ------------------------------------------------
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise ModelLoadError(
                "onnxruntime is not installed — run "
                "`pip install -r requirements.txt` "
                f"(onnxruntime CPU). Original error: {e}")
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            self._sess = ort.InferenceSession(
                self.model_path, sess_options=opts,
                providers=["CPUExecutionProvider"])
        except Exception as e:  # corrupt file, wrong IR, missing ops...
            raise ModelLoadError(
                f"ONNX session init failed for {self.model_path}: {e}")
        self._input_name = self._sess.get_inputs()[0].name
        self.version = (f"pkg {PACKAGE_VERSION} / manifest "
                        f"{self.manifest.get('format', '?')}")
        self._n_calls = 0
        self.closed = False

    # -- core forward ---------------------------------------------------
    def logits_batch(self, observations):
        """(N, 10) float32 -> (N, 2) float32 logits (diagnostic; the
        parity suite drives this). Validation identical to
        predict_batch."""
        if self.closed:
            raise PolicyError("policy is closed — create a new one "
                              "with load_policy()")
        x = validate_batch(observations)
        out = self._sess.run(["logits"], {self._input_name: x})[0]
        self._n_calls += 1
        return np.asarray(out, dtype=np.float32)

    # -- public API ------------------------------------------------------
    def predict(self, observation):
        """One observation (10,) float32 -> 'HOVER' | 'FLAP'."""
        x = validate_observation(observation)
        if self.closed:
            raise PolicyError("policy is closed — create a new one "
                              "with load_policy()")
        out = self._sess.run(["logits"], {self._input_name: x})[0]
        self._n_calls += 1
        return self.classes[int(np.argmax(out[0]))]

    def predict_batch(self, observations):
        """(N, 10) float32 -> ['HOVER'|'FLAP', ...] (first-max argmax;
        a tie resolves to 'HOVER')."""
        if self.closed:
            raise PolicyError("policy is closed — create a new one "
                              "with load_policy()")
        out = self.logits_batch(observations)
        return [self.classes[int(i)] for i in np.argmax(out, axis=1)]

    def reset(self):
        """Lifecycle hook: the decision function is stateless between
        calls; perception state is the host adapter's responsibility
        (re-create ITS observer per episode — see INTERFACE.md)."""
        if self.closed:
            raise PolicyError("policy is closed")
        self._n_calls = 0

    def close(self):
        """Release the ONNX session. Idempotent."""
        self.closed = True
        self._sess = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- introspection ---------------------------------------------------
    @property
    def n_calls(self):
        return self._n_calls

    def identity(self):
        """A dict describing exactly WHAT is loaded (for logs/telemetry)."""
        return {
            "package_version": PACKAGE_VERSION,
            "model_path": self.model_path,
            "model_sha256": self.model_sha256,
            "manifest_path": self.manifest_path,
            "manifest_sha256": self.manifest_sha256,
            "source_checkpoint": self.manifest.get(
                "source_checkpoint", {}).get("path"),
            "classes": self.classes,
            "feature_names": self.feature_names,
            "n_features": N_FEATURES,
        }

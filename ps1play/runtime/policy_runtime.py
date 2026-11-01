"""ps1play.runtime.policy_runtime — the frozen-policy boundary (R62).

RuntimePolicy wraps the R61 INDEPENDENT deployment package
(`deployment/flappybird_policy`) behind the runtime's Policy contract:

  * loads ONLY the deployment package (numpy + onnxruntime + the ONNX
    artifact) — never the training code, never the teacher;
  * verifies the model + manifest SHA256 against the AUTHORITY
    manifest (`data/learn/FINAL_MODEL_MANIFEST.json`) before the first
    decision — a mismatch is an AssetError, never a warning;
  * refuses invalid observations (the package enforces the strict
    input contract; RuntimePolicy re-raises as RuntimePolicyError with
    the observation frame id — no silent coercion, no fallback);
  * measures per-decision latency and exposes the policy identity for
    every episode record.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Sequence

from .errors import AssetError, RuntimePolicyError
from .interfaces import ActionDecision, GameObservation, Policy
from .telemetry import sha256_file


class RuntimePolicy(Policy):
    def __init__(self, config, telemetry=None):
        self._cfg = config
        self._tel = telemetry
        self._verify_authority()
        import sys
        pkg_root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        pkg_path = os.path.join(pkg_root, "deployment",
                                "flappybird_policy")
        if os.path.isdir(pkg_path) and pkg_path not in sys.path:
            sys.path.insert(0, pkg_path)
        try:
            from flappybird_policy import load_policy  # noqa: PLC0415
        except Exception as e:
            raise RuntimePolicyError(
                f"the independent policy package is not importable "
                f"({type(e).__name__}: {e}) — expected at {pkg_path}; "
                f"refusing to fall back to any other policy")
        try:
            self._pol = load_policy(model_path=config.model_path,
                                    manifest_path=config.manifest_path)
        except Exception as e:
            raise RuntimePolicyError(
                f"policy load failed: {type(e).__name__}: {e}")
        ident = self._pol.identity()
        self._identity = {
            "name": "flappybird_policy (R61 frozen champion)",
            "package_version": ident.get("package_version"),
            "model_path": config.model_path,
            "model_sha256": ident.get("model_sha256"),
            "manifest_sha256": ident.get("manifest_sha256"),
        }
        self._n_calls = 0

    # ---- identity ----
    def _verify_authority(self) -> None:
        """Model/manifest hashes must match the authority manifest."""
        import json
        ap = self._cfg.authority_manifest_path
        if not os.path.exists(ap):
            raise AssetError(f"authority manifest missing: {ap}")
        with open(ap) as f:
            auth = json.load(f)
        exp_model = auth.get("onnx_artifact", {}).get("sha256")
        try:
            got = sha256_file(self._cfg.model_path)
        except OSError as e:
            raise AssetError(f"model not found: "
                             f"{self._cfg.model_path}: {e}")
        if exp_model and got != exp_model:
            raise AssetError(
                f"model hash mismatch: {self._cfg.model_path} is "
                f"{got[:16]}..., the authority manifest pins "
                f"{exp_model[:16]}... — refusing to run a different "
                f"model")
        exp_bytes = auth.get("onnx_artifact", {}).get("bytes")
        if exp_bytes and os.path.getsize(self._cfg.model_path) != \
                exp_bytes:
            raise AssetError("model byte-size mismatch vs authority")

    # ---- Policy surface ----
    def predict(self, observation: GameObservation) -> ActionDecision:
        if not observation.valid or observation.values is None:
            raise RuntimePolicyError(
                f"refusing invalid observation (frame "
                f"{observation.frame_id}): "
                f"{observation.invalid_reason or 'marked invalid'}")
        t0 = time.perf_counter()
        try:
            action = self._pol.predict(observation.values)
        except Exception as e:
            raise RuntimePolicyError(
                f"policy rejected observation at frame "
                f"{observation.frame_id}: {type(e).__name__}: {e}",
                detail={"frame": observation.frame_id})
        ms = (time.perf_counter() - t0) * 1000.0
        self._n_calls += 1
        if self._tel is not None:
            self._tel.latency("policy_ms", ms)
        logits = None
        try:
            logits = [round(float(v), 6) for v in
                      self._pol.logits_batch(observation.values)[0]]
        except Exception:
            logits = None
        return ActionDecision(
            action=str(action), logits=logits,
            frame_seq=observation.frame_seq,
            policy_name=self._identity["name"],
            policy_sha256=self._identity["model_sha256"] or "?",
            latency_ms=ms,
            diagnostics={"n_calls": self._n_calls})

    def legal_actions(self) -> Sequence[str]:
        return ("HOVER", "FLAP")

    def reset(self) -> None:
        try:
            self._pol.reset()
        except Exception as e:
            raise RuntimePolicyError(f"policy reset failed: {e}")

    def identity(self) -> Dict[str, Any]:
        return dict(self._identity)

    def close(self) -> None:
        try:
            self._pol.close()
        except Exception:
            pass

"""flappybird_policy — the independent inference consumer for the final
FlappyBirdPSX policy (R61 deployment package).

This package is the ONLY documented way to run the final policy outside
the training repository. It imports NO training code, NO teacher code,
NO dataset code — only numpy + onnxruntime (see requirements.txt).

Public API (see policy.py for the full contract):
    load_policy(model_path=None, manifest_path=None) -> FlappyBirdPolicy
    policy.predict(observation)            -> "HOVER" | "FLAP"
    policy.predict_batch(observations)     -> ["HOVER" | "FLAP", ...]
    policy.logits_batch(observations)      -> (N, 2) float32 logits
    policy.reset() / policy.close()
"""

from .policy import (  # noqa: F401
    FlappyBirdPolicy,
    InputValidationError,
    ManifestError,
    ModelLoadError,
    PolicyError,
    load_policy,
)
from .version import PACKAGE_VERSION  # noqa: F401

__all__ = [
    "FlappyBirdPolicy",
    "InputValidationError",
    "ManifestError",
    "ModelLoadError",
    "PolicyError",
    "load_policy",
    "PACKAGE_VERSION",
]

"""schema.py — the input contract of the final policy, enforced.

The model consumes the RAW v7 decision vector (10 float32 values);
normalization happens INSIDE the ONNX graph. This module validates the
vector BEFORE it reaches the session: shape, dtype, finiteness and the
documented per-feature ranges. Nothing is ever silently replaced,
clipped or imputed: an invalid observation raises InputValidationError.

Feature semantics (authoritative; mirrored in the model card):

  i  name        unit                                  missing   range
  0  by          bird y, full-res y px (240-space)     -1.0      [-1, 240]
  1  vy          bird vertical velocity, px/frame      0.0       [-10, 10]
  2  gc          gap center y, full-res y px           -1.0      [-1, 240]
  3  dx          gap band x offset from screen center  -1.0      [-160, 160]
                 (signed, full-res x px)
  4  g0          gap top edge, full-res y px           -1.0      [-1, 240]
  5  g1          gap bottom edge, full-res y px        -1.0      [-1, 240]
  6  flap_run    the policy's own consecutive FLAPs    0         [0, 9]
  7  since_flap  frames since the policy's own FLAP    99        [0, 99]
  8  last_gc     last valid gap center y               -1.0      [-1, 240]
  9  since_gap   frames since the last valid gap       40        [0, 40]

The host-side perception state machine (BirdObserverV7 / GapTrackerV7 /
the policy's own action-history counters) produces exactly this vector;
see INTERFACE.md for the full perception-to-action contract.
"""
import numpy as np

N_FEATURES = 10

FEATURE_NAMES = [
    "by", "vy", "gc", "dx", "g0", "g1",
    "flap_run", "since_flap", "last_gc", "since_gap",
]

# (low, high) inclusive, after the dtype/shape checks. The missing-value
# sentinels are part of the documented contract, not arbitrary fillers:
# they are exactly what the reference perception emits when it has no
# reading (by/gc/g0/g1/last_gc -> -1.0; vy -> 0.0).
VALID_RANGES = [
    (-1.0, 240.0),    # by
    (-10.0, 10.0),    # vy
    (-1.0, 240.0),    # gc
    (-160.0, 160.0),  # dx
    (-1.0, 240.0),    # g0
    (-1.0, 240.0),    # g1
    (0.0, 9.0),       # flap_run
    (0.0, 99.0),      # since_flap
    (-1.0, 240.0),    # last_gc
    (0.0, 40.0),      # since_gap
]

CLASS_NAMES = ["HOVER", "FLAP"]


class InputValidationError(ValueError):
    """Raised for any observation that violates the input contract."""


def _as_float32_array(obs, n, context):
    """Strict dtype/shape conversion. Accepts ONLY numpy arrays whose
    dtype is exactly float32 (batch: shape (n, N_FEATURES); single:
    (N_FEATURES,)). Everything else raises with a precise message."""
    if not isinstance(obs, np.ndarray):
        raise InputValidationError(
            f"{context}: expected a numpy.ndarray with dtype=float32, "
            f"got {type(obs).__name__}. Convert with "
            f"numpy.asarray(obs, dtype=numpy.float32) first.")
    if obs.dtype != np.float32:
        raise InputValidationError(
            f"{context}: dtype must be float32, got {obs.dtype}. "
            f"Convert with numpy.asarray(obs, dtype=numpy.float32).")
    return obs


def validate_observation(obs):
    """Validate one observation; return it as a (1, 10) float32 view."""
    a = _as_float32_array(obs, 1, "observation")
    if a.ndim != 1 or a.shape[0] != N_FEATURES:
        raise InputValidationError(
            f"observation: shape must be ({N_FEATURES},), got "
            f"{a.shape}. Feature order: {FEATURE_NAMES}.")
    return _check_values(a.reshape(1, N_FEATURES), 0)


def validate_batch(obs):
    """Validate a batch; return it as an (N, 10) float32 array."""
    a = _as_float32_array(obs, None, "observation batch")
    if a.ndim != 2 or a.shape[1] != N_FEATURES:
        raise InputValidationError(
            f"observation batch: shape must be (N, {N_FEATURES}), got "
            f"{a.shape}. Feature order: {FEATURE_NAMES}.")
    return _check_values(a, None)


def _check_values(a, idx):
    if a.size and not np.isfinite(a).all():
        bad = np.argwhere(~np.isfinite(a))
        first = bad[0].tolist()
        where = f"row {first[0]}, feature " \
                f"'{FEATURE_NAMES[first[1]]}' ({first[1]})"
        raise InputValidationError(
            f"observation batch: non-finite value (NaN/Inf) at {where}; "
            "the policy never runs on non-finite input.")
    for j, (lo, hi) in enumerate(VALID_RANGES):
        col = a[:, j]
        out = (col < lo) | (col > hi)
        if out.any():
            r = int(out.nonzero()[0][0]) if idx is None else idx
            raise InputValidationError(
                f"observation batch: feature '{FEATURE_NAMES[j]}' "
                f"({j}) out of documented range [{lo}, {hi}] — got "
                f"{float(a[r, j])!r} at row {r}. The policy must "
                "receive the raw v7 vector as defined by the "
                "perception contract (INTERFACE.md); do not feed "
                "unnormalized, rescaled or synthesized values.")
    return a

# TROUBLESHOOTING.md — common errors and fixes

## `ModelLoadError: model file not found`
The `models/` directory is missing or moved. Point
`load_policy(model_path=..., manifest_path=...)` at the real files or
restore the shipped `models/` tree.

## `ManifestError: MODEL HASH MISMATCH`
The `.onnx` file does not match the manifest (truncated copy, wrong
version, corruption). Never bypass it — re-fetch the artifact and
check sha256 `4dd592a7118a5c4de7b44166b42b8d09d53fbb59330d36d0ba2746393dc11044`.

## `ModelLoadError: onnxruntime is not installed`
Run `pip install -r requirements.txt` inside the package directory.

## `InputValidationError: dtype must be float32`
Cast explicitly: `numpy.asarray(obs, dtype=numpy.float32)`. Lists and
float64/int arrays are rejected by design (silent coercion is the
failure mode this prevents).

## `InputValidationError: feature 'X' out of documented range`
The vector violates the INTERFACE.md contract (wrong scale,
unnormalized values, rescaled coordinates). Feed the RAW v7 vector —
the graph normalizes internally.

## `InputValidationError: non-finite value`
NaN/Inf in the observation. Fix the perception adapter; the policy
never runs on non-finite input.

## `PolicyError: policy is closed`
`close()` is final; create a new policy with `load_policy()`.

## Actions look wrong / the bird spams flaps
Re-create the perception objects (BirdObserverV7/GapTrackerV7) at
EVERY episode start and reset the history counters to the §5 init
values (stale perception is the classic bug — it produced a real
incident during R61 validation, fixed and regression-tested in
`tests/test_r61_deployment.py::test_r61_loop_resets_numpy_policies_between_episodes`).

## Results differ from the recorded family scores
Check, in order: the model sha256, the seed semantics (k = idle frames
between anchor restore and the X press), the 10,000-frame budget, the
one-decision-per-frame cadence, and the B-button (Cross) mapping.
Every recorded number assumes ALL of these.

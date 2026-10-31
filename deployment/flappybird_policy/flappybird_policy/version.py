"""Package version — independent of the training implementation.

The version records the deployment package's own evolution; the MODEL
identity is the ONNX sha256 exposed by the loaded policy (never bump a
model without a new manifest).
"""

PACKAGE_VERSION = "1.0.0"

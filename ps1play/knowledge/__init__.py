"""ps1play.knowledge — compact, provenance-aware per-game knowledge capsules.

Design contract (Issue #10 addendum):
- Every fact carries a STATUS: VERIFIED | OBSERVED | INFERRED | UNKNOWN |
  CONTRADICTED | BLOCKED.
- VERIFIED/OBSERVED facts MUST carry provenance (source url or probe id,
  plus an evidence reference: frame/event, artifact hash, or doc path).
- Capsules stay portable: <64 KiB target, >128 KiB rejected on save.
- Large artifacts (disassembly, dumps, screenshots, traces) live in the
  local cache and are referenced by stable id + hash + path, never embedded.
- Unverified hypotheses are never silently promoted; reward/ground-truth
  consumers must request status >= OBSERVED explicitly.
"""
from .capsule import (  # noqa: F401
    FACT_STATUSES,
    CAPSULE_WARN_BYTES,
    CAPSULE_MAX_BYTES,
    Capsule,
    CapsuleError,
    MemoryField,
    Provenance,
    require_observable,
)
from .cache import AnalysisCache  # noqa: F401
from .cache import UnsupportedAddress  # noqa: F401

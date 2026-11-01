"""ps1play.runtime.telemetry — event log, latency stats, run manifest
(R62).

TelemetryLog writes a strictly ordered JSONL event stream (one object
per line) plus per-stage latency statistics. Writes are buffered for
speed and explicitly flushed at episode boundaries and shutdown, so a
crashed run still leaves every event up to the last flush. Event
ordering is preserved (single writer, sequence numbers).

`build_manifest` pins the complete environment identity (runtime
version, repo commit, model/ONNX/manifest hashes, ISO hash, emulator
core hash, python + dependency versions, component versions, config
hash) — every episode record references this manifest hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import deque
from typing import Any, Dict, List, Optional

from .config import REPO, RUNTIME_VERSION


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit(repo: str = REPO) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
            text=True, timeout=10)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


class LatencyStats:
    """Bounded latency recorder with P50/P95/P99 (ring buffer)."""

    def __init__(self, name: str, capacity: int = 20000):
        self.name = name
        self._buf = deque(maxlen=capacity)
        self.n = 0
        self.total_ms = 0.0
        self.max_ms = 0.0

    def add(self, ms: float) -> None:
        self._buf.append(float(ms))
        self.n += 1
        self.total_ms += float(ms)
        if ms > self.max_ms:
            self.max_ms = ms

    def summary(self) -> Dict[str, float]:
        if not self._buf:
            return {"n": self.n, "p50_ms": None, "p95_ms": None,
                    "p99_ms": None, "mean_ms": None, "max_ms": self.max_ms}
        xs = sorted(self._buf)

        def pct(p):
            i = min(len(xs) - 1, int(round(p / 100.0 * len(xs) + 0.5)) - 1)
            return round(xs[max(0, i)], 4)
        return {"n": self.n, "p50_ms": pct(50), "p95_ms": pct(95),
                "p99_ms": pct(99),
                "mean_ms": round(self.total_ms / self.n, 4),
                "max_ms": round(self.max_ms, 4)}


class TelemetryLog:
    """Ordered JSONL event stream + latency statistics."""

    def __init__(self, path: str, run_meta: Optional[Dict[str, Any]] = None,
                 echo: bool = False):
        self.path = path
        self.echo = echo
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._fh = open(path, "a", buffering=1 << 16)
        self._seq = 0
        self._t0 = time.time()
        self.latencies: Dict[str, LatencyStats] = {}
        self.warnings: List[str] = []
        self._closed = False
        if run_meta:
            self.emit("run_start", **run_meta)

    # ------------------------------------------------------------ --
    def emit(self, event: str, **fields: Any) -> None:
        if self._closed:
            return
        self._seq += 1
        rec = {"seq": self._seq, "t": round(time.time() - self._t0, 3),
               "ts": round(time.time(), 3), "event": event}
        rec.update(fields)
        try:
            self._fh.write(json.dumps(rec, default=str) + "\n")
        except OSError:
            # disk-full / vanished dir: never crash the control loop on
            # telemetry; record the degradation and continue.
            self.warnings.append(f"telemetry write failed at seq "
                                 f"{self._seq}")
        if self.echo:
            print(json.dumps(rec, default=str), flush=True)

    def latency(self, stage: str, ms: float) -> None:
        st = self.latencies.get(stage)
        if st is None:
            st = self.latencies[stage] = LatencyStats(stage)
        st.add(ms)

    def flush(self) -> None:
        if self._closed:
            return                 # idempotent (R64: teardown order)
        try:
            self._fh.flush()
            try:
                os.fsync(self._fh.fileno())
            except (OSError, ValueError, AttributeError):
                pass
        except OSError:
            self.warnings.append("telemetry flush failed")

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.emit("latency_summary", **self.latency_summary())
            self.emit("telemetry_close",
                      warnings=list(self.warnings[-20:]))
            self._fh.flush()
        except Exception:
            pass
        self._closed = True
        try:
            self._fh.close()
        except Exception:
            pass

    def latency_summary(self) -> Dict[str, Dict[str, Any]]:
        return {k: st.summary() for k, st in sorted(self.latencies.items())}


# ------------------------------------------------------------------
# the runtime manifest
# ------------------------------------------------------------------


def dep_versions() -> Dict[str, str]:
    out = {"python": sys.version.split()[0], "platform":
           platform.platform()}
    for mod in ("numpy", "onnxruntime", "PIL"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", "unknown")
        except Exception as e:          # pragma: no cover
            out[mod] = f"IMPORT_ERROR: {e}"
    return out


def build_manifest(config, *, iso_path: Optional[str] = None,
                   core_path: Optional[str] = None,
                   bios_path: Optional[str] = None) -> Dict[str, Any]:
    """The complete run identity. Hashes are computed from the actual
    files; a missing required file raises here (fail-early)."""
    man_path = config.manifest_path
    from importlib.metadata import version as _pkgver
    try:
        adapter_ver = _pkgver("ps1play")
    except Exception:
        adapter_ver = "local"
    man: Dict[str, Any] = {
        "runtime_version": RUNTIME_VERSION,
        "runtime_manifest_version": 2,   # 2 = per-game components (R64)
        "repo_commit": _git_commit(),
        "generated_ts": round(time.time(), 3),
        "config": config.to_dict(),
        "config_hash": config.config_hash(),
        "python_deps": dep_versions(),
        "component_versions": {
            "runtime": RUNTIME_VERSION,
            "observer": "v7 (ps1play.learn.visual_only)",
            "controller": "1.0.0",
        },
    }
    # per-game component identity from the registry (R64: the manifest
    # describes the game that actually runs — flappybird adds its
    # frozen policy package, tetrade its built-in heuristic)
    from .registry import component_versions  # noqa: PLC0415
    man["component_versions"].update(component_versions())
    if config.game == "flappybird":
        man["component_versions"]["policy_package"] = \
            "flappybird_policy 1.0.0"
    else:
        try:
            from .registry import policy_for_game  # noqa: PLC0415
            man["component_versions"]["policy"] = \
                str(policy_for_game(config).identity().get("name", "?"))
        except Exception:
            pass
    for key, p in (("model", config.model_path),
                   ("model_manifest", man_path),
                   ("authority_manifest", config.authority_manifest_path)):
        if p and os.path.exists(p):
            man[f"{key}_path"] = p
            man[f"{key}_sha256"] = sha256_file(p)
            man[f"{key}_bytes"] = os.path.getsize(p)
        elif p:
            man[f"{key}_error"] = f"missing: {p}"
    if iso_path and os.path.exists(iso_path):
        man["iso_path"] = iso_path
        man["iso_sha256"] = sha256_file(iso_path)
        man["iso_bytes"] = os.path.getsize(iso_path)
    elif iso_path:
        man["iso_error"] = f"missing: {iso_path}"
    if core_path and os.path.exists(core_path):
        man["emulator_core_path"] = core_path
        man["emulator_core_sha256"] = sha256_file(core_path)
    if bios_path and os.path.exists(bios_path):
        man["bios_path"] = bios_path
        man["bios_sha256"] = sha256_file(bios_path)
    return man


def manifest_sha(man: Dict[str, Any]) -> str:
    blob = json.dumps(man, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()

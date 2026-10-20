"""labconfig.py — the shared, explicit configuration contract (v0.12).

Every runner (autolab, env_probe, the real-game probes and the Mission-1
runner) resolves paths and firmware through THIS module so that a
passing environment probe and a gameplay run can never silently use
different bytes.

Resolution order (highest priority first):
  1. explicit function/CLI argument
  2. environment variable (M1_GAME, M1_CORE, M1_WORKSPACE, M1_EVID,
     M1_PROFILE_DIR, M1_FIRMWARE)
  3. machine-local config file ``<repo>/.autolab_config.json``
     (never committed; gitignored) with keys
     ``game/core/workspace/evidence_dir/profile_dir``
  4. repo-root-relative fallbacks where meaningful

Firmware modes (never switched silently):
  * ``openbios`` — the MIT-licensed OpenBIOS shipped in
    ``third_party/openbios`` (hash-verified) via the core's official
    override variable ``beetle_psx_override_bios=openbios``.
  * ``retail``   — a region-correct retail BIOS in
    ``<workspace>/system`` (NTSC-U: scph5501.bin, MD5-verified). The
    core's silent embedded-OpenBIOS fallback is NOT retail; if the log
    shows fallback, the run fails early.
  * ``auto``     — retail when a validated retail BIOS is present,
    otherwise openbios. The chosen mode is returned and must be
    recorded in every report.
"""
import hashlib
import json
import os

# ------------------------------------------------------------------
# BIOS truth table (single source; scripts/env_probe re-exports these
# names so tests/test_bios_truth.py keeps working).
# ------------------------------------------------------------------
BIOS_NAMES = ("scph5501.bin", "scph5500.bin", "scph5502.bin")
BIOS_MD5_OK = "490f666e1afb15b7362b406ed1cea246"          # SCPH-5501 NTSC-U
BIOS_SHA1_OK = "0555c6fae8906f3f09baf5988f00e55f88e9f30b"
KNOWN_UNSUPPORTED_BIOS_MD5 = {
    "4dc4690a277144675bfe5ac5aaf5896d": "SCPH-1001 (NTSC-U retail)",
    "30a25911fa858048e8adde16590f218a": "SCPH-7502 (PAL retail)",
}
OPENBIOS_MD5 = "664ee444f38f6008d0cffc9d23e5c40d"
OVERRIDE_VAR = b"beetle_psx_override_bios"
OVERRIDE_VALUE = b"openbios"
FIRMWARE_MODES = ("auto", "openbios", "retail")


class ConfigError(Exception):
    """Raised when a required configuration piece cannot be resolved."""


class FirmwareError(ConfigError):
    """Raised when the requested firmware mode cannot be satisfied."""


def repo_root():
    """Repository root derived from THIS file's location."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def machine_config_path(root=None):
    return os.path.join(root or repo_root(), ".autolab_config.json")


def load_machine_config(root=None):
    """Read the gitignored machine-local config, {} when absent."""
    p = machine_config_path(root)
    if os.path.exists(p):
        try:
            with open(p) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {}


# ------------------------------------------------------------------
# path resolution
# ------------------------------------------------------------------
def resolve_path(kind, explicit=None, env=None, root=None):
    """Resolve one path: arg > env var > machine config.

    Returns the resolved path or None. Does NOT require existence;
    callers decide whether a None/missing path is fatal.
    """
    env = os.environ if env is None else env
    if explicit:
        return explicit
    env_var = {"game": "M1_GAME", "core": "M1_CORE",
               "workspace": "M1_WORKSPACE", "evidence_dir": "M1_EVID",
               "profile_dir": "M1_PROFILE_DIR"}.get(kind)
    if env_var and env.get(env_var):
        return env[env_var]
    cfg = load_machine_config(root)
    val = cfg.get(kind)
    return val if isinstance(val, str) and val else None


def resolve_config(game=None, core=None, workspace=None,
                   evidence_dir=None, profile_dir=None, env=None,
                   root=None):
    """Resolve all runner paths at once (arg > env > machine config)."""
    return {
        "game": resolve_path("game", game, env, root),
        "core": resolve_path("core", core, env, root),
        "workspace": resolve_path("workspace", workspace, env, root),
        "evidence_dir": resolve_path("evidence_dir", evidence_dir, env,
                                     root),
        "profile_dir": resolve_path("profile_dir", profile_dir, env,
                                    root),
    }


def require(kind, path):
    """Turn a missing required path into a concise actionable error."""
    if not path:
        raise ConfigError(
            f"{kind}: not configured — pass it explicitly, set the "
            f"M1_{kind.upper()} environment variable, or create "
            f"{machine_config_path()}")
    if not os.path.exists(path):
        raise ConfigError(f"{kind}: file not found: {path}")
    return path


# ------------------------------------------------------------------
# content validation
# ------------------------------------------------------------------
def validate_cue(game):
    """Validate a game image path: cue references must exist.

    Returns (ok, detail). Non-cue files are checked for existence and
    non-zero size only.
    """
    if not game or not os.path.exists(game):
        return False, f"not found: {game}"
    if not game.lower().endswith(".cue"):
        size = os.path.getsize(game)
        return (size > 0,
                f"{os.path.basename(game)} ({size} bytes, non-cue)")
    gdir = os.path.dirname(game)
    try:
        with open(game, "r", errors="replace") as f:
            cue = f.read()
    except OSError as e:
        return False, f"cue unreadable: {e}"
    bins = [ln.split('"')[1] for ln in cue.splitlines() if 'FILE "' in ln]
    if not bins:
        return False, "cue contains no FILE entries"
    for b in bins:
        bp = os.path.join(gdir, b)
        if not os.path.exists(bp):
            return False, f"cue references missing file {b}"
        if os.path.getsize(bp) <= 0:
            return False, f"cue reference is empty: {b}"
    return True, (f"cue ok: {len(bins)} track file(s), "
                  f"{os.path.getsize(os.path.join(gdir, bins[0]))} bytes "
                  f"total for {bins[0]}")


def file_md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------
# firmware selection (never silent)
# ------------------------------------------------------------------
def classify_bios(filename, md5hex):
    """Pure classifier: what will THIS core build do with a BIOS file?

    Verdicts: RETAIL_OK | OPENBIOS_OK | KNOWN_UNSUPPORTED | UNKNOWN.
    (Identical semantics to scripts/env_probe.classify_bios, which now
    delegates here; kept in ps1play/ so the library and every script
    share one truth table.)
    """
    name = (filename or "").lower()
    if name == "openbios.bin":
        if md5hex == OPENBIOS_MD5:
            return "OPENBIOS_OK", (
                "open-source BIOS replacement (MIT, PCSX-Redux) — use "
                "with beetle_psx_override_bios=openbios; its shell "
                "cannot drive retail-menu flows by itself")
        return "UNKNOWN", "openbios.bin with unexpected md5 — re-verify"
    if name in BIOS_NAMES:
        if name == "scph5501.bin" and md5hex == BIOS_MD5_OK:
            return "RETAIL_OK", (
                "SCPH-5501 NTSC-U retail — accepted by the core region "
                "list; required for SLUS-01212 retail runs")
        return "UNKNOWN", (
            f"{name} present but md5 {md5hex} is not the verified "
            "NTSC-U hash — the core will warn and may misbehave")
    if md5hex in KNOWN_UNSUPPORTED_BIOS_MD5:
        label = KNOWN_UNSUPPORTED_BIOS_MD5[md5hex]
        return "KNOWN_UNSUPPORTED", (
            f"{label}: this core build rejects it by name+SHA1 region "
            "gate (libretro.c firmware_is_present); booting will "
            "SILENTLY FALL BACK to the core's embedded OpenBIOS")
    return "UNKNOWN", (
        f"{filename} md5 {md5hex} not in any verified list — run "
        "scripts/bios_probe.py for an executable boot verdict")


def _scan_system_bios(workspace):
    """Return the first RETAIL_OK candidate in <workspace>/system."""
    sysdir = os.path.join(workspace, "system") if workspace else None
    if not sysdir or not os.path.isdir(sysdir):
        return None
    for fn in sorted(os.listdir(sysdir)):
        if not fn.lower().endswith(".bin"):
            continue
        bp = os.path.join(sysdir, fn)
        try:
            md5hex = file_md5(bp)
        except OSError:
            continue
        verdict, detail = classify_bios(fn, md5hex)
        if verdict == "RETAIL_OK":
            return {"path": bp, "file": fn, "md5": md5hex,
                    "verdict": verdict, "detail": detail}
    return None


def resolve_firmware(mode="auto", workspace=None, root=None):
    """Resolve the firmware mode EXPLICITLY. Never falls back silently.

    Returns a dict: {mode, bios_path, bios_md5, override_vars, detail}.
    Raises FirmwareError when the requested mode cannot be satisfied.
    """
    root = root or repo_root()
    if mode not in FIRMWARE_MODES:
        raise FirmwareError(
            f"unknown firmware mode {mode!r} — expected one of "
            f"{', '.join(FIRMWARE_MODES)}")
    openbios_path = os.path.join(root, "third_party", "openbios",
                                 "openbios.bin")
    retail = _scan_system_bios(workspace) if workspace else None

    def openbios_ok():
        if not os.path.exists(openbios_path):
            return False
        try:
            return file_md5(openbios_path) == OPENBIOS_MD5
        except OSError:
            return False

    def openbios_rec(detail=None):
        return {"mode": "openbios", "bios_path": openbios_path,
                "bios_md5": OPENBIOS_MD5,
                "override_vars": {OVERRIDE_VAR: OVERRIDE_VALUE},
                "detail": detail or (
                    "OpenBIOS (MIT, PCSX-Redux) via the core's official "
                    "override path")}

    def retail_rec():
        return {"mode": "retail", "bios_path": retail["path"],
                "bios_md5": retail["md5"], "override_vars": None,
                "detail": (f"retail BIOS {retail['file']} accepted by "
                           "the core region list")}

    if mode == "openbios":
        if not openbios_ok():
            raise FirmwareError(
                f"firmware mode 'openbios' requested but "
                f"{openbios_path} is missing or its md5 is not "
                f"{OPENBIOS_MD5}")
        return openbios_rec()
    if mode == "retail":
        if retail is None:
            raise FirmwareError(
                "firmware mode 'retail' requested but no validated "
                f"retail BIOS found in {os.path.join(workspace or '.', 
                'system')} — supply scph5501.bin (MD5 {BIOS_MD5_OK}) "
                "there, or request mode 'openbios' explicitly")
        return retail_rec()
    # auto: retail first, then openbios — the RESULT records which one
    if retail is not None:
        return retail_rec()
    if openbios_ok():
        return openbios_rec(
            "auto: no validated retail BIOS in system/ -> OpenBIOS "
            "override (recorded, not silent)")
    raise FirmwareError(
        "firmware mode 'auto' cannot be satisfied: no validated retail "
        "BIOS in system/ and no valid third_party/openbios image")


def firmware_log_evidence(log_history):
    """Extract firmware truth from the core's own log lines."""
    lines = list(log_history or [])
    joined = "\n".join(str(l) for l in lines)
    return {
        "override_found": "Override firmware found" in joined,
        "fallback": "Firmware is missing" in joined,
        "log_tail": lines[-8:],
    }


def check_firmware_trust(fw_res, log_evidence):
    """Verify the core's runtime log MATCHES the requested mode.

    Returns (ok, detail). This is what stops a 'retail' run from being
    an embedded-OpenBIOS fallback in disguise, or an 'openbios' run
    from actually using a rejected retail file through the fallback.
    """
    mode = fw_res["mode"]
    if mode == "openbios":
        if log_evidence["override_found"]:
            return True, "override engaged (core log: Override firmware found)"
        if log_evidence["fallback"]:
            return False, (
                "openbios mode requested but the core logged 'Firmware "
                "is missing' — the override did not engage; refusing "
                "to continue")
        return False, (
            "openbios mode requested but the core log shows no "
            "'Override firmware found' evidence")
    if mode == "retail":
        if log_evidence["fallback"]:
            return False, (
                "retail mode requested but the core logged 'Firmware "
                "is missing' — this run is on the core's embedded "
                "OpenBIOS fallback, NOT retail; refusing to continue")
        return True, "retail BIOS accepted (no fallback in core log)"
    return True, "auto mode: recorded log evidence only"

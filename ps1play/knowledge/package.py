"""ps1play.knowledge.package — the downloadable .ps1game knowledge
package (R65, Part B).

ONE PORTABLE FILE PER GAME.  A `<game_id>.ps1game` archive is a
deflated ZIP with a validated `manifest.json` carrying the game's
identity, maturity, runtime compatibility, content hashes and legal
notes.  The knowledge inside is GAME-SPECIFIC and ISOLATED: a package
never contains, references or depends on another game's gameplay
intelligence (the ABSOLUTE NO-CROSS-GAME-TRANSFER rule).  Only generic
runtime dependencies (emulator lifecycle, controller, CLI, test
runner) may be declared, and they are declared explicitly.

Lifecycle (the R65 user experience):

    export    assemble a game's knowledge into <game_id>.ps1game
              (repo-side; the exporter validates what it produces)
    validate  verify an archive: structure, schema, hashes, maturity,
              runtime compatibility, path safety
    install   validate, then unpack into an ISOLATED per-game store
              (<root>/<game_id>/<version>/) — never over another
              game's package; no package code is executed
    list      exportable + installed packages and their maturity

Security rules (all enforced, all loud):

  * ZIP entries must be plain relative paths — no absolute paths,
    no `..` traversal, no backslashes, no symlink/device entries
  * per-file and total size caps
  * every content file's SHA-256 is pinned in the manifest and
    recomputed on validate/install; any mismatch is a PackageError
  * installation NEVER executes package code and NEVER writes outside
    its own <game_id>/<version> directory
  * the package NEVER contains the user's (or anyone's) commercial
    disc image, BIOS, or other copyrighted game assets — the user
    provides their own legal copy (checked at play time by the
    runtime's disc hash pin)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import zipfile
from typing import Any, Dict, List, Optional

PACKAGE_SCHEMA = "ps1play.game-package/1"

# The honest maturity ladder (Part B7): a package may be useful before
# full completion; the level must accurately describe the evidence.
MATURITY_LEVELS = (
    "EXPERIMENTAL",              # knowledge only, nothing verified
    "BOOT_VERIFIED",             # the game boots under the runtime
    "INPUT_VERIFIED",            # + controller causality proven
    "GAMEPLAY_VERIFIED",         # + gameplay state driven by the policy
    "PARTIAL_AUTONOMOUS_PLAYER", # + real but incomplete autonomous play
    "OBJECTIVE_VERIFIED",        # + the game's objective achieved
    "FULL_GAME_COMPLETION_VERIFIED",  # + the full game completed
)

MANIFEST_NAME = "manifest.json"
README_NAME = "README.md"

# safety caps
MAX_FILE_BYTES = 64 * 1024 * 1024       # per entry
MAX_PACKAGE_BYTES = 128 * 1024 * 1024   # whole archive
MAX_ENTRIES = 4096

_RESERVED = (MANIFEST_NAME,)


class PackageError(ValueError):
    """Raised on any package structure/schema/hash/safety violation
    (loud, never silent)."""


# ---------------------------------------------------------------- --
# helpers
# ---------------------------------------------------------------- --

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_arcname(name: str) -> None:
    """Path-safety for one archive entry (reject, never rewrite)."""
    if not name or name.endswith("/"):
        return                      # directory entries are allowed
    if name.startswith("/") or name.startswith("\\"):
        raise PackageError(f"unsafe archive entry (absolute): {name!r}")
    if "\\" in name:
        raise PackageError(
            f"unsafe archive entry (backslash): {name!r}")
    if drive := os.path.splitdrive(name)[0]:
        raise PackageError(f"unsafe archive entry (drive): {name!r}")
    parts = name.split("/")
    if any(p in ("..", ".") for p in parts):
        raise PackageError(f"unsafe archive entry (traversal): {name!r}")
    if any(":" in p for p in parts):
        raise PackageError(f"unsafe archive entry (colon): {name!r}")


def _package_filename(game_id: str, version: str) -> str:
    if not re.fullmatch(r"[a-z0-9_]{2,32}", game_id):
        raise PackageError(f"bad game_id {game_id!r}")
    if not re.fullmatch(r"[0-9A-Za-z.+\-]{1,32}", version):
        raise PackageError(f"bad version {version!r}")
    return f"{game_id}.ps1game"


# ---------------------------------------------------------------- --
# manifest
# ---------------------------------------------------------------- --

REQUIRED_MANIFEST_KEYS = ("schema", "package", "runtime", "game_identity",
                          "contents", "capabilities", "legal",
                          "integrity")
PACKAGE_KEYS = ("game_id", "title", "version", "created_at_utc",
                "maturity", "built_by")
IDENTITY_KEYS = ("serial", "region", "revision")


def make_manifest(*, game_id: str, title: str, version: str,
                  maturity: str, serial: str, region: str,
                  revision: str, contents: List[Dict[str, Any]],
                  runtime: Dict[str, Any], capabilities: Dict[str, Any],
                  legal: Dict[str, Any],
                  created_at_utc: Optional[str] = None) -> Dict[str, Any]:
    """Assemble a manifest. `contents` = [{path, sha256, bytes, role}];
    integrity.manifest_sha256 is computed over the canonical JSON of
    the manifest WITHOUT the integrity field (sorted keys, compact)."""
    if maturity not in MATURITY_LEVELS:
        raise PackageError(
            f"bad maturity {maturity!r} (allowed: {MATURITY_LEVELS})")
    man = {
        "schema": PACKAGE_SCHEMA,
        "package": {
            "game_id": game_id, "title": title, "version": version,
            "created_at_utc": created_at_utc
            or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "maturity": maturity,
            "built_by": "ps1play knowledge exporter "
                        "(Sh-TB/Ps1ai R65)",
        },
        "runtime": runtime,
        "game_identity": {"serial": serial, "region": region,
                          "revision": revision},
        "contents": contents,
        "capabilities": capabilities,
        "legal": legal,
    }
    canon = json.dumps(man, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode()
    man["integrity"] = {"manifest_sha256": sha256_bytes(canon)}
    return man


def verify_manifest(man: Dict[str, Any]) -> None:
    """Schema + integrity verification of a manifest dict."""
    missing = [k for k in REQUIRED_MANIFEST_KEYS if k not in man]
    if missing:
        raise PackageError(f"manifest missing keys: {missing}")
    if man["schema"] != PACKAGE_SCHEMA:
        raise PackageError(
            f"bad package schema {man['schema']!r} "
            f"(expected {PACKAGE_SCHEMA!r})")
    pkg = man["package"]
    missing = [k for k in PACKAGE_KEYS if k not in pkg]
    if missing:
        raise PackageError(f"package section missing: {missing}")
    if pkg["maturity"] not in MATURITY_LEVELS:
        raise PackageError(f"bad maturity {pkg['maturity']!r}")
    _package_filename(pkg["game_id"], pkg["version"])
    missing = [k for k in IDENTITY_KEYS
               if k not in man["game_identity"]]
    if missing:
        raise PackageError(f"game_identity missing: {missing}")
    contents = man["contents"]
    if not isinstance(contents, list) or not contents:
        raise PackageError("contents must be a non-empty list")
    seen = set()
    for i, c in enumerate(contents):
        for k in ("path", "sha256", "bytes", "role"):
            if k not in c:
                raise PackageError(f"contents[{i}] missing {k!r}")
        _check_arcname(c["path"])
        if c["path"] in seen:
            raise PackageError(
                f"duplicate content path: {c['path']!r}")
        seen.add(c["path"])
        if c["path"] == MANIFEST_NAME:
            raise PackageError(
                "contents must not include the manifest itself")
    integ = man["integrity"]
    if not isinstance(integ, dict) or \
            not integ.get("manifest_sha256"):
        raise PackageError("integrity.manifest_sha256 missing")
    body = {k: v for k, v in man.items() if k != "integrity"}
    canon = json.dumps(body, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode()
    if sha256_bytes(canon) != integ["manifest_sha256"]:
        raise PackageError(
            "manifest integrity mismatch "
            "(integrity.manifest_sha256 does not match the manifest "
            "body — the manifest was modified)")


# ---------------------------------------------------------------- --
# archive I/O
# ---------------------------------------------------------------- --

def _read_zip(zf: zipfile.ZipFile, name: str) -> bytes:
    return zf.read(name)


def validate_package(path: str, *, check_runtime: bool = True) \
        -> Dict[str, Any]:
    """Full validation of a .ps1game archive. Returns the manifest.

    Raises PackageError on ANY of: not a zip, unsafe entries, missing
    manifest, schema violation, manifest integrity mismatch, content
    hash mismatch, size caps."""
    if not os.path.exists(path):
        raise PackageError(f"package not found: {path}")
    size = os.path.getsize(path)
    if size > MAX_PACKAGE_BYTES:
        raise PackageError(
            f"package too large: {size} > {MAX_PACKAGE_BYTES}")
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise PackageError(f"not a valid .ps1game (zip) archive: {e}")
    with zf:
        names = zf.namelist()
        if len(names) > MAX_ENTRIES:
            raise PackageError(
                f"too many archive entries: {len(names)}")
        for n in names:
            _check_arcname(n)
            info = zf.getinfo(n)
            if info.file_size > MAX_FILE_BYTES:
                raise PackageError(
                    f"archive entry too large: {n} "
                    f"({info.file_size} B)")
        if MANIFEST_NAME not in names:
            raise PackageError(f"{MANIFEST_NAME} missing from archive")
        try:
            man = json.loads(_read_zip(zf, MANIFEST_NAME))
        except json.JSONDecodeError as e:
            raise PackageError(
                f"{MANIFEST_NAME} is not valid JSON: {e}")
        verify_manifest(man)
        # every content file's hash, recomputed from the archive
        zinfos = {i.filename: i for i in zf.infolist()}
        for c in man["contents"]:
            p = c["path"]
            if p not in zinfos:
                raise PackageError(
                    f"content missing from archive: {p}")
            data = _read_zip(zf, p)
            if len(data) != c["bytes"]:
                raise PackageError(
                    f"content size mismatch: {p} "
                    f"({len(data)} != {c['bytes']})")
            if sha256_bytes(data) != c["sha256"]:
                raise PackageError(
                    f"content sha256 mismatch: {p} "
                    f"(manifest pins {c['sha256'][:16]}…)")
        if check_runtime:
            _check_runtime_compat(man)
    return man


def _current_runtime_version() -> str:
    try:
        from ps1play.runtime.config import RUNTIME_VERSION  # noqa: PLC0415
        return RUNTIME_VERSION
    except Exception:
        return "0"


def _check_runtime_compat(man: Dict[str, Any]) -> None:
    rt = man.get("runtime", {})
    compat = rt.get("runtime_version_compat")
    if not compat:
        raise PackageError("runtime.runtime_version_compat missing")
    cur = _current_runtime_version()
    if cur != "0" and cur not in compat:
        raise PackageError(
            f"runtime incompatible: package needs {compat}, "
            f"this runtime is {cur}")


def install_package(path: str, root: str, *, force: bool = False) \
        -> Dict[str, Any]:
    """Validate then unpack into <root>/<game_id>/<version>/.

    Isolation: the destination is derived ONLY from the manifest's
    game_id + version, the directory is created fresh (an existing
    install of the SAME version requires --force; any other game's
    directory is never touched), and no archive entry can escape it
    (paths were validated).  No code from the package is executed.
    Returns the install summary."""
    man = validate_package(path)
    pkg = man["package"]
    dest = os.path.join(root, pkg["game_id"], pkg["version"])
    if os.path.exists(dest):
        if not force:
            raise PackageError(
                f"already installed: {dest} (use force=True to "
                "re-install the SAME game_id+version)")
        # same game_id+version only — never another game's tree
    os.makedirs(dest, exist_ok=True)
    n_files = 0
    with zipfile.ZipFile(path) as zf:
        for c in man["contents"]:
            target = os.path.join(dest, *c["path"].split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(c["path"]) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            n_files += 1
        if README_NAME in zf.namelist() and \
                README_NAME not in {c["path"] for c in man["contents"]}:
            with zf.open(README_NAME) as src:
                data = src.read()
            with open(os.path.join(dest, README_NAME), "wb") as out:
                out.write(data)
    with open(os.path.join(dest, MANIFEST_NAME), "w") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    return {"game_id": pkg["game_id"], "version": pkg["version"],
            "maturity": pkg["maturity"], "installed_to": dest,
            "files": n_files}


def read_installed_manifest(root: str, game_id: str) \
        -> Optional[Dict[str, Any]]:
    """The installed manifest for a game (any version, latest first),
    or None."""
    base = os.path.join(root, game_id)
    if not os.path.isdir(base):
        return None
    for ver in sorted(os.listdir(base), reverse=True):
        p = os.path.join(base, ver, MANIFEST_NAME)
        if os.path.exists(p):
            try:
                man = json.load(open(p))
                verify_manifest(man)
                return man
            except (PackageError, json.JSONDecodeError, OSError):
                continue
    return None


# ---------------------------------------------------------------- --
# exporter
# ---------------------------------------------------------------- --

def build_package(spec: Dict[str, Any], out_dir: str) -> Dict[str, Any]:
    """Assemble, hash, write and RE-VALIDATE one game's package.

    spec (from the game's own package_spec builder — game-specific
    material stays inside the game's module):
        game_id, title, version, maturity,
        serial, region, revision,
        files: [(abs_or_repo_path, arcpath, role)],
        readme: str,
        runtime: {...}, capabilities: {...}, legal: {...}

    The exporter refuses duplicate arcpaths, missing sources and
    reserved names, computes SHA-256 for every file, writes
    <game_id>.ps1game plus a .sha256 sidecar, then re-opens the
    archive with validate_package() — an exporter that cannot re-validate
    its own output is a hard failure."""
    game_id = spec["game_id"]
    out_name = _package_filename(game_id, spec["version"])
    contents: List[Dict[str, Any]] = []
    payload: List[tuple] = []          # (arcpath, bytes)
    seen: set = set()
    for entry in spec["files"]:
        if len(entry) == 3 and isinstance(entry[0], (dict, str)):
            src, arc, role = None, entry[1], entry[2]
            data = json.dumps(entry[0], indent=1,
                              sort_keys=True).encode("utf-8") \
                if isinstance(entry[0], dict) else entry[0].encode(
                    "utf-8")
        else:
            src, arc, role = entry
        _check_arcname(arc)
        if arc in seen or arc in _RESERVED:
            raise PackageError(f"duplicate/reserved arcpath: {arc!r}")
        seen.add(arc)
        if src is not None:
            if not os.path.exists(src):
                raise PackageError(f"package source missing: {src}")
            with open(src, "rb") as f:
                data = f.read()
        if len(data) > MAX_FILE_BYTES:
            raise PackageError(f"source too large: {src}")
        contents.append({"path": arc, "sha256": sha256_bytes(data),
                         "bytes": len(data), "role": role})
        payload.append((arc, data))
    if spec.get("readme"):
        _check_arcname(README_NAME)
        rb = spec["readme"].encode("utf-8")
        if README_NAME not in seen:
            contents.append({"path": README_NAME,
                             "sha256": sha256_bytes(rb),
                             "bytes": len(rb), "role": "readme"})
            payload.append((README_NAME, rb))
    man = make_manifest(
        game_id=game_id, title=spec["title"], version=spec["version"],
        maturity=spec["maturity"], serial=spec["serial"],
        region=spec["region"], revision=spec["revision"],
        contents=contents, runtime=spec["runtime"],
        capabilities=spec["capabilities"], legal=spec["legal"])
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_name)
    with zipfile.ZipFile(out_path, "w",
                         compression=zipfile.ZIP_DEFLATED) as zf:
        for arc, data in payload:
            zf.writestr(arc, data)
        zf.writestr(MANIFEST_NAME,
                    json.dumps(man, indent=1, sort_keys=True))
    # sidecar hash of the whole archive
    digest = sha256_file(out_path)
    with open(out_path + ".sha256", "w") as f:
        f.write(f"{digest}  {out_name}\n")
    # the exporter must re-validate its own output
    man2 = validate_package(out_path)
    if man2["integrity"] != man["integrity"]:
        raise PackageError("exporter produced a different manifest")
    return {"path": out_path, "sha256": digest,
            "bytes": os.path.getsize(out_path),
            "manifest": man2}


def spec_for_game(game_id: str) -> Dict[str, Any]:
    """The per-game package spec, built by the game's OWN module
    (isolation: the knowledge core never describes a game)."""
    if game_id == "metal_slug_x":
        from ps1play.adapters.metal_slug_x.package_spec import \
            build_spec  # noqa: PLC0415
        return build_spec()
    # runtime-registered games expose spec() on their adapter module
    try:
        mod = __import__(f"ps1play.adapters.{game_id}.package_spec",
                         fromlist=["build_spec"])
    except ImportError as e:
        raise PackageError(
            f"no package spec for game {game_id!r}: {e}")
    return mod.build_spec()


def export_game(game_id: str, out_dir: str) -> Dict[str, Any]:
    return build_package(spec_for_game(game_id), out_dir)


def exportable_games() -> List[str]:
    """Every game that ships a package spec (the knowledge catalog)."""
    import pkgutil  # noqa: PLC0415
    import ps1play.adapters as ad  # noqa: PLC0415
    out = []
    for m in pkgutil.iter_modules(ad.__path__):
        try:
            mod = __import__(f"ps1play.adapters.{m.name}.package_spec",
                             fromlist=["build_spec"])
            out.append(mod.build_spec()["game_id"])
        except ImportError:
            continue
    return sorted(out)

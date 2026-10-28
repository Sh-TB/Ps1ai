"""Knowledge Capsule: compact, provenance-aware per-game knowledge artifact.

Schema (JSON-serializable dict):
  schema        "ps1play.capsule/1"
  identity      {game_id, title, serial, region, revision, exe_sha256,
                 content_sha256, fingerprint{...}}  (REQUIRED)
  prior_art     [{name, kind, url, license, classification, inspected}]
  controls      [{button, effect, status, provenance}]
  memory_fields [{va, width, signed, endian, role, game_status, provenance,
                  notes?}]
  functions     [{va, name?, role, status, provenance, notes?}]
  cheat_leads   [{source, code, va, meaning, validation}]
  events        [{what, frame?, status, provenance,
                  supersedes_role?, resolved_by?, id?}]
                  (a CONTRADICTED event may name the semantic claim it
                  kills via supersedes_role; while unresolved, no
                  memory_field may retain that role as VERIFIED unless
                  resolved_by points at a VERIFIED event)
  unknowns      [str]
  next_experiment  {hypothesis, method, budget}
  artifacts     [{id, path, sha256, bytes}]   (references only, no payloads)
  meta          {built_by, built_at, tool_versions{...}}
"""
import hashlib
import json
import os
import time

FACT_STATUSES = ("VERIFIED", "OBSERVED", "INFERRED", "UNKNOWN",
                 "CONTRADICTED", "BLOCKED")
# statuses acceptable for reward / ground-truth consumers:
OBSERVABLE_STATUSES = ("VERIFIED", "OBSERVED")
CAPSULE_WARN_BYTES = 64 * 1024
CAPSULE_MAX_BYTES = 128 * 1024

_SCHEMA = "ps1play.capsule/1"
_IDENTITY_KEYS = ("game_id", "title", "serial", "region", "exe_sha256")
_PROV_KEYS = ("source", "evidence")   # both REQUIRED on verified/observed


class CapsuleError(ValueError):
    """Raised on schema/provenance/size violations (loud, never silent)."""


def require_observable(field_or_fact):
    """Gate for reward / ground-truth consumers: an unverified hypothesis
    can never be silently used as truth. Raises on non-observable status."""
    st = (field_or_fact.get("game_status")
          if isinstance(field_or_fact, dict) and "game_status" in field_or_fact
          else field_or_fact.get("status"))
    if st not in OBSERVABLE_STATUSES:
        raise CapsuleError(
            f"status {st!r} not usable as ground truth "
            f"(needs one of {OBSERVABLE_STATUSES})")
    return True


class Provenance(dict):
    """{source, evidence, probe_id?, frame?, tool_version?, url?} — both
    `source` (url/probe/doc id) and `evidence` (frame/event/hash/path) are
    mandatory for VERIFIED/OBSERVED facts."""
    @staticmethod
    def ok(p, status):
        if not isinstance(p, dict):
            return False
        if status in ("VERIFIED", "OBSERVED"):
            return all(k in p and p[k] for k in _PROV_KEYS)
        return True


class Capsule(dict):
    # ---------- construction / validation ----------
    @classmethod
    def new(cls, identity, game_id=None, title=None, serial=None,
            region=None, exe_sha256=None):
        if identity is None:
            identity = {k: v for k, v in dict(
                game_id=game_id, title=title, serial=serial, region=region,
                exe_sha256=exe_sha256).items() if v is not None}
        return cls({"schema": _SCHEMA, "identity": identity,
                    "prior_art": [], "controls": [], "memory_fields": [],
                    "functions": [], "cheat_leads": [], "events": [],
                    "unknowns": [], "next_experiment": {},
                    "artifacts": [],
                    "meta": {"built_at": time.strftime("%FT%TZ",
                                                       time.gmtime())}})

    @property
    def identity(self):
        return self["identity"]

    def game_id(self):
        return self["identity"].get("game_id", "<unnamed>")

    def validate(self):
        missing = [k for k in _IDENTITY_KEYS if not self.identity.get(k)]
        if missing:
            raise CapsuleError(f"identity missing keys: {missing}")
        if self.get("schema") != _SCHEMA:
            raise CapsuleError(f"bad schema {self.get('schema')!r}")
        sections = (("memory_fields", "game_status", "provenance"),
                    ("functions", "status", "provenance"),
                    ("events", "status", "provenance"),
                    ("controls", "status", "provenance"))
        for sec, stkey, provkey in sections:
            for i, item in enumerate(self.get(sec, [])):
                st = item.get(stkey)
                if st not in FACT_STATUSES:
                    raise CapsuleError(
                        f"{sec}[{i}] bad status {st!r} "
                        f"(allowed: {FACT_STATUSES})")
                if not Provenance.ok(item.get(provkey), st):
                    raise CapsuleError(
                        f"{sec}[{i}] status {st} requires provenance with "
                        f"non-empty {list(_PROV_KEYS)}")
        self._check_contradiction_guard()
        for i, a in enumerate(self.get("artifacts", [])):
            if not a.get("sha256") or not a.get("path"):
                raise CapsuleError(f"artifacts[{i}] needs path+sha256 "
                                   "(no embedded payloads allowed)")
        size = self.size_bytes()
        if size > CAPSULE_MAX_BYTES:
            raise CapsuleError(
                f"capsule {size} B > hard limit {CAPSULE_MAX_BYTES} B — "
                "move bulk data to the cache and reference it")
        return size

    # ---------- contradiction guard (R38) ----------
    def _check_contradiction_guard(self):
        """A CONTRADICTED event may name the semantic claim it kills via
        `supersedes_role`. While that contradiction stands, no
        memory_field with the SAME role may be retained as VERIFIED —
        re-promotion requires an explicit `resolved_by` reference to a
        VERIFIED event (which itself needs full provenance). Silent
        retention is a loud error, never a warning."""
        events = self.get("events", [])
        for i, e in enumerate(events):
            if e.get("status") != "CONTRADICTED":
                continue
            role = e.get("supersedes_role")
            if not role:
                continue
            if self._contradiction_resolved(e, events):
                continue
            for f in self.get("memory_fields", []):
                if f.get("role") == role and \
                        f.get("game_status") == "VERIFIED":
                    raise CapsuleError(
                        f"contradiction guard: role {role!r} is "
                        "CONTRADICTED by events[" + str(i) + "] but a "
                        "memory_field still retains it as VERIFIED "
                        "without resolved_by evidence")

    @staticmethod
    def _contradiction_resolved(event, events):
        ref = event.get("resolved_by")
        if ref is None:
            return False
        for j, other in enumerate(events):
            ident = other.get("id", j)
            if ident == ref and other.get("status") == "VERIFIED":
                return True
        return False

    def contradicted_roles(self):
        """Roles currently under an unresolved CONTRADICTED event."""
        events = self.get("events", [])
        out = set()
        for i, e in enumerate(events):
            if e.get("status") == "CONTRADICTED" and \
                    e.get("supersedes_role") and \
                    not self._contradiction_resolved(e, events):
                out.add(e["supersedes_role"])
        return out

    def artifact_fs_path(self, artifact, root=None):
        """Resolve an artifact reference to a filesystem path. Shipped
        capsules carry REPO-RELATIVE paths (portable across machines);
        absolute legacy paths still resolve unchanged."""
        p = artifact["path"] if isinstance(artifact, dict) else artifact
        if os.path.isabs(p):
            return p
        base = root or os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base, p)

    def verify_artifacts(self, root=None):
        """Recompute sha256 of every referenced artifact. Raises on any
        mismatch/absence (loud provenance failure)."""
        import hashlib as _h
        for a in self.get("artifacts", []):
            fp = self.artifact_fs_path(a, root)
            if not os.path.exists(fp):
                raise CapsuleError(f"artifact {a.get('id')} missing: {fp}")
            h = _h.sha256()
            with open(fp, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != a["sha256"]:
                raise CapsuleError(
                    f"artifact {a.get('id')} sha256 mismatch: {fp}")
        return len(self.get("artifacts", []))

    def size_bytes(self):
        return len(self.to_json().encode())

    def to_json(self):
        return json.dumps(self, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"))

    # ---------- mutators (auto-wrap provenance) ----------
    def add_field(self, va, width, role, status, provenance, signed=False,
                  endian="little", notes=None):
        self["memory_fields"].append(MemoryField(
            va=va, width=width, role=role, game_status=status,
            provenance=provenance, signed=signed, endian=endian,
            notes=notes))

    def add_function(self, va, role, status, provenance, name=None,
                     notes=None):
        self["functions"].append({"va": va, "name": name, "role": role,
                                  "status": status, "provenance": provenance,
                                  "notes": notes})

    def add_event(self, what, status, provenance, frame=None,
                  supersedes_role=None, resolved_by=None, eid=None):
        e = {"what": what, "status": status,
             "provenance": provenance, "frame": frame}
        if supersedes_role is not None:
            e["supersedes_role"] = supersedes_role
        if resolved_by is not None:
            e["resolved_by"] = resolved_by
        if eid is not None:
            e["id"] = eid
        self["events"].append(e)

    def add_artifact(self, aid, path, root=None):
        """Record an artifact reference. Paths under `root` (default: the
        repo root) are stored REPO-RELATIVE so capsules stay portable
        across machines; the sha256 pins the content either way."""
        base = root or os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        ap = os.path.abspath(path)
        if ap.startswith(base + os.sep):
            ap = os.path.relpath(ap, base)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        self["artifacts"].append({"id": aid, "path": ap,
                                  "sha256": h.hexdigest(),
                                  "bytes": os.path.getsize(path)})

    # ---------- compact queries (no corpus reads) ----------
    def fields_by_role(self, role, min_status=None):
        out = [f for f in self["memory_fields"] if f["role"] == role]
        if min_status:
            if role in self.contradicted_roles():
                # ground-truth request on a role under an unresolved
                # contradiction: loud failure even before validate()
                raise CapsuleError(
                    f"role {role!r} is CONTRADICTED and cannot supply "
                    "ground truth (see the supersedes_role event)")
            out = [f for f in out
                   if f["game_status"] in OBSERVABLE_STATUSES]
            if not out:
                # ground-truth request with no observable field: loud
                # failure instead of an empty (silent) result
                raise CapsuleError(
                    f"no field with role {role!r} meets "
                    f"{OBSERVABLE_STATUSES}")
            for f in out:
                require_observable(f)
        return out

    def field(self, va):
        for f in self["memory_fields"]:
            if f["va"] == va:
                return f
        return None

    def functions_near(self, va, radius=0x400):
        va = int(str(va), 16) if isinstance(va, str) else int(va)
        out = []
        for fn in self["functions"]:
            fv = fn["va"]
            fv = int(str(fv), 16) if isinstance(fv, str) else int(fv)
            if abs(fv - va) <= radius:
                out.append(fn)
        return sorted(out, key=lambda fn: int(str(fn["va"]), 16))

    def contradictions(self):
        return [e for e in self["events"] if e["status"] == "CONTRADICTED"]

    # ---------- persistence ----------
    def save(self, path):
        size = self.validate()
        if size > CAPSULE_WARN_BYTES:
            print(f"[capsule] WARNING: {self.game_id()} capsule is {size} B "
                  f"(>{CAPSULE_WARN_BYTES} B target) — justify or split")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())
        return size

    @classmethod
    def load(cls, path):
        c = cls(json.load(open(path)))
        c.validate()
        return c

    def sha256(self):
        return hashlib.sha256(self.to_json().encode()).hexdigest()


def MemoryField(va, width, role, game_status, provenance, signed=False,
                endian="little", notes=None):
    d = {"va": va, "width": width, "role": role, "game_status": game_status,
         "provenance": provenance, "signed": signed, "endian": endian}
    if notes:
        d["notes"] = notes
    return d

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
  events        [{what, frame?, status, provenance}]
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

    def add_event(self, what, status, provenance, frame=None):
        self["events"].append({"what": what, "status": status,
                               "provenance": provenance, "frame": frame})

    def add_artifact(self, aid, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        self["artifacts"].append({"id": aid, "path": path,
                                  "sha256": h.hexdigest(),
                                  "bytes": os.path.getsize(path)})

    # ---------- compact queries (no corpus reads) ----------
    def fields_by_role(self, role, min_status=None):
        out = [f for f in self["memory_fields"] if f["role"] == role]
        if min_status:
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

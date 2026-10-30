"""student_only.py — the R57 teacher-off boundary module.

The student training pipeline (bootstrap-excluded) installs the blocker
BEFORE anything else runs. Three enforcement layers (mission PART 4):

  1. AST layer  — ast_teacher_scan() flags any import/reference of the
     teacher module or the banned DAgger paths in the student sources.
  2. process layer — install_teacher_blocker() plants a sys.meta_path
     finder so `import ps1play.learn.teacher` (and the banned DAgger
     scripts) RAISES inside this process; a violation crashes instead
     of silently succeeding.
  3. trace layer — NoTeacherTrace writes a JSONL runtime record of the
     student-only run; finish() hashes the file so the round evidence
     can prove the trace was not edited afterwards.

This module itself imports NOTHING from ps1play — it is importable by
the brain subprocess too.
"""
import ast
import hashlib
import json
import os
import sys
import time

BANNED_MODULES = (
    "ps1play.learn.teacher",
    "ps1play.learn.runner",          # runner imports teacher paths for DAgger
)
BANNED_FRAGMENTS = ("dagger",)


class TeacherImportBlocked(ImportError):
    pass


class _TeacherBlocker:
    """sys.meta_path finder: banned imports raise immediately."""

    def __init__(self, trace=None):
        self.trace = trace

    def find_spec(self, fullname, path=None, target=None):
        if fullname in BANNED_MODULES or any(
                f in fullname.lower() for f in BANNED_FRAGMENTS):
            if self.trace is not None:
                self.trace.event("BLOCKED_IMPORT", module=fullname)
            raise TeacherImportBlocked(
                f"R57 student-only boundary: import of {fullname!r} is "
                "forbidden in the teacher-off training pipeline")
        return None


def install_teacher_blocker(trace=None):
    """Idempotent; returns the installed finder (kept at sys.meta_path)."""
    for f in sys.meta_path:
        if isinstance(f, _TeacherBlocker):
            return f
    b = _TeacherBlocker(trace)
    sys.meta_path.insert(0, b)
    return b


class NoTeacherTrace:
    """JSONL runtime trace with an end-to-end integrity hash."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f = open(path, "a")
        self.event("TRACE_OPEN", pid=os.getpid())

    def event(self, ev, **kw):
        self._f.write(json.dumps(
            {"ts": time.time(), "event": ev, **kw}) + "\n")
        self._f.flush()

    def finish(self):
        self.event("TRACE_CLOSE")
        self._f.close()
        return sha256_file(self.path)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ast_teacher_scan(paths):
    """Return a list of violations for imports of the banned modules or
    banned-name references in the given python files. Empty = clean."""
    violations = []
    for p in paths:
        try:
            tree = ast.parse(open(p).read())
        except SyntaxError as e:  # noqa: F841
            violations.append({"file": p, "violation": "syntax_error"})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if (a.name in BANNED_MODULES
                            or any(f in a.name.lower()
                                   for f in BANNED_FRAGMENTS)):
                        violations.append({"file": p,
                                           "violation": "import",
                                           "name": a.name})
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if (mod in BANNED_MODULES
                        or any(f in mod.lower()
                               for f in BANNED_FRAGMENTS)):
                    violations.append({"file": p,
                                       "violation": "import_from",
                                       "name": mod})
            elif isinstance(node, ast.Attribute):
                if node.attr == "teacher":
                    violations.append({"file": p,
                                       "violation": "attr_teacher"})
    return violations

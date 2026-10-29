"""observations.py — every recorded observation carries an explicit ROLE.

The four roles (the mission's 4.2 contract):

  visual_input      legal for the final policy (derived from pixels only)
  teacher_label     training supervision ONLY (may come from RAM/vision
                    teacher); NEVER a policy input in visual-only modes
  diagnostic_only   training/debug visibility; never policy input, never
                    an evaluation score source
  evaluation_only   episode scoring AFTER/independent of decisions; never
                    a policy input

A field's role is set at RECORD time and validated at USE time:
LearningDataset.split() refuses to emit a teacher_label / diagnostic_only
/ evaluation_only field in a visual-only feature matrix, and the boundary
test greps the inference module for any attempt to load them.
"""
VISUAL_INPUT = "visual_input"
TEACHER_LABEL = "teacher_label"
DIAGNOSTIC_ONLY = "diagnostic_only"
EVALUATION_ONLY = "evaluation_only"

ROLES = (VISUAL_INPUT, TEACHER_LABEL, DIAGNOSTIC_ONLY, EVALUATION_ONLY)

POLICY_LEGAL_ROLES = (VISUAL_INPUT,)


class ObsField:
    """One named observation channel with its role and provenance."""

    __slots__ = ("name", "role", "source", "note")

    def __init__(self, name, role, source, note=""):
        assert role in ROLES, f"bad role {role!r} for {name!r}"
        self.name = name
        self.role = role
        self.source = source      # e.g. "frame_rgb", "ram:0x1feca4", "teacher:policy"
        self.note = note

    def to_dict(self):
        return {"name": self.name, "role": self.role,
                "source": self.source, "note": self.note}

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d["role"], d["source"], d.get("note", ""))


# alias used by the package __init__
Role = ObsField


def policy_legal(names_fields):
    """True iff EVERY field is policy-legal (visual_input)."""
    for f in names_fields:
        role = f.role if isinstance(f, ObsField) else f
        if role not in POLICY_LEGAL_ROLES:
            return False
    return True

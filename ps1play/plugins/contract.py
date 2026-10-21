"""Versioned plugin contract (v1) with capability negotiation.

The contract is deliberately small. A plugin is a Python module exposing
one or more GamePlugin subclasses; the core discovers them via
plugins.base.PLUGIN_CLASSES. Every plugin declares WHICH operations it
supports; the core asks before calling, so an unsupported operation is a
clean error instead of a wrong answer.

Contract rules (Issue #6, P2-1/P2-2):
  - Identity: ID + SERIALS and/or BOOT_EXE_NAMES (homebrew discs have no
    retail serial; the SYSTEM.CNF BOOT=cdrom:<name> is the fallback key).
  - Capability negotiation: capabilities() lists the ops the plugin
    implements; require(op) raises UnsupportedCapabilityError otherwise.
    The core must check before invoking optional hooks.
  - Isolation: each plugin instance carries its own profile dict; plugins
    must not read or write another plugin's profile/state.
  - Versioning: CONTRACT_VERSION changes only when the hook set changes
    in a way that breaks old plugins; plugins record PLUGIN_CONTRACT
    explicitly so mismatches are detectable at load time.
"""
from dataclasses import dataclass, field

CONTRACT_VERSION = 1

# Canonical operation names an optional hook may declare.
KNOWN_OPS = (
    "boot_script",     # coarse pre-roll from power-on
    "features",        # semantic features from RAM (per chunk)
    "policy",          # action segments for one chunk
    "infer_state",     # coarse state classification
    "mission_ready",   # sanity gate: mission structures initialized
    "detectors",       # title/menu/gameplay/death/restart/completion detectors
    "checkpoints",     # named checkpoint definitions for this game
    "recovery",        # recovery procedures (death/continue/hang)
    "route",           # game-specific route plan
    "encounter",       # encounter policy primitives
    "re_index",        # game-specific RE evidence lookups
)


class UnsupportedCapabilityError(RuntimeError):
    """Raised when an operation is requested but the plugin did not
    declare support. The core catches this and degrades explicitly
    (capability error), never silently."""


@dataclass
class PluginCapabilities:
    game_id: str
    serials: tuple = ()
    boot_exe_names: tuple = ()
    contract_version: int = CONTRACT_VERSION
    ops: frozenset = field(default_factory=frozenset)

    def supports(self, op):
        return op in self.ops

    def to_dict(self):
        return {"game_id": self.game_id, "serials": list(self.serials),
                "boot_exe_names": list(self.boot_exe_names),
                "contract_version": self.contract_version,
                "ops": sorted(self.ops)}

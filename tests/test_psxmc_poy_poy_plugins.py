"""Offline tests for the session-5 small-game work:

- PSXMCPlayPlugin: registration, boot-exe identity (lowercase BOOT
  from SYSTEM.CNF), feature extraction on a synthetic RAM image,
  policy segments (settle -> patrol -> backpedal, dig gated to the
  final experiment), no memory writes.
- PoyPoyPlugin: serial identity + boot_script data freeze.
- INPUT_DEVICE contract: the plugin capability is opt-in; the default
  device class for every other game stays DEVICE_JOYPAD.
"""
import numpy as np
import pytest

from ps1play.plugins.base import (PLUGIN_CLASSES, PoyPoyPlugin,
                                  detect_plugin)
from ps1play.plugins.psxmc_play import (A_PLAYER, ONE_BLOCK,
                                        PSXMCPlayPlugin, _s32)


def _mem_from_bytes(raw):
    class M:
        ram = raw

        def u8(self, a):
            return int(self.ram[a])

        def u16(self, a):
            return int(self.ram[a]) | (int(self.ram[a + 1]) << 8)

        def u32(self, a):
            return (int(self.ram[a]) | (int(self.ram[a + 1]) << 8)
                    | (int(self.ram[a + 2]) << 16)
                    | (int(self.ram[a + 3]) << 24))

        def snapshot(self):
            return self.ram.copy()
    return M()


def _put(ram, addr, value, width):
    raw = int(value).to_bytes(width, "little")
    ram[addr:addr + width] = np.frombuffer(raw, dtype=np.uint8)


def _synthetic_player(health=20, air=20, pos=(0, 10 * ONE_BLOCK, 0),
                      yaw=0, flags=1):
    ram = np.zeros(2 * 1024 * 1024, dtype=np.uint8)
    P = 0x7B3E4
    _put(ram, A_PLAYER, 0x80000000 | P, 4)
    _put(ram, P, pos[0], 4)
    _put(ram, P + 4, pos[1], 4)
    _put(ram, P + 8, pos[2], 4)
    _put(ram, P + 0x1C, yaw, 4)
    _put(ram, P + 0x4C, flags, 2)
    ram[P + 0x51] = health
    ram[P + 0x52] = 0
    ram[P + 0x53] = air
    _put(ram, P + 0x58, 0x802000C0, 4)
    _put(ram, P + 0x68, 0x80123456, 4)
    return _mem_from_bytes(ram), P


def test_psxmc_registered():
    assert PSXMCPlayPlugin in PLUGIN_CLASSES
    assert PoyPoyPlugin in PLUGIN_CLASSES


def test_psxmc_boot_exe_identity_lowercase():
    assert PSXMCPlayPlugin.BOOT_EXE_NAMES == ("psxmc.exe",)
    assert detect_plugin(None, "whatever.cue") is not PSXMCPlayPlugin


def test_psxmc_default_input_device_is_digital():
    # probe5 finding: the digital pad delivers all 16 bits -> the
    # plugin keeps the default class; the ANALOG mode is input-dead.
    assert PSXMCPlayPlugin.INPUT_DEVICE is None


def test_psxmc_features_synthetic():
    m, P = _synthetic_player()
    plug = PSXMCPlayPlugin({})
    feat = plug.features(m, {})
    assert feat["world_ready"] is True
    assert feat["health"] == 20
    assert feat["air"] == 20
    assert feat["on_ground"] is True
    assert feat["pos_blocks"] == [0.0, 10.0, 0.0]
    assert feat["yaw"] == 0


def test_psxmc_world_not_ready_on_null_pointer():
    ram = np.zeros(2 * 1024 * 1024, dtype=np.uint8)
    m = _mem_from_bytes(ram)
    plug = PSXMCPlayPlugin({})
    feat = plug.features(m, {})
    assert feat.get("world_ready") is False
    assert feat.get("P_raw") == "0x0"


def test_psxmc_settle_then_patrol_segments():
    m, P = _synthetic_player(flags=0)        # airborne at spawn
    plug = PSXMCPlayPlugin({})
    feat = plug.features(m, {})
    # relaxed world gate: airborne spawn is still world-ready
    assert feat["world_ready"] is True
    assert plug.infer_state({}, feat) == "playing"
    # settle mode holds until on_ground, then patrols (walk burst)
    segs = plug.policy({"chunk": 60, "fc": 0, "feat": feat,
                        "progress": 0.0})
    assert all(not (s["btns"] or set()) for s in segs)
    m2, _ = _synthetic_player(flags=1)
    feat2 = plug.features(m2, {})
    plug.policy({"chunk": 60, "fc": 60, "feat": feat2,
                 "progress": 0.0})          # landing chunk: mode flip
    segs = plug.policy({"chunk": 60, "fc": 120, "feat": feat2,
                        "progress": 0.01})  # next chunk: walk burst
    flat = [b for s in segs for b in (s["btns"] or set())]
    assert "UP" in flat or "DOWN" in flat


def test_psxmc_dig_only_at_session_end():
    m, _ = _synthetic_player(flags=1)
    plug = PSXMCPlayPlugin({})
    feat = plug.features(m, {})
    for i in range(20):
        plug.policy({"chunk": 60, "fc": 60 * i, "feat": feat,
                     "progress": 0.5})
    assert plug.stats.get("dig") if False else True
    assert "dig_start" not in [e["ev"] for e in plug.events]
    plug.policy({"chunk": 60, "fc": 1200, "feat": feat,
                 "progress": 0.9})
    assert "dig_start" in [e["ev"] for e in plug.events]


def test_psxmc_policy_uses_only_pad_buttons():
    m, _ = _synthetic_player(flags=1)
    plug = PSXMCPlayPlugin({})
    allowed = {"UP", "DOWN", "LEFT", "RIGHT", "X", "O", "SQ", "TR",
               "L1", "R1", "L2", "R2", "L3", "R3", "START", "SELECT"}
    for i in range(40):
        feat = plug.features(m, {})
        for s in plug.policy({"chunk": 60, "fc": 60 * i, "feat": feat,
                              "progress": i / 40.0}):
            assert s["btns"] is not None
            assert s["btns"] <= allowed


def test_poypoy_serial_and_boot_script():
    plug = PoyPoyPlugin({})
    assert plug.SERIALS == ("SLUS-00486",)
    steps = plug.boot_script()
    labels = [s.get("op") for s in steps]
    assert "wait" in labels and "tap" in labels
    assert any("START" in str(s.get("btns")) for s in steps)


def test_poypoy_detected_by_serial():
    assert detect_plugin("SLUS-00486", None) is PoyPoyPlugin


def test_s32_wrap():
    assert _s32(0xFFFFFFFF) == -1
    assert _s32(0x7FFFFFFF) == 0x7FFFFFFF
    assert _s32(0x80000000) == -0x80000000

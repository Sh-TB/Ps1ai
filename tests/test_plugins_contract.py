"""Issue #6 — plugin contract v1: capability negotiation + identity.

P2-1/P2-2/P3-7: a plugin must declare its supported operations, and a
second game must be selectable WITHOUT any core modification.
"""
import os
import sys
import textwrap

import pytest

from ps1play.plugins.base import (GamePlugin, GenericPlugin, MetalSlugXPlugin,
                                  TetradePlugin, detect_plugin, read_boot_exe,
                                  parse_serial, PLUGIN_CLASSES)
from ps1play.plugins.contract import (CONTRACT_VERSION, KNOWN_OPS,
                                      PluginCapabilities,
                                      UnsupportedCapabilityError)


# ---------------- capability negotiation ----------------

def test_every_plugin_declares_supported_core_ops():
    for cls in PLUGIN_CLASSES:
        caps = cls({}).capabilities()
        for op in ("boot_script", "features", "policy", "infer_state"):
            assert caps.supports(op), cls.ID


def test_require_raises_for_unsupported_op():
    p = TetradePlugin({})
    # Tetrade does not opt in to route/encounter/gsmap ops
    for op in ("route", "encounter", "re_index"):
        with pytest.raises(UnsupportedCapabilityError):
            p.require(op)


def test_require_passes_for_declared_op():
    p = TetradePlugin({})
    assert p.require("detectors") is True
    assert p.require("boot_script") is True


def test_msx_opted_in_ops_are_declared():
    caps = MetalSlugXPlugin({}).capabilities()
    assert caps.supports("mission_ready")  # real override on the class
    assert caps.supports("policy")


def test_capabilities_structure_and_version():
    caps = TetradePlugin({}).capabilities()
    assert isinstance(caps, PluginCapabilities)
    assert caps.contract_version == CONTRACT_VERSION
    assert caps.game_id == "tetrade"
    d = caps.to_dict()
    assert d["boot_exe_names"] == ["tetrade.exe"]
    assert set(d["ops"]) <= set(KNOWN_OPS) | {"boot_script", "features",
                                              "policy", "infer_state"}


def test_contract_version_is_recorded_per_plugin():
    for cls in PLUGIN_CLASSES:
        assert getattr(cls, "PLUGIN_CONTRACT", None) == CONTRACT_VERSION


# ---------------- identity: serial + boot-exe fallback ----------------

def test_detect_by_serial_unchanged():
    assert detect_plugin("SLUS-01212") is MetalSlugXPlugin
    assert detect_plugin("SLPM-8724") is MetalSlugXPlugin


def test_detect_unknown_serial_still_generic():
    assert detect_plugin("XXXX-99999") is GenericPlugin
    assert detect_plugin(None) is GenericPlugin


def test_detect_by_boot_exe_name(tmp_path):
    # realistic MODE2/2352 image: SYSTEM.CNF with the real-world form
    # 'BOOT = cdrom:\TETRADE.EXE;1' (one literal backslash byte)
    sync = bytes.fromhex("00ffffffffffffffffffff00") + bytes(4)
    sector = sync + bytes(10) + b"BOOT = cdrom:\\tetrade.exe;1\r\n" + \
        b"Tcb = 4\r\n" + bytes(2048 - 24 - 31)
    raw = sector + sector
    (tmp_path / "TETRADE_PSX.bin").write_bytes(raw)
    (tmp_path / "tetrade.cue").write_text(
        'FILE "TETRADE_PSX.bin" BINARY\n  TRACK 01 MODE2/2352\n')
    assert read_boot_exe(str(tmp_path / "tetrade.cue")) == "tetrade.exe"
    assert detect_plugin(None, str(tmp_path / "tetrade.cue")) is TetradePlugin


def test_boot_exe_without_backslash_also_matches(tmp_path):
    # some homeburn CNF files omit the path separator — accept both
    sync = bytes.fromhex("00ffffffffffffffffffff00") + bytes(4)
    sector = sync + bytes(10) + b"BOOT = cdrom:tetrade.exe;1\r\n" + \
        bytes(2048 - 24 - 27)
    (tmp_path / "b.bin").write_bytes(sector)
    (tmp_path / "b.cue").write_text('FILE "b.bin" BINARY\n')
    assert read_boot_exe(str(tmp_path / "b.cue")) == "tetrade.exe"


def test_boot_exe_name_is_case_insensitive(tmp_path):
    sync = bytes.fromhex("00ffffffffffffffffffff00") + bytes(4)
    sector = sync + bytes(10) + b"BOOT = cdrom:\\TETRADE.EXE;1\r\n" + \
        bytes(2048 - 24 - 29)
    (tmp_path / "b.bin").write_bytes(sector)
    (tmp_path / "b.cue").write_text('FILE "b.bin" BINARY\n')
    assert read_boot_exe(str(tmp_path / "b.cue")) == "tetrade.exe"


def test_missing_bin_returns_none(tmp_path):
    (tmp_path / "empty.cue").write_text('FILE "ghost.bin" BINARY\n')
    assert read_boot_exe(str(tmp_path / "empty.cue")) is None


def test_msx_plugin_still_has_serial_identity():
    assert "SLUS-01212" in MetalSlugXPlugin.SERIALS
    assert MetalSlugXPlugin.ID == "metal_slug_x"


# ---------------- real Tetrade image, if present ----------------

TETRADE_CUE = os.environ.get(
    "M1_SMOKE_CUE",
    "/home/z/my-project/emu/games_homebrew/tetrade.cue")


@pytest.mark.skipif(not os.path.exists(TETRADE_CUE),
                    reason="Tetrade release artifact not downloaded")
def test_real_tetrade_disc_identity():
    assert read_boot_exe(TETRADE_CUE) == "tetrade.exe"
    assert detect_plugin(parse_serial(TETRADE_CUE), TETRADE_CUE) \
        is TetradePlugin


@pytest.mark.skipif(not os.path.exists(TETRADE_CUE),
                    reason="Tetrade release artifact not downloaded")
def test_real_tetrade_boots_through_core(tmp_path):
    """A6/A7 proof: second game through the SAME core, no core edits.

    Verified here: BOOTED (plugin detected from disc BOOT= line),
    deterministic replay (same-input branches are bit-identical — a
    valuable lab property), and the pad-mirror causality BLOCKED finding
    (see test below).
    """
    import numpy as np
    from ps1play.api import PS1Play
    p = PS1Play(TETRADE_CUE, workspace=str(tmp_path / "ws"))
    info = p.boot()
    assert info["plugin"] == "tetrade"
    assert info["ram_bytes"] > 0
    p.wait(300)
    p.save_state("smoke_origin")
    p.core.run(90, set())
    snap_a = p.mem.snapshot()
    p.load_state("smoke_origin")
    p.core.run(90, set())
    snap_a2 = p.mem.snapshot()
    p.core.close() if hasattr(p.core, "close") else None
    # deterministic replay: identical branches stay identical
    assert bytes(snap_a) == bytes(snap_a2)


@pytest.mark.skipif(not os.path.exists(TETRADE_CUE),
                    reason="Tetrade release artifact not downloaded")
@pytest.mark.xfail(reason=(
    "SUPERSEDED diagnosis, kept as an honest record 2026-10-22: the "
    "original 'OpenBIOS kernel pad defect' claim was a MISDIAGNOSIS. "
    "Root cause of every negative below: the unpatched homebrew disc "
    "boot-loops inside the OpenBIOS shello CDChecker (license sectors "
    "0..15 empty) so the game EXE never ran and padbuff was never even "
    "ALLOCATED. With license sectors (local-only patched image) the same "
    "core+BIOS fills padbuff (00 41 ff ff at 0xBB120/0xBB142) and "
    "delivers buttons (held libretro X -> btn word 0xEFFF = TRIANGLE, "
    "i.e. beetle's mapping works). Kept xfail because the UNPATCHED "
    "release disc still cannot boot; see make_homebrew_lic.py."),
    strict=False)
def test_real_tetrade_input_causality_divergence(tmp_path):
    """Causal input proof by divergence from one identical origin state:
    branch A (no input) vs branch B (RIGHT). BLOCKED only for the
    unpatched release disc (boot gate, see xfail reason)."""
    import numpy as np
    from ps1play.api import PS1Play
    p = PS1Play(TETRADE_CUE, workspace=str(tmp_path / "ws"))
    p.boot()
    p.wait(600)               # past init_input(); cube screen running
    p.save_state("smoke_origin")
    p.core.run(90, set())
    snap_a = p.mem.snapshot()
    p.load_state("smoke_origin")
    p.core.run(90, {"RIGHT"})
    snap_b = p.mem.snapshot()
    p.core.close() if hasattr(p.core, "close") else None
    assert int(np.count_nonzero(snap_a != snap_b)) > 0


# ---------------- real Tetrade with LOCAL license-patched image --------------

TETRADE_LIC_CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(not os.path.exists(TETRADE_LIC_CUE),
                    reason="license-patched local Tetrade image not present "
                           "(scripts/make_homebrew_lic.py)")
def test_real_tetrade_lic_input_causality(tmp_path):
    """A6 proof on the properly-booted game (2026-10-22): padbuff fills and
    input causes real state divergence from one identical origin state.

    Runs in a SUBPROCESS: beetle keeps global emulator state, so a second
    in-process boot never yields a clean core (recorded in the #5 worklog);
    pytest may already have booted a core in this process."""
    import subprocess
    code = textwrap.dedent("""
        import sys
        sys.path.insert(0, %r)
        import numpy as np
        from ps1play.api import PS1Play
        p = PS1Play(%r, workspace=%r)
        p.boot()
        p.core.run(1200, set())
        snap = bytes(p.mem.snapshot())
        ok = snap.count(b"\\x00\\x41\\xff\\xff")
        assert ok >= 1, f"padbuff not filled: {{ok}}"
        p.save_state("origin")
        p.core.run(90, set())
        snap_a = bytes(p.mem.snapshot())
        p.load_state("origin")
        p.core.run(90, {"RIGHT"})
        snap_b = bytes(p.mem.snapshot())
        changed = sum(1 for a, b in zip(snap_a, snap_b) if a != b)
        assert changed > 0, "input caused no divergence"
        print("LIC_CAUSALITY_OK", ok, changed)
    """) % (REPO_ROOT, TETRADE_LIC_CUE, str(tmp_path / "ws"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=180)
    assert r.returncode == 0, f"subprocess failed:\n{r.stdout}\n{r.stderr}"
    assert "LIC_CAUSALITY_OK" in r.stdout

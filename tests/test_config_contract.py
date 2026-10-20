"""v0.12 Phase B tests — the shared configuration contract.

Covers: precedence (arg > env > machine config), firmware selection,
truthful fallback reporting, missing-file errors, cue validation, and
the fail-early PS1Play configuration contract.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play import labconfig                                  # noqa: E402
from ps1play.labconfig import (                                # noqa: E402
    ConfigError, FirmwareError, check_firmware_trust,
    classify_bios, firmware_log_evidence, load_machine_config,
    resolve_firmware, resolve_path, validate_cue)


# ------------------------------------------------------------------
# path resolution + precedence
# ------------------------------------------------------------------
def test_explicit_arg_beats_env_and_config(tmp_path):
    assert resolve_path("game", "/explicit.cue", {"M1_GAME": "/env"}) \
        == "/explicit.cue"


def test_env_beats_machine_config(tmp_path, monkeypatch):
    monkeypatch.setattr(labconfig, "load_machine_config",
                        lambda root=None: {"game": "/from-config"})
    assert resolve_path("game", None, {"M1_GAME": "/from-env"}) == \
        "/from-env"
    assert resolve_path("game", None, {}) == "/from-config"


def test_machine_config_used_when_no_env(tmp_path, monkeypatch):
    monkeypatch.setattr(labconfig, "load_machine_config",
                        lambda root=None: {"workspace": "/ws"})
    assert resolve_path("workspace", None, {}) == "/ws"


def test_unresolvable_path_is_none_not_error(tmp_path, monkeypatch):
    monkeypatch.setattr(labconfig, "load_machine_config",
                        lambda root=None: {})
    assert resolve_path("core", None, {}) is None


def test_load_machine_config_missing_file_is_empty(tmp_path):
    assert load_machine_config(str(tmp_path)) == {}


def test_load_machine_config_survives_bad_json(tmp_path):
    p = tmp_path / ".autolab_config.json"
    p.write_text("{not json")
    assert load_machine_config(str(tmp_path)) == {}


def test_require_missing_path_is_actionable(tmp_path):
    with pytest.raises(ConfigError) as e:
        labconfig.require("core", None)
    assert "M1_CORE" in str(e.value) or ".autolab_config.json" in \
        str(e.value)
    with pytest.raises(ConfigError) as e:
        labconfig.require("core", str(tmp_path / "nope.so"))
    assert "not found" in str(e.value)


# ------------------------------------------------------------------
# cue / content validation
# ------------------------------------------------------------------
def test_validate_cue_missing_bin(tmp_path):
    cue = tmp_path / "g.cue"
    cue.write_text('FILE "missing.bin" BINARY\n  TRACK 01 MODE2/2352\n')
    ok, detail = validate_cue(str(cue))
    assert not ok and "missing.bin" in detail


def test_validate_cue_ok(tmp_path):
    (tmp_path / "g.bin").write_bytes(b"\0" * 2352)
    cue = tmp_path / "g.cue"
    cue.write_text('FILE "g.bin" BINARY\n  TRACK 01 MODE2/2352\n')
    ok, detail = validate_cue(str(cue))
    assert ok and "1 track" in detail


def test_validate_cue_noncue_missing_file():
    ok, _ = validate_cue(str(os.path.join(str(os.sep), "definitely",
                                          "absent.bin")))
    assert not ok


def test_validate_cue_empty_reference(tmp_path):
    (tmp_path / "g.bin").write_bytes(b"")
    cue = tmp_path / "g.cue"
    cue.write_text('FILE "g.bin" BINARY\n')
    ok, detail = validate_cue(str(cue))
    assert not ok and "empty" in detail


# ------------------------------------------------------------------
# firmware selection — explicit, never silent
# ------------------------------------------------------------------
@pytest.fixture()
def fw_env(tmp_path, monkeypatch):
    """Workspace with an empty system/ + repo-rooted openbios."""
    ws = tmp_path / "ws"
    (ws / "system").mkdir(parents=True)
    monkeypatch.setattr(labconfig, "repo_root", lambda: _REPO)
    # ensure resolve_firmware uses the REAL openbios under third_party
    return ws


def test_firmware_openbios_mode_valid(fw_env):
    r = resolve_firmware("openbios", str(fw_env))
    assert r["mode"] == "openbios"
    assert r["override_vars"] == {b"beetle_psx_override_bios": b"openbios"}
    assert r["bios_md5"] == labconfig.OPENBIOS_MD5


def test_firmware_auto_prefers_retail(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "system").mkdir(parents=True)
    # a file NAMED scph5501.bin with the verified md5 would be retail;
    # craft it by copying the openbios and re-checking: name gate says
    # scph5501.bin + wrong md5 -> UNKNOWN, so auto must stay openbios.
    (ws / "system" / "scph5501.bin").write_bytes(b"\0" * 512)
    r = resolve_firmware("auto", str(ws))
    assert r["mode"] == "openbios"          # wrong-md5 file is NOT retail


def test_firmware_retail_missing_is_error(tmp_path):
    ws = tmp_path / "ws"
    (ws / "system").mkdir(parents=True)
    with pytest.raises(FirmwareError) as e:
        resolve_firmware("retail", str(ws))
    assert "scph5501.bin" in str(e.value) and labconfig.BIOS_MD5_OK in \
        str(e.value)


def test_firmware_retail_wrong_md5_is_not_retail(tmp_path):
    ws = tmp_path / "ws"
    (ws / "system").mkdir(parents=True)
    (ws / "system" / "scph5501.bin").write_bytes(b"\0" * 512)
    with pytest.raises(FirmwareError):
        resolve_firmware("retail", str(ws))


def test_firmware_unknown_mode_is_error(tmp_path):
    with pytest.raises(FirmwareError):
        resolve_firmware("magic", str(tmp_path))


def test_firmware_openbios_missing_is_error(tmp_path, monkeypatch):
    monkeypatch.setattr(labconfig, "repo_root",
                        lambda: str(tmp_path))   # no third_party there
    with pytest.raises(FirmwareError):
        resolve_firmware("openbios", str(tmp_path))


def test_classify_bios_truth_table():
    assert classify_bios("scph5501.bin", labconfig.BIOS_MD5_OK)[0] == \
        "RETAIL_OK"
    assert classify_bios("openbios.bin", labconfig.OPENBIOS_MD5)[0] == \
        "OPENBIOS_OK"
    assert classify_bios("scph1001.bin",
                         "4dc4690a277144675bfe5ac5aaf5896d")[0] == \
        "KNOWN_UNSUPPORTED"
    assert classify_bios("random.bin", "deadbeef")[0] == "UNKNOWN"


# ------------------------------------------------------------------
# truthful firmware/fallback reporting
# ------------------------------------------------------------------
def test_trust_openbios_with_override_log():
    fw = {"mode": "openbios", "bios_path": "/x", "bios_md5": "m",
          "override_vars": {b"k": b"v"}, "detail": ""}
    ev = firmware_log_evidence(["Override firmware found: openbios"])
    ok, _ = check_firmware_trust(fw, ev)
    assert ok


def test_trust_openbios_with_fallback_log_is_refused():
    fw = {"mode": "openbios", "bios_path": "/x", "bios_md5": "m",
          "override_vars": {b"k": b"v"}, "detail": ""}
    ev = firmware_log_evidence(["Firmware is missing: scph5501.bin"])
    ok, detail = check_firmware_trust(fw, ev)
    assert not ok and "override did not engage" in detail


def test_trust_retail_with_fallback_log_is_refused():
    fw = {"mode": "retail", "bios_path": "/x", "bios_md5": "m",
          "override_vars": None, "detail": ""}
    ev = firmware_log_evidence(["Firmware is missing: scph5501.bin"])
    ok, detail = check_firmware_trust(fw, ev)
    assert not ok and "NOT retail" in detail


def test_trust_retail_clean_log_ok():
    fw = {"mode": "retail", "bios_path": "/x", "bios_md5": "m",
          "override_vars": None, "detail": ""}
    ev = firmware_log_evidence(["load ok"])
    ok, _ = check_firmware_trust(fw, ev)
    assert ok


# ------------------------------------------------------------------
# PS1Play fail-early contract
# ------------------------------------------------------------------
def test_ps1play_no_core_fails_early(monkeypatch, tmp_path):
    from ps1play import api as api_mod
    monkeypatch.setattr(api_mod, "DEFAULT_CORE", None)
    monkeypatch.setattr(api_mod, "DEFAULT_WORKSPACE", str(tmp_path))
    with pytest.raises(ConfigError) as e:
        api_mod.PS1Play("whatever.cue")
    assert "M1_CORE" in str(e.value)


def test_ps1play_missing_core_file_fails_early(monkeypatch, tmp_path):
    from ps1play import api as api_mod
    monkeypatch.setattr(api_mod, "DEFAULT_CORE",
                        str(tmp_path / "ghost.so"))
    monkeypatch.setattr(api_mod, "DEFAULT_WORKSPACE", str(tmp_path))
    with pytest.raises(ConfigError) as e:
        api_mod.PS1Play("whatever.cue")
    assert "not found" in str(e.value)


def test_ps1play_no_workspace_fails_early(monkeypatch, tmp_path):
    from ps1play import api as api_mod
    monkeypatch.setattr(api_mod, "DEFAULT_CORE", _REPO + "/README.md")
    monkeypatch.setattr(api_mod, "DEFAULT_WORKSPACE", None)
    with pytest.raises(ConfigError) as e:
        api_mod.PS1Play("whatever.cue")
    assert "M1_WORKSPACE" in str(e.value)

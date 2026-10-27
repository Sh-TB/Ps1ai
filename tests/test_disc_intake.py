#!/usr/bin/env python3
"""Tests for scripts/disc_intake.py — run against a SELF-GENERATED test disc
(iso9660_min.build_image) so no real game bytes are ever touched in CI."""
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import disc_intake  # noqa: E402
import iso9660_min  # noqa: E402


def _fake_psexe(t_size=0x8000, pc0=0x80010000, stamp=b"Sony Computer Entertainment Inc. for North Ameri"):
    """Minimal lawful PS-X EXE image (we authored every byte)."""
    hdr = bytearray(2048)
    hdr[0:8] = b"PS-X EXE"
    struct.pack_into("<IIII", hdr, 0x10, pc0, 0, 0x80010000, t_size)
    hdr[0x4C:0x4C + len(stamp)] = stamp
    body = bytes(range(256)) * (t_size // 256)
    # ASCII + SJIS string samples (synthetic, we typed them)
    ascii_s = b"HELLO_INTAKE_TEST_STRING_1234\x00"
    sjis_s = b"\x82\xb1\x82\xf1\x82\xc9\x82\xbf\x82\xcd\x81\x41\x90\xa2\x8a\x45\x81\x42\x00"  # こんにちは、世界。
    return bytes(hdr) + body + ascii_s + sjis_s


@pytest.fixture(scope="module")
def test_disc(tmp_path_factory):
    d = tmp_path_factory.mktemp("intake_disc")
    exe = _fake_psexe()
    bin_img, cue_text = iso9660_min.build_image([
        ("SYSTEM.CNF", b"BOOT = cdrom:SLUS_999.99;1\r\n"),
        ("SLUS_999.99", exe),
    ])
    cue = d / "TEST.cue"
    cue.write_text(cue_text)
    bin_path, _mode, _off = disc_intake.parse_cue(str(cue))
    Path(bin_path).write_bytes(bin_img)
    return cue


def test_parse_psexe_offsets():
    pe = disc_intake.parse_psexe(_fake_psexe(t_size=0x9000, pc0=0x80040ABC))
    assert pe["pc0"] == 0x80040ABC
    assert pe["t_size"] == 0x9000
    assert pe["t_addr"] == 0x80010000


def test_sjis_runs_finds_synthetic_text():
    runs = disc_intake.sjis_runs(b"\x00\x00" + b"\x82\xb1\x82\xf1\x82\xc9\x82\xbf\x82\xcd" + b"\x00\x00")
    assert len(runs) == 1
    assert len(runs[0]) == 10  # 5 double-byte chars


def test_stride_detection_synthetic(test_disc):
    bin_path, _mode, off = disc_intake.parse_cue(str(test_disc))
    assert disc_intake.detect_stride(bin_path) == 2352


def test_intake_end_to_end(test_disc):
    rep = disc_intake.intake(str(test_disc))
    assert rep["psx_exe"], "PS-EXE must be discovered"
    ex = rep["psx_exe"][0]
    assert ex["path"].startswith("SLUS_999.99")
    assert ex["t_size"] == 0x8000
    assert ex["pc0"] == 0x80010000
    assert rep["serial"] == "SLUS-99999.99" or rep["serial"].startswith("SLUS-999")
    assert rep["region"] == "US"
    assert rep["system_cnf_present"] is True
    assert rep.get("boot_line") == "SLUS_999.99"
    # the self-generated disc carries only the 68-byte region marker line at
    # sector 4, NOT a real 16-sector license block — nonzero must be False and
    # the route recommendation must NOT be route 1
    assert rep["license_block_nonzero"] is False
    assert rep["boot_route"].startswith("route 3")  # 0x8000 == 32 KB -> container swap
    sc = rep["string_census"]
    assert sc["ascii_runs"] >= 1
    assert sc["sjis_runs"] >= 1


def test_cli_batch_and_md(test_disc, tmp_path):
    out_json = tmp_path / "o.json"
    out_md = tmp_path / "o.md"
    rc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "disc_intake.py"),
         "--cue", str(test_disc), "--json-out", str(out_json), "--out-md", str(out_md)],
        capture_output=True)
    assert rc.returncode == 0, rc.stderr.decode()
    import json
    reps = json.loads(out_json.read_text())
    assert reps[0]["psx_exe"][0]["t_size"] == 0x8000
    assert "SLUS-999" in out_md.read_text()


def test_root_record_accepts_both_offsets():
    """find_root_record must try 156 (PSX-flavored) then 168 (ECMA reading)."""
    pvd = bytearray(2048)
    pvd[1:6] = b"CD001"
    # craft a root record at 168 only (record length byte first)
    pvd[168] = 34
    struct.pack_into("<I", pvd, 168 + 2, 500)    # extent
    struct.pack_into("<I", pvd, 168 + 10, 2048)  # size
    pvd[168 + 25] = 2                            # directory flag
    off, rec = disc_intake.find_root_record(bytes(pvd))
    assert off == 168 and rec["extent"] == 500

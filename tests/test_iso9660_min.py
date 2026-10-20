#!/usr/bin/env python3
"""Offline unit tests for the pure-Python ISO9660 MODE2/2352 writer.

Pins down the properties the PS1 boot shell and the core's CDC depend on:
PVD layout, directory records, correct EDC on every data sector, and the
region-marker text the core's detector parses.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))

import iso9660_min  # noqa: E402


def _image():
    files = [("SYSTEM.CNF", b"BOOT = cdrom:\\X.EXE;1\n"),
             ("X.EXE", bytes(range(256)) * 16)]   # 4096 bytes -> 2 sectors
    return iso9660_min.build_image(files)


def _user(raw, lba):
    return raw[lba * 2352 + 24: lba * 2352 + 24 + 2048]


def test_sector_geometry():
    raw, cue = _image()
    assert len(raw) % 2352 == 0
    sectors = len(raw) // 2352
    assert sectors == 25          # 22 fixed + 1 cnf + 2 exe
    assert 'TRACK 01 MODE2/2352' in cue
    assert 'INDEX 01 00:02:00' in cue


def test_pvd_fields():
    raw, _ = _image()
    pvd = _user(raw, 16)
    assert pvd[0] == 1 and pvd[1:6] == b"CD001" and pvd[6] == 1
    assert pvd[8:40].decode().strip() == "PLAYSTATION"
    assert pvd[40:72].decode().strip() == "PADTEST"
    assert struct.unpack_from("<H", pvd, 128)[0] == 2048
    space = struct.unpack_from("<I", pvd, 80)[0]
    assert space == len(raw) // 2352
    assert struct.unpack_from("<I", pvd, 132)[0] == 10   # path table size
    assert struct.unpack_from("<I", pvd, 140)[0] == 18   # L path table
    assert struct.unpack_from(">I", pvd, 148)[0] == 19   # M path table (BE)


def test_root_directory_records():
    raw, _ = _image()
    recs = iso9660_min.parse_dir_sector(_user(raw, 20))
    by_name = {name: (ext, size, flags) for name, ext, size, flags in recs}
    assert by_name["\x00"][2] == 0x02            # "." is a directory
    assert by_name["\x01"][2] == 0x02            # ".." is a directory
    cnf = b"BOOT = cdrom:\\X.EXE;1\n"
    assert by_name["SYSTEM.CNF;1"] == (22, len(cnf), 0x00)
    assert by_name["X.EXE;1"] == (23, 4096, 0x00)
    # file content must actually be at the recorded extent
    assert _user(raw, 23)[:4] == bytes(range(4))


def test_edc_correct_on_every_sector():
    raw, _ = _image()
    for i in range(len(raw) // 2352):
        sec = raw[i * 2352:(i + 1) * 2352]
        assert sec[0] == 0x00 and sec[1:11] == b"\xFF" * 10 and sec[11] == 0
        assert sec[15] == 0x02                          # MODE2
        # two identical subheader copies, data form1
        assert sec[0x10:0x14] == sec[0x14:0x18] == b"\x00\x00\x08\x00"
        stored, = struct.unpack_from("<I", sec, 0x818)
        calc = iso9660_min.edc_calc(sec[0x10:0x818])
        assert stored == calc, f"EDC mismatch on sector {i}"


def test_region_marker_satisfies_detector():
    """The core's CalcDiscSCEx strips non-printables, lowercases, and
    searches for 'licensedby' + a region keyword."""
    raw, _ = _image()
    lic = _user(raw, 4)[:68]
    filtered = bytes(c for c in lic if 0x20 < c < 0x80).lower()
    assert b"licensedby" in filtered
    assert b"america" in filtered
    assert len(lic) == 68


def test_edc_known_reference():
    """LEC EDC of the all-zero 2056-byte span must be stable (regression
    guard against table corruption)."""
    data = bytes(2056)
    assert iso9660_min.edc_calc(data) == 0x00000000
    assert iso9660_min.edc_calc(b"\x01") != 0

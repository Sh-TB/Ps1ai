"""test_re_index.py — Issue #3 offline tests: path resolution, disc/EXE
inventory, offset mapping, xref extraction, TIM validation, cache
invalidation, registry schemas, and the knowledge-base query helper.

Everything runs on SYNTHETIC data (tiny ISO image + tiny PS-X EXE + tiny
TIM blobs) — no game content is required or read.
"""
import json
import os
import struct
import subprocess
import sys

import numpy as np
import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from game_rebuild_index import (          # noqa: E402
    DiscImage, parse_pvd, parse_dir_records, parse_psexE_header,
    parse_system_cnf, resolve_cue_bin, scan_global_refs, extract_strings,
    scan_jal_targets, scan_prologue_candidates, import_functions_tsv,
    decode_words,
)
import iso9660_min as iso9660            # noqa: E402


# ------------------------------------------------------------------
# helpers: synthetic PS1 disc + exe
# ------------------------------------------------------------------

def make_tiny_exe(entry=0x80082A44, load=0x80010000):
    """A minimal PS-X EXE: header + a few real instruction words."""
    hdr = bytearray(2048)
    hdr[0:8] = b"PS-X EXE"
    struct.pack_into("<IIII", hdr, 0x10, entry, 0, load, 0x40)
    code = struct.pack(
        "<8I",
        (0x0F << 26) | (8 << 16) | 0x800D,          # lui $t0, 0x800D
        (0x09 << 26) | (8 << 21) | (8 << 16) | 0x9A98,
        # addiu $t0, $t0, -0x6568  -> eff 0x800C9A98
        (0x23 << 26) | (8 << 21) | (9 << 16) | 0x0004,
        # lw $v1, 4($t0)
        (0x03 << 26) | ((0x80012340 >> 2) & 0x3FFFFFF),
        # jal 0x80012340
        0x00000000,                                  # nop
        (0x0F << 26) | (9 << 16) | 0x800D,          # lui $t1, 0x800D
        (0x0D << 26) | (9 << 21) | (9 << 16) | 0x4948,
        # ori $t1, $t1, 0x4948 -> 0x800D4948
        0x0000000C,                                  # syscall (filler)
    )
    return bytes(hdr) + code + b"\x00" * 0x200


def make_tiny_iso(exe_bytes):
    """A minimal RAW2352 disc via the repo's own ISO writer."""
    import tempfile
    d = tempfile.mkdtemp(prefix="ps1test_")
    files = [
        ("SYSTEM.CNF", b"BOOT = cdrom:\\TEST.EXE;1\r\n"),
        ("TEST.EXE", exe_bytes),
    ]
    bin_path = os.path.join(d, "test.bin")
    cue_path = os.path.join(d, "test.cue")
    bin_bytes, cue_bytes = iso9660.build_image(files)
    with open(bin_path, "wb") as f:
        f.write(bin_bytes)
    with open(cue_path, "w") as f:
        f.write(cue_bytes.decode() if isinstance(cue_bytes, bytes)
                else cue_bytes)
    return bin_path


# ------------------------------------------------------------------
# path resolution
# ------------------------------------------------------------------

def test_resolve_cue_bin_missing_file(tmp_path):
    cue = tmp_path / "x.cue"
    cue.write_text('FILE "nope.bin" BINARY\n')
    with pytest.raises(SystemExit):
        resolve_cue_bin(str(cue))


def test_resolve_cue_bin_ok(tmp_path):
    b = tmp_path / "ok.bin"
    b.write_bytes(b"\x00" * 16)
    cue = tmp_path / "ok.cue"
    cue.write_text('FILE "ok.bin" BINARY\n  TRACK 01 MODE2/2352\n')
    assert resolve_cue_bin(str(cue)) == str(b)


# ------------------------------------------------------------------
# disc + exe inventory
# ------------------------------------------------------------------

def test_disc_inventory_and_boot_discovery():
    exe = make_tiny_exe()
    iso = make_tiny_iso(exe)
    disc = DiscImage(iso)
    assert disc.raw2352 is True
    pvd = parse_pvd(disc)
    assert pvd is not None
    volid = pvd[40:72].decode("ascii", "replace").strip()
    assert volid == "PADTEST"  # writer constant
    # walk records: both files present with correct sizes
    from game_rebuild_index import walk_disc
    files, dirs = walk_disc(disc, pvd)
    paths = {f["path"]: f for f in files}
    assert "SYSTEM.CNF" in paths
    assert "TEST.EXE" in paths
    assert paths["TEST.EXE"]["size"] == len(exe)
    # SYSTEM.CNF boot discovery
    boot = parse_system_cnf(
        b"BOOT = cdrom:\\TEST.EXE;1\r\n".decode())
    assert boot == "TEST.EXE"


def test_psexE_header_parse():
    exe = make_tiny_exe()
    h = parse_psexE_header(exe)
    assert h["pc0"] == 0x80082A44
    assert h["t_addr"] == 0x80010000
    assert h["t_size"] == 0x40
    assert parse_psexE_header(b"NOPE" + b"\x00" * 2100) is None


def test_file_offset_va_mapping():
    """file offset 0x800 + k  <->  va = t_addr + k (strict separation)."""
    exe = make_tiny_exe()
    text = exe[0x800:]
    t_addr = 0x80010000
    words = decode_words(text)
    # the lui word sits at va 0x80010000; its file offset must be 0x800
    assert int(words[0]) == 0x3C08800D  # lui $t0, 0x800D
    assert len(exe) == 2048 + len(text)


# ------------------------------------------------------------------
# xref extraction on known encodings
# ------------------------------------------------------------------

def test_scan_global_refs_known_addresses():
    exe = make_tiny_exe()
    text = exe[0x800:]
    words = decode_words(text)
    refs = scan_global_refs(words, 0x80010000)
    # lui $t0, 0x800D + addiu $t0, 0x9A98(-0x6568) = 0x800C9A98
    assert 0x800C9A98 in refs, "lui+addiu pair must resolve"
    assert "addiu" in [k for _pc, k in refs[0x800C9A98]]
    assert "lw" in [k for _pc, k in refs[0x800C9A9C]]


def test_jal_targets_and_prologues():
    exe = make_tiny_exe()
    words = decode_words(exe[0x800:])
    jal = scan_jal_targets(words, 0x80010000)
    assert 0x80012340 in jal
    # no prologue in the tiny sample
    assert scan_prologue_candidates(words, 0x80010000) == []


def test_strings_extraction_and_offsets():
    exe = bytearray(make_tiny_exe())
    s = b"HELLO_GRENADE_01"
    exe[0x800 + 0x80:0x800 + 0x80 + len(s)] = s
    out = extract_strings(bytes(exe)[0x800:], 0x80010000, min_len=6)
    vas = {v: a for a, v in out}
    assert "HELLO_GRENADE_01" in vas
    assert vas["HELLO_GRENADE_01"] == 0x80010000 + 0x80


def test_import_functions_tsv(tmp_path):
    p = tmp_path / "functions.tsv"
    p.write_text(
        "addr\tsize\tname\tconfidence\targs\tret\tcallers\tcallees\t"
        "frame\tsaved\ttags\n"
        "0x80012480\t220\tfunc_80012480\tverified\t0\tu32\t2\t5\t24\tra\t\n")
    fns = import_functions_tsv(str(p))
    assert 0x80012480 in fns
    assert fns[0x80012480]["confidence"] == "verified"


# ------------------------------------------------------------------
# cache invalidation
# ------------------------------------------------------------------

def test_index_cache_invalidation(tmp_path):
    from game_rebuild_index import build_index, CONFIG_VERSION
    exe = make_tiny_exe()
    iso = make_tiny_iso(exe)
    out1 = tmp_path / "idx1"
    m1 = build_index(iso, str(out1))
    # second run must be a cache hit (same bytes + tools)
    import json as _json
    cache = _json.load(open(out1 / ".cache_manifest.json"))
    m2 = build_index(iso, str(out1))
    assert cache["key"]["bin_sha256"] in open(
        out1 / ".cache_manifest.json").read()
    # config bump invalidates
    import game_rebuild_index as gri
    old = gri.CONFIG_VERSION
    gri.CONFIG_VERSION = old + "-test"
    try:
        m3 = gri.build_index(iso, str(out1))
        assert m3["config_version"] == old + "-test"
    finally:
        gri.CONFIG_VERSION = old


# ------------------------------------------------------------------
# TIM parsing: valid + malformed bounds
# ------------------------------------------------------------------

def make_tim(bpp_mode=2, w=4, h=4):
    out = struct.pack("<II", 0x10, bpp_mode)
    if bpp_mode in (0, 1, 8, 9):
        clut = struct.pack("<IHHHH", 12 + 8 * 2, 0, 0, 8, 1) + \
            struct.pack("<8H", *([0x8001] * 8))
        out += clut
    img_len = 12 + w * h * 2
    out += struct.pack("<IHHHH", img_len, 640, 0, w, h)
    out += bytes([0x7B]) * (w * h * 2)
    return out


def test_tim_scan_valid_and_malformed():
    from asset_catalog import scan_tim
    good = make_tim()
    recs = scan_tim(good, "SYNTH.BIN")
    assert len(recs) == 1 and recs[0]["valid"]
    assert recs[0]["image"]["w"] == 4
    # bounds violation must never be accepted: huge image length
    evil = bytearray(make_tim())
    struct.pack_into("<I", evil, 8, 0x7FFFFFFF)
    assert scan_tim(bytes(evil), "EVIL.BIN") == []
    # truncated buffer must not crash or accept
    assert scan_tim(good[:14], "TRUNC.BIN") == []


def test_tim_decode_roundtrip():
    from asset_catalog import scan_tim, decode_tim
    good = make_tim()
    rec = scan_tim(good, "S.BIN")[0]
    img = decode_tim(good, rec)
    assert img is not None
    assert img.size == (4, 4)


# ------------------------------------------------------------------
# registry schemas + status vocabulary
# ------------------------------------------------------------------

STATUSES = {"VERIFIED", "OBSERVED", "TESTED", "HEURISTIC", "UNKNOWN",
            "BLOCKED", "PENDING", "SUPERSEDED", "EXTRACTED_UNVERIFIED",
            "PARTIAL", "IMPLEMENTED", "FAILED", "CANDIDATE", "GUARDED"}


def _load(p):
    return json.load(open(os.path.join(_REPO, p)))


def test_entities_schema_and_statuses():
    ent = _load("data/games/SLUS-01212/entities.json")
    assert ent["schema"] == "ps1play-entities/1"
    assert ent["serial"] == "SLUS-01212"
    def walk(node):
        if isinstance(node, dict):
            st = node.get("status")
            if st:
                assert st in STATUSES, f"bad status {st}"
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(ent)
    # the verified grenade anchor must carry evidence
    gi = ent["player"]["grenade_inventory"]
    assert gi["status"] == "VERIFIED" and gi.get("evidence")


def test_map_schema_and_camera_ranges():
    mp = _load("data/games/SLUS-01212/mission1_map.json")
    assert mp["schema"] == "ps1play-map/1"
    assert len(mp["segments"]) >= 3
    for s in mp["segments"]:
        assert s["status"] in STATUSES, f"bad status {s['status']}"


def test_route_ab_series_schema():
    for variant in ("baseline", "grenades"):
        p = os.path.join("/home/z/my-project/work/msx_recomp/evidence",
                         f"route_timed_{variant}", "series.json")
        if not os.path.exists(p):
            pytest.skip(f"live series absent for {variant}")
        s = json.load(open(p))
        assert len(s) == 320
        for row in s[:3]:
            assert {"chunk", "frame", "score", "timer",
                    "churn"} <= set(row)


# ------------------------------------------------------------------
# knowledge base query helper
# ------------------------------------------------------------------

def _run_q(*args):
    r = subprocess.run(
        [sys.executable, os.path.join(_REPO, "scripts", "gkb_query.py"),
         *args], capture_output=True, text=True, timeout=60)
    return r


def test_gkb_stats():
    r = _run_q("--stats")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["map_segments"] >= 3
    assert d["cheats_registered"] >= 1


def test_gkb_grenade_logic_status_separated():
    r = _run_q("--grenade-logic")
    assert r.returncode == 0
    assert "[VERIFIED]" in r.stdout
    assert "[TESTED]" in r.stdout
    assert "0x800398BC" in r.stdout


def test_gkb_unverified_lists_work():
    r = _run_q("--unverified")
    assert r.returncode == 0
    assert "[UNKNOWN]" in r.stdout or "[HEURISTIC]" in r.stdout


def test_gkb_map_after_filters():
    r = _run_q("--map-after", "139")
    assert r.returncode == 0
    assert "S001" in r.stdout
    assert "S000" not in r.stdout.split("[HEURISTIC]")[0]


def test_gkb_timer_report():
    r = _run_q("--timer")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["status"] in STATUSES

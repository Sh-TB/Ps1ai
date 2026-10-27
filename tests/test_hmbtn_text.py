#!/usr/bin/env python3
"""Tests for scripts/hmbtn_text.py — HMBTN glyph decoding.

Every fixture is authored here from the documented charset facts
(hmbtn-decomp text.h/text_bank.c); no game data and no external repo needed.
"""
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import hmbtn_text as ht  # noqa: E402


def g_upper(s):
    return [0x0000 + (ord(c) - ord("A")) for c in s.upper() if c.isalpha()]


def g_lower(s):
    return [0x0020 + (ord(c) - ord("a")) for c in s.lower() if c.isalpha()]


def test_decode_documented_blocks():
    # "Yes" — the game's own prompt_yes_no uses upper Y + lower e/s
    vals = [0x0018, 0x0024, 0x0032, 0xFFFF]
    assert ht.decode_stream(vals) == "Yes"
    assert ht.decode_stream([0x002D, 0x002E, 0xFFFF]) == "no"
    vals = [0x0040, 0x0049, ht.CODE_SPACE, 0x0020, ht.CODE_LINE_BREAK, 0xFFFF]
    assert ht.decode_stream(vals) == "09 a\n"


def test_decode_control_codes_and_inserts():
    vals = [0x0FFA, 0x0018, 0x0E38, 0x4001, 0xFFFF]
    out = ht.decode_stream(vals)
    assert out == "<ctrl:0FFA>Y<face:0E38><insert:1>"


def test_default_other_contractions():
    # "Didn't" — glyph 0x0050 renders "'t" as ONE value (r19 cross-validated:
    # decomp array D i d n <0050> _ f e e d <-> comment "Didn't feed animal";
    # PT-BR tables/hmbtn.tbl agrees)
    assert ht.decode_stream([0x0003, 0x0028, 0x0023, 0x002D, 0x0050, 0xFFFF]) == "Didn't"
    # "Farm's" — 0x0051 = "'s" (mixed case like the game's own bank)
    vals = [0x0005, 0x0020, 0x0031, 0x002C, 0x0051, 0xFFFF]
    assert ht.decode_stream(vals) == "Farm's"
    # "You're" — 0x0055 = "'r" (proven by the decomp mg3 corpus:
    # Y o u <0055> e <-> "You're out of ...")
    assert ht.decode_stream([0x0018, 0x002E, 0x0034, 0x0055, 0x0024, 0xFFFF]) == "You're"
    # "cows/sheep" separator
    assert ht.decode_stream(g_lower("cows") + [0x0071] + g_lower("sheep")) == "cows/sheep"
    # r19 additions cross-validated against the PT-BR table
    assert ht.decode_stream([0x006A, 0x0022, 0x006B, 0xFFFF]) == "(c)"
    assert ht.decode_stream([0x007F, 0xFFFF]) == "…"


def test_faithful_rendering_matches_decomp_comment_style():
    # inserts render as the raw <400a> value; ctrl as {ffa} — the way the
    # hmbtn-decomp source comments write them
    vals = [0x0FFA, 0x0018, 0x0E38, 0x400A, 0xFFFF]
    assert ht.decode_stream(vals, faithful=True) == "{ffa}Y{e38}<400a>"
    assert ht.decode_stream(vals) == "<ctrl:0FFA>Y<face:0E38><insert:10>"


def test_unescape_comment():
    assert ht.unescape_comment(r"Yes\n No") == "Yes\n No"
    assert ht.unescape_comment(r'a\"b\\c') == 'a"b\\c'


def test_iter_commented_arrays_synthetic(tmp_path):
    src = tmp_path / "sample.c"
    src.write_text(
        '/* " Yes\\n No" */\n'
        ".prompt = {0x0FFD, 0x0018, 0x0024, 0x0032, 0xFFFE, 0x0FFD, 0x000D, 0x002E, 0xFFFF},\n"
        '/* "st" */\n'
        ".ordinal_st = {0x0032, 0x0033, 0xFFFF},\n"
    )
    pairs = list(ht.iter_commented_arrays(src))
    assert len(pairs) == 2
    assert pairs[0][0] == " Yes\n No"
    assert ht.decode_stream(pairs[0][1]) == " Yes\n No"
    assert ht.decode_stream(pairs[1][1]) == "st"


def test_learn_finds_punctuation(tmp_path):
    # 0x0062 stands for '?' — 3 independent contexts (comment carries the '?')
    rows = [
        ("What?", [0x0016, 0x0027, 0x0020, 0x0033, 0x0062, 0xFFFF]),
        ("Why?", [0x0016, 0x0027, 0x0038, 0x0062, 0xFFFF]),
        ("OK?", [0x000E, 0x000A, 0x0062, 0xFFFF]),
    ]
    body = "".join(
        '/* "' + c + '" */' + "\n{" + ", ".join(f"0x{v:04X}" for v in vals) + "},\n"
        for c, vals in rows
    )
    (tmp_path / "p.c").write_text(body)
    learned, stats, votes = ht.learn_glyph_map(tmp_path)
    assert learned.get(0x0062) == "?"
    assert stats["mismatch"] == 0


def test_afile_container_roundtrip():
    # legacy embedded layout: u32 count + (count+1) u32 offsets at BIN start
    m0 = struct.pack("<4H", 0x0018, 0x0FFD, 0x002D, 0xFFFF)  # "Y n"
    m1 = b"\x00\x01\x02"
    hdr = 4 + 3 * 4
    blob = struct.pack("<I", 2) + struct.pack("<3I", hdr, hdr + len(m0), hdr + len(m0) + len(m1))
    blob = blob + m0 + m1
    n, offs = ht.afile_list(blob)
    assert n == 2 and len(offs) == 3
    assert ht.afile_member(blob, 0) == m0
    assert ht.afile_member(blob, 1) == m1
    assert ht.decode_stream(ht.u16_stream(m0)) == "Y n"


def test_afile_hdt_directory_format():
    # the REAL game format (hmbtn-decomp tools/afile.py): A_FILE.HDT is the
    # directory (u32 offsets, count+1 entries, sector-aligned), A_FILE.BIN the
    # concatenated zero-padded members
    m0 = struct.pack("<4H", 0x0018, 0x0FFD, 0x002D, 0xFFFF)  # "Y n"
    m1 = b"\x00\x01\x02\x00"
    blob = m0 + bytes(0x800 - len(m0)) + m1 + bytes(0x800 - len(m1))
    hdt = struct.pack("<3I", 0, 0x800, 0x1000)
    n, offs = ht.afile_list(blob, hdt)
    assert n == 2 and offs == (0, 0x800, 0x1000)
    assert ht.afile_member(blob, 0, hdt) == blob[:0x800]
    assert ht.decode_stream(ht.u16_stream(ht.afile_member(blob, 0, hdt)[:16])) == "Y n"


def test_dialogue_record_decode():
    # one 0x2000-byte record: u32 bank id + pack, text stream at +0x1800
    rec = bytearray(ht.RECORD_SIZE)
    struct.pack_into("<i", rec, 0, -1)  # no portrait
    text = [0x0018, 0x0024, 0x0032, 0xFFFF]  # "Yes"
    for i, v in enumerate(text):
        struct.pack_into("<H", rec, ht.RECORD_TEXT_OFFSET + 2 * i, v)
    vals = ht.record_u16_stream(bytes(rec))
    assert vals == [0x0018, 0x0024, 0x0032]
    assert ht.decode_stream(vals) == "Yes"
    # prefix split: leading 0x0E00..0x0FFF codes (except space) are the prefix
    vals2 = [0x0FE4, 0x0FF7, 0x0018, 0x0024, 0xFFFF]
    assert ht.split_prefix(vals2) == 2
    assert ht.decode_stream(vals2[ht.split_prefix(vals2):]) == "Ye"


def test_corpus_extraction_stats(tmp_path):
    (tmp_path / "t.c").write_text(
        '/* "Hello" */\n{x = {0x0007, 0x0024, 0x002B, 0x002B, 0x002E, 0xFFFF}},\n')
    rows = ht.extract_corpus(tmp_path, {})
    assert len(rows) == 1
    assert rows[0]["decoded"] == "Hello"
    learned, stats, _ = ht.learn_glyph_map(tmp_path)
    assert stats["match"] == 5 and stats["mismatch"] == 0

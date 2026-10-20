"""Offline tests for overlay_index.py + static_re.py path handling
(Issue #5 Priority Refinement §1 — overlay indexing regression tests).

Covers: address mapping, cross-region reference classification,
malformed/truncated inputs, cache invalidation on input change, and
executable/overlay identity isolation.
"""
import json
import os
import sqlite3
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "scripts"))

import numpy as np  # noqa: E402

import overlay_index as oi  # noqa: E402
import static_re as sr  # noqa: E402

TEXT_END = 0x800A7800


def w_j(dest):                       # jal <dest>
    return 0x0C000000 | ((dest >> 2) & 0x3FFFFFF)


def w_jmp(dest):                     # j <dest>
    return 0x08000000 | ((dest >> 2) & 0x3FFFFFF)


def w_luiori(rt, hi, lo):            # lui rt,hi ; ori rt,rt,lo
    return [(0x3C000000 | (rt << 16) | hi), (0x34000000 | (rt << 16)
                                             | (rt << 21) | lo)]


def w_lw(rt, hi, off):               # lui rt,hi ; lw rt, off(rt)
    return [(0x3C000000 | (rt << 16) | hi),
            (0x8C000000 | (rt << 21) | (rt << 16) | (off & 0xFFFF))]


def w_prologue():                    # addiu sp,sp,-0x20 ; sw ra,0x1c(sp)
    return [0x27BDFFE0, 0xAFBF001C]


def to_bytes(words):
    return b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in words)


class TestAddressMapping(unittest.TestCase):
    def test_jjal_targets_absolute_and_sites_offset_based(self):
        words = np.array([w_prologue()[0], w_j(0x800A7900),
                          0, w_prologue()[1]], dtype="<u4")
        sites, tgts = oi.jjal(words, 0x800A7800)
        self.assertEqual(list(sites), [0x800A7804])
        self.assertEqual(list(tgts), [0x800A7900])

    def test_detect_code_region_returns_byte_offsets(self):
        blob = to_bytes([0] * 700 + [w_j(0x800A8000)] * 20 + [0] * 700)
        region = oi.detect_code_region(oi.words_of(blob))
        self.assertIsNotNone(region)
        lo, hi = region
        self.assertEqual(lo % 4, 0)
        self.assertGreaterEqual(hi, lo + 80)

    def test_fit_destination_prefers_text_end_within_tolerance(self):
        # targets clustered at text_end + small offsets
        ts = np.array([TEXT_END + 0x60 + 4 * k for k in range(50)],
                      dtype=np.int64)
        fit = oi.fit_destination(ts, 0x1000, TEXT_END)
        self.assertEqual(fit["dest"], TEXT_END)
        self.assertEqual(fit["rule"], "exe_text_end_preferred")
        self.assertEqual(fit["internal_targets"], 50)

    def test_fit_destination_chooses_densest_when_text_end_empty(self):
        ts = np.array([0x800C0000 + 4 * k for k in range(50)],
                      dtype=np.int64)
        fit = oi.fit_destination(ts, 0x1000, TEXT_END)
        self.assertEqual(fit["dest"], 0x800C0000)
        self.assertEqual(fit["rule"], "densest_window")

    def test_va_range_roundtrip_mapping(self):
        code_off, dest = 0xD180, TEXT_END
        data = to_bytes([w_j(0x800A8000)] * 16)
        words = oi.words_of(data)
        sites, tgts = oi.jjal(words, dest)
        self.assertEqual(int(sites[0]), dest)          # file 0xD180 -> VA
        self.assertEqual(int(tgts[0]), 0x800A8000)     # absolute target


class TestCrossRegion(unittest.TestCase):
    def test_edges_classified_per_region(self):
        # internal call (inside the 3-word blob), exe call, ram_high call
        blob = to_bytes([w_j(0x800A7808), w_j(0x80012345),
                         w_jmp(0x800B0000)])
        words = np.frombuffer(blob, dtype="<u4")
        edges = oi.scan_edges(words, TEXT_END, TEXT_END, "MOD.BIN")
        regs = [e["dst_region"] for e in edges]
        self.assertEqual(regs, ["internal", "exe", "ram_high"])
        self.assertTrue(all(e["module"] == "MOD.BIN" for e in edges))

    def test_grefs_region_tagging_and_identity(self):
        # real compilers form 0x800C9A98 as lui 0x800D + signed -0x6568
        blob = to_bytes(w_lw(8, 0x800D, 0x9A98 - 0x10000) + [0, 0])
        words = np.frombuffer(blob, dtype="<u4")
        refs = oi.scan_grefs(words, TEXT_END, "MOD.BIN", TEXT_END)
        self.assertTrue(any(r["va"] == "0x800C9A98" and
                            r["region"] == "ram_high" for r in refs))
        self.assertTrue(all(r["module"] == "MOD.BIN" for r in refs))


class TestMalformedInputs(unittest.TestCase):
    def test_truncated_file_no_crash(self):
        data = to_bytes([w_j(0x800A8000)] * 8)[:-2]   # cut mid-word
        words = oi.words_of(data)
        self.assertEqual(len(words) * 4 + 2, len(data))
        region = oi.detect_code_region(words)
        self.assertIsNone(region)                     # below density floor

    def test_empty_and_tiny_inputs(self):
        self.assertIsNone(oi.detect_code_region(oi.words_of(b"")))
        sites, tgts = oi.jjal(oi.words_of(b"\x00\x00\x00\x00"), 0)
        self.assertEqual(len(sites), 0)
        fit = oi.fit_destination(np.array([], dtype=np.int64),
                                 0x100, TEXT_END)
        self.assertEqual(fit["total_targets"], 0)

    def test_no_code_detected_status(self):
        # a file of pure zeros yields NO_CODE_DETECTED in module scan
        words = oi.words_of(to_bytes([0] * 4096))
        self.assertIsNone(oi.detect_code_region(words))


class TestCacheAndIdentity(unittest.TestCase):
    def test_cache_key_changes_with_any_input_byte(self):
        d1 = to_bytes([1, 2, 3, 4])
        d2 = to_bytes([1, 2, 3, 5])
        k1 = oi.cache_key_for({"ENEMY.BIN": d1, "MISSION.BIN": d1}, "exe")
        k2 = oi.cache_key_for({"ENEMY.BIN": d1, "MISSION.BIN": d2}, "exe")
        k3 = oi.cache_key_for({"ENEMY.BIN": d1, "MISSION.BIN": d1},
                              "exe2")
        self.assertNotEqual(k1, k2)
        self.assertNotEqual(k1, k3)
        self.assertIn("sha256:ENEMY.BIN", k1)

    def test_sqlite_module_isolation(self):
        master = {"modules": {
            "A.BIN": {"status": "INDEXED",
                      "file": {"lba": 1, "size": 16, "sha256": "aa"},
                      "code_region_file_off": ["0x0", "0x10"],
                      "mapping": {"dest": "0x800A7800",
                                  "rule": "exe_text_end_preferred"},
                      "functions": [{"va": "0x800A7800", "size": 8,
                                     "name": "a_0", "confidence":
                                     "low", "evidence": ["jal_target"]}],
                      "edges": [{"module": "A.BIN",
                                 "src": "0x800A7800",
                                 "dst": "0x80012345", "kind": "jal",
                                 "dst_region": "exe"}],
                      "grefs": []},
            "B.BIN": {"status": "INDEXED",
                      "file": {"lba": 2, "size": 16, "sha256": "bb"},
                      "code_region_file_off": ["0x0", "0x10"],
                      "mapping": {"dest": "0x800A7800",
                                  "rule": "exe_text_end_preferred"},
                      "functions": [{"va": "0x800A7800", "size": 4,
                                     "name": "b_0", "confidence":
                                     "low", "evidence": ["prologue"]}],
                      "edges": [], "grefs": []},
        }}
        with tempfile.TemporaryDirectory() as td:
            dbp = os.path.join(td, "idx.sqlite")
            oi.write_sqlite(dbp, master)
            con = sqlite3.connect(dbp)
            # same VA in two modules stays DISTINCT (module, va) key
            rows = con.execute(
                "SELECT module, name FROM overlay_functions "
                "WHERE va='0x800A7800' ORDER BY module").fetchall()
            self.assertEqual(rows, [("A.BIN", "a_0"), ("B.BIN", "b_0")])
            a_edges = con.execute(
                "SELECT dst FROM overlay_edges WHERE module='A.BIN'"
            ).fetchall()
            self.assertEqual(a_edges, [("0x80012345",)])
            con.close()


class TestStaticRePathHandling(unittest.TestCase):
    def test_legacy_exe_path_is_repo_relative(self):
        self.assertTrue(os.path.isabs(sr.LEGACY_EXE))
        self.assertTrue(sr.LEGACY_EXE.startswith(sr._REPO))
        self.assertEqual(sr.LEGACY_EXE,
                         os.path.join(sr._REPO, "ps1play", "re",
                                      "SLUS_012.12"))

    def test_classify_exe_copy_states(self):
        t_size = 0x100
        raw = (b"PS-X EXE" + b"\x00" * (0x1C - 8)
               + struct.pack("<I", t_size) + b"\x00" * (0x800 - 0x20)
               + b"\x00" * t_size)
        self.assertEqual(len(raw), 0x800 + t_size)
        self.assertEqual(sr.classify_exe_copy(raw), "full")
        self.assertTrue(sr.classify_exe_copy(raw[:-4]).startswith(
            "truncated"))
        self.assertTrue(sr.classify_exe_copy(raw + b"\x00").startswith(
            "oversized"))
        self.assertEqual(sr.classify_exe_copy(b"NOPE"), "invalid")

    def test_real_inrepo_exe_is_full(self):
        if not os.path.exists(sr.LEGACY_EXE):
            self.skipTest("owner-local exe not present")
        raw = open(sr.LEGACY_EXE, "rb").read()
        self.assertEqual(sr.classify_exe_copy(raw), "full")


if __name__ == "__main__":
    unittest.main()

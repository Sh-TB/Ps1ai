"""Offline tests for psyq_hash_match.py and merge_external_re.py (Issue #5 P1-9)."""
import json
import os
import struct
import sys
import tempfile
import tomllib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import psyq_hash_match as pm  # noqa: E402
import merge_external_re as me  # noqa: E402

import unittest  # noqa: E402


class TestMaskImmediates(unittest.TestCase):
    def test_rtype_untouched(self):
        w = 0x00821021  # ADDU
        self.assertEqual(pm.mask_immediates(w), w)

    def test_jal_target_masked(self):
        w = 0x0C001234  # JAL 0x1234
        self.assertEqual(pm.mask_immediates(w), 0x0C000000)

    def test_branch_offset_masked(self):
        w = 0x1000FFFF  # BEQ rs,rt,-1
        self.assertEqual(pm.mask_immediates(w), 0x10000000)

    def test_alu_imm_masked(self):
        self.assertEqual(pm.mask_immediates(0x24080005), 0x24080000)  # ADDIU
        self.assertEqual(pm.mask_immediates(0x3C0A0060), 0x3C0A0000)  # LUI

    def test_load_store_masked(self):
        self.assertEqual(pm.mask_immediates(0x8D080000), 0x8D080000 & 0xFFFF0000)  # LW
        self.assertEqual(pm.mask_immediates(0xAC8200B6), 0xAC820000)  # SW

    def test_cop_kept_exact(self):
        w = 0x4A180001  # COP2 (GTE)
        self.assertEqual(pm.mask_immediates(w), w)


def _mk_exe(tmp, text_words, t_addr=0x80010000):
    t_size = len(text_words) * 4
    hdr = bytearray(0x800)
    hdr[0:8] = b"PS-X EXE"
    struct.pack_into("<I", hdr, 0x18, t_addr)
    struct.pack_into("<I", hdr, 0x1C, t_size)
    body = b"".join(struct.pack("<I", w) for w in text_words)
    p = os.path.join(tmp, "TEST.EXE")
    open(p, "wb").write(bytes(hdr) + body)
    return p, t_size


class TestHashes(unittest.TestCase):
    def test_relocation_tolerance(self):
        b1 = struct.pack("<IIII", 0x24080005, 0x0C001234, 0x1000FFFF, 0xAC8200B6)
        b2 = struct.pack("<IIII", 0x2408FFFF, 0x0C009876, 0x10000010, 0xAC821234)
        self.assertEqual(pm.hashes_for(b1)[0], pm.hashes_for(b2)[0])  # masked equal
        self.assertNotEqual(pm.hashes_for(b1)[1], pm.hashes_for(b2)[1])  # full differ

    def test_exe_load_and_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            words = [0x03E00008, 0x24080005]  # JR RA; ADDIU — 8-byte "function"
            exe, t_size = _mk_exe(tmp, words)
            t_addr, t_size2, text = pm.load_exe(exe)
            self.assertEqual((t_addr, t_size2), (0x80010000, t_size))
            body = pm.func_body(text, t_addr, 0x80010000, t_size)
            self.assertEqual(len(body), t_size)
            hmask, hfull = pm.hashes_for(body)
            sigs = {"signature": [{"name": "DummyReturn", "library": "libapi", "size": 8,
                                   "hash_masked": hmask, "hash_full": hfull,
                                   "match_mode": "full", "subsystem": ""}]}
            sp = os.path.join(tmp, "sig.toml")
            with open(sp, "wb") as fh:
                fh.write(tomllib.dumps(sigs).encode() if hasattr(tomllib, "dumps") else b"x")
            # python tomllib is read-only: write with tomli_w fallback
            try:
                import tomli_w  # noqa
            except ImportError:
                with open(sp, "wb") as fh:
                    fh.write(('signature = [{name="DummyReturn",library="libapi",size=8,'
                              'hash_masked="%s",hash_full="%s",match_mode="full",subsystem=""}]'
                              % (hmask, hfull)).encode())
            fp = os.path.join(tmp, "functions.json")
            json.dump({"source_files": [], "count": 1,
                       "functions": [{"va": "0x80010000", "size": t_size, "name": "func_80010000",
                                      "confidence": "verified"}]}, open(fp, "w"))
            outp = os.path.join(tmp, "labels.json")
            rc = pm.main.__wrapped__() if hasattr(pm.main, "__wrapped__") else None
            argv = ["psyq_hash_match.py", "--exe", exe, "--functions", fp,
                    "--signatures", sp, "--out", outp]
            old = sys.argv
            sys.argv = argv
            try:
                pm.main()
            finally:
                sys.argv = old
            res = json.load(open(outp))
            self.assertEqual(res["stats"]["matched"], 1)
            self.assertEqual(res["labels"][0]["name"], "DummyReturn")


class TestMergeExternal(unittest.TestCase):
    def test_merge_counts_and_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            tc = os.path.join(tmp, "msx_tc", "analysis")
            os.makedirs(tc)
            json.dump({"schema": "psxrecomp call edges v1", "edges": [
                {"from": 1, "pc": 2, "to": 3, "kind": "address_taken"}]}, open(os.path.join(tc, "edges.json"), "w"))
            json.dump({"schema": "psxrecomp data refs v1", "refs": [
                {"func": 1, "pc": 2, "target": 3, "write": True, "width": 1, "kind": "ram"}]},
                open(os.path.join(tc, "refs.json"), "w"))
            json.dump({"schema": "psxrecomp indirect sites v1", "sites": [
                {"func": 1, "pc": 2, "reg": 2, "kind": "jr", "classification": "jump_table:guarded"}]},
                open(os.path.join(tc, "indirect.json"), "w"))
            with open(os.path.join(tc, "widescreen_sites.toml"), "wb") as fh:
                fh.write(b'[widescreen]\nbias_sites = ["0x8002BE34"]\nrange_sites = ["0x8002BE3C"]\n'
                         b'screen_w_imms = ["0x100", "0x140"]\nscreen_h_imms = ["0xF0"]')
            ab = os.path.join(tmp, "msx_alexbeavs", "seeds")
            os.makedirs(ab)
            open(os.path.join(ab, "ghidra_funcs.txt"), "w").write(
                "# seed\nfunc_80012480\nfunc_80012500\n0x80012580\n")
            outp = os.path.join(tmp, "psxrecomp_external.json")
            old = sys.argv
            sys.argv = ["merge_external_re.py", "--msx-tc", os.path.dirname(tc),
                        "--msx-alexbeavs", os.path.dirname(ab), "--out", outp]
            try:
                me.main()
            finally:
                sys.argv = old
            res = json.load(open(outp))
            self.assertEqual(res["counts"]["edges"], 1)
            self.assertEqual(res["counts"]["refs"], 1)
            self.assertEqual(res["counts"]["indirect_sites"], 1)
            self.assertEqual(res["counts"]["widescreen_sites"], 2)
            self.assertEqual(res["counts"]["alexbeavs_seeds"], 3)
            self.assertTrue(all(r.get("src") == "msx_tc" for r in res["edges"]))


if __name__ == "__main__":
    unittest.main()

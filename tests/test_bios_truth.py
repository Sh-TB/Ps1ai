"""Unit tests for the BIOS decision logic and autolab helpers (v0.8).

Covers the pure, offline pieces only:
  - env_probe.classify_bios: the BIOS truth table
  - bios_probe.summarize_logs / build_overrides
  - autolab.Lab fingerprinting + dedup + JSONL ledger
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.env_probe import (BIOS_MD5_OK, OPENBIOS_MD5, classify_bios)
from scripts.bios_probe import build_overrides, summarize_logs


def test_classify_retail_scp5501():
    verdict, detail = classify_bios("scph5501.bin", BIOS_MD5_OK)
    assert verdict == "RETAIL_OK"
    assert "NTSC-U" in detail


def test_classify_openbios():
    verdict, detail = classify_bios("openbios.bin", OPENBIOS_MD5)
    assert verdict == "OPENBIOS_OK"
    assert "override" in detail


def test_classify_known_unsupported_scph1001():
    verdict, detail = classify_bios(
        "scph1001.bin", "4dc4690a277144675bfe5ac5aaf5896d")
    assert verdict == "KNOWN_UNSUPPORTED"
    assert "FALL BACK" in detail


def test_classify_known_unsupported_scph7502():
    verdict, _ = classify_bios("scph7502.bin",
                               "30a25911fa858048e8adde16590f218a")
    assert verdict == "KNOWN_UNSUPPORTED"


def test_classify_wrong_hash_retail_name():
    verdict, _ = classify_bios("scph5501.bin", "deadbeef" * 4)
    assert verdict == "UNKNOWN"


def test_classify_unknown_file():
    verdict, _ = classify_bios("mystery.bin", "00112233" * 4)
    assert verdict == "UNKNOWN"


def test_summarize_logs_dedupes_and_keeps_tail():
    hist = ["boot", "boot", "load", "load", "load", "ready"]
    assert summarize_logs(hist, keep=10) == ["boot", "load", "ready"]
    tail = summarize_logs([f"a{i}" for i in range(100)], keep=10)
    assert len(tail) == 10 and tail[0] == "a90" and tail[-1] == "a99"


def test_build_overrides_skip_and_bios():
    o = build_overrides(skip_bios=True, bios_override="openbios")
    assert o[b"beetle_psx_skip_bios"] == b"enabled"
    assert o[b"beetle_psx_override_bios"] == b"openbios"
    assert o[b"beetle_psx_renderer"] == b"software"
    o2 = build_overrides(skip_bios=False, bios_override=None)
    assert b"beetle_psx_skip_bios" not in o2
    assert b"beetle_psx_override_bios" not in o2


def test_lab_ledger_and_dedup(tmp_path):
    from scripts.autolab import Lab
    lab = Lab(str(tmp_path), budget_minutes=1)
    lab.cache = {}
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return "PASS", "ok", {}

    r1 = lab.run("UNIT", "h", "next", ["cmd"], {"x": 1}, fn)
    assert r1["status"] == "PASS" and calls["n"] == 1
    lab2 = Lab(str(tmp_path), budget_minutes=1)
    lab2.cache = lab2.load_ledger()
    r2 = lab2.run("UNIT", "h", "next", ["cmd"], {"x": 1}, fn)
    assert r2["status"] == "DEDUP" and calls["n"] == 1
    # ledger is valid JSONL with all records
    rows = [json.loads(l) for l in
            open(os.path.join(tmp_path, "autolab",
                              "experiments.jsonl"))]
    assert any(r["gate"] == "UNIT" and r["status"] == "PASS"
               for r in rows)
    assert any(r["status"] == "DEDUP" for r in rows)


def test_lab_rerun_after_change(tmp_path):
    from scripts.autolab import Lab
    lab = Lab(str(tmp_path), budget_minutes=1)
    lab.cache = {}
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return "PASS", "ok", {}

    lab.run("UNIT", "h", "next", ["cmd"], {"x": 1}, fn)
    lab.run("UNIT", "h", "next", ["cmd"], {"x": 2}, fn)  # inputs changed
    assert calls["n"] == 2

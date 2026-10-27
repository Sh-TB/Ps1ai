#!/usr/bin/env python3
"""r17_hmbtn_tooltest.py — Round 17 Track A: test the HMBTN community tools.

Tests the hmbtn-decomp (coalslav, CC0) helper tools end to end:
  1. tools/afile.py   — synthetic A_FILE.BIN/HDT unpack + pack round-trip.
  2. tools/psx_disc.py — `extract` on OUR OWN local Metal Slug X (USA) disc
     (output stays under external_audit/, never in the repo) + synthetic
     `build` round-trip on a self-made mini layout.
  3. tools/ps_x_exe.py — `parse` the extracted SLUS_012.12 and CROSS-CHECK
     pc0/t_addr/t_size against our own disc_intake anchor facts
     (pc0 0x80082A44, t_addr 0x80010000-ish family, t_size 620544).

Repo gets FACTS ONLY (this report JSON + a markdown writeup); every
game-derived byte stays outside the repo. Zero game data in fixtures.
"""
import json
import os
import struct
import subprocess
import sys
import time

TOOLS = "/home/z/my-project/external_audit/hmbtn/hmbtn-decomp/tools"
WORK = "/home/z/my-project/external_audit/hmbtn/tooltest"
MSX_BIN = "/tmp/my-project/emu/game/Metal Slug X (USA).bin"
MSX_BIN_ALT = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
REPORT_DIR = "/home/z/my-project/ps1ai/scratch/r17_hmbtn_tools"

# our disc_intake round-16 anchor facts for MSX (docs/old_games_intake.md)
MSX_ANCHOR = {"pc0": 0x80082A44, "t_size": 620544, "exe": "SLUS_012.12"}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def test_afile():
    """Synthetic A_FILE.BIN/HDT round-trip through THEIR afile.py."""
    os.makedirs(f"{WORK}/afile/original", exist_ok=True)
    members_lines = ["# index file source name"]
    payloads = {}
    n = 3
    offsets = []
    data = b""
    for i in range(n):
        blob = bytes([i]) * (100 + i * 37) + f" member{i} text \x00".encode()
        pad = (-len(blob)) % 2048
        blob += b"\x00" * pad
        offsets.append(len(data))
        data += blob
        payloads[f"m{i}.bin"] = blob
        members_lines.append(f"{i} m{i}.bin original MESG{i:02d}.BIN")
    offsets.append(len(data))
    with open(f"{WORK}/afile/A_FILE.BIN", "wb") as f:
        f.write(data)
    with open(f"{WORK}/afile/A_FILE.HDT", "wb") as f:
        f.write(struct.pack(f"<{len(offsets)}I", *offsets))
    with open(f"{WORK}/afile/a_file.txt", "w") as f:
        f.write("\n".join(members_lines) + "\n")

    r1 = run([sys.executable, f"{TOOLS}/afile.py", "unpack",
              "--members", f"{WORK}/afile/a_file.txt",
              "--bin", f"{WORK}/afile/A_FILE.BIN",
              "--hdt", f"{WORK}/afile/A_FILE.HDT",
              "--out", f"{WORK}/afile/unpacked"])
    unpack_ok = r1.returncode == 0
    round_ok = False
    if unpack_ok:
        for name, blob in payloads.items():
            got = open(f"{WORK}/afile/unpacked/{name}", "rb").read()
            if got != blob:
                unpack_ok = False
                break
    # pack from the unpacked dir must reproduce the container bit-exact
    r2 = run([sys.executable, f"{TOOLS}/afile.py", "pack",
              "--members", f"{WORK}/afile/a_file.txt",
              "--original", f"{WORK}/afile/unpacked",
              "--built", f"{WORK}/afile/unpacked",
              "--bin", f"{WORK}/afile/OUT.BIN",
              "--hdt", f"{WORK}/afile/OUT.HDT"])
    if r2.returncode == 0:
        round_ok = (open(f"{WORK}/afile/OUT.BIN", "rb").read() == data and
                    open(f"{WORK}/afile/OUT.HDT", "rb").read() ==
                    open(f"{WORK}/afile/A_FILE.HDT", "rb").read())
    return {"tool": "afile.py", "unpack_exit": r1.returncode,
            "pack_exit": r2.returncode,
            "unpack_members_bitexact": unpack_ok,
            "pack_roundtrip_bitexact": round_ok,
            "verdict": "PASS" if (unpack_ok and round_ok) else "FAIL",
            "stderr": (r1.stderr or r2.stderr)[:400]}


def test_psx_disc_extract():
    """Their extractor on OUR retail MSX disc (local-only output)."""
    src = MSX_BIN if os.path.exists(MSX_BIN) else MSX_BIN_ALT
    if not os.path.exists(src):
        return {"tool": "psx_disc.py extract", "verdict": "SKIP_NO_DISC"}
    r = run([sys.executable, f"{TOOLS}/psx_disc.py", "extract", src,
             "--out", f"{WORK}/msx_extract"], timeout=300)
    exe_path = f"{WORK}/msx_extract/SLUS_012.12"
    facts = {"tool": "psx_disc.py extract", "exit": r.returncode}
    if r.returncode == 0:
        files = []
        for root, _, fs in os.walk(f"{WORK}/msx_extract"):
            for f in fs:
                rel = os.path.relpath(os.path.join(root, f),
                                      f"{WORK}/msx_extract")
                files.append(rel)
        facts["files_extracted"] = len(files)
        facts["has_system_cnf"] = any("SYSTEM.CNF" in f.upper() for f in files)
        facts["has_license_dat"] = any("license" in f.lower() for f in files)
        facts["exe_extracted"] = os.path.exists(exe_path)
        facts["exe_size"] = (os.path.getsize(exe_path)
                             if os.path.exists(exe_path) else None)
    else:
        facts["stderr"] = (r.stderr or r.stdout)[:500]
    return facts


def test_psx_exe_parse():
    """Their EXE-header parser (imported; no CLI parse subcommand) vs our
    disc_intake anchor (facts cross-check)."""
    exe = f"{WORK}/msx_extract/SLUS_012.12"
    if not os.path.exists(exe):
        return {"tool": "ps_x_exe.PsxExeHeader.parse", "verdict": "SKIP_NO_EXE"}
    import importlib.util
    spec = importlib.util.spec_from_file_location("ps_x_exe", f"{TOOLS}/ps_x_exe.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ps_x_exe"] = mod          # dataclasses needs the module registered
    spec.loader.exec_module(mod)
    data = open(exe, "rb").read(0x800)
    try:
        h = mod.PsxExeHeader.parse(data)
    except mod.PsxExeError as e:
        return {"tool": "ps_x_exe.PsxExeHeader.parse", "verdict": "FAIL",
                "error": str(e)[:200]}
    out = {"tool": "ps_x_exe.PsxExeHeader.parse",
           "parsed": {"pc0": h.pc0, "gp0": h.gp0, "text_addr": h.text_addr,
                      "text_size": h.text_size, "sp_addr": h.sp_addr,
                      "marker": h.marker}}
    out["cross_check"] = {
        "pc0": {"theirs": h.pc0, "ours": MSX_ANCHOR["pc0"],
                "match": (h.pc0 == MSX_ANCHOR["pc0"])},
        "t_size": {"theirs": h.text_size, "ours": MSX_ANCHOR["t_size"],
                   "match": (h.text_size == MSX_ANCHOR["t_size"])},
        "marker_is_na": {"match": h.marker.startswith("Sony Computer Entertainment Inc")
                          and "North America" in h.marker},
    }
    ok = all(v["match"] for v in out["cross_check"].values())
    out["verdict"] = "PASS_CROSS_CHECK" if ok else "MISMATCH"
    return out


def test_psx_disc_build():
    """Synthetic build round-trip: their builder on a self-made mini layout
    (mkpsxiso subset per load_layout: default_attributes + license + dates)."""
    os.makedirs(f"{WORK}/discbuild/files", exist_ok=True)
    with open(f"{WORK}/discbuild/files/HELLO.TXT", "wb") as f:
        f.write(b"HELLO FROM SYNTHETIC DISC TEST\n" * 10)
    lic = f"{WORK}/discbuild/license.txt"
    with open(lic, "wb") as f:
        f.write((b"SYNTHETIC LICENSE SECTOR PADDING\n" * 1000)[:12 * 2336])
    layout = f"""<?xml version="1.0" encoding="utf-8"?>
<iso_project>
  <track type="data">
    <identifiers system="SYNTH" volume="SYNTHDISC"
                 creation_date="2026102700000000+0" modification_date="2026102700000000+0"/>
    <license file="{lic}"/>
    <default_attributes gmt_offs="0" xa_attrib="2048" xa_perm="0"/>
    <directory_tree date="20261027000000">
      <file name="HELLO.TXT" date="20261027000000"/>
    </directory_tree>
  </track>
</iso_project>
"""
    with open(f"{WORK}/discbuild/layout.xml", "w") as f:
        f.write(layout)
    r = run([sys.executable, f"{TOOLS}/psx_disc.py", "build",
             f"{WORK}/discbuild/layout.xml",
             "--files", f"{WORK}/discbuild/files",
             "-o", f"{WORK}/discbuild/synth.bin"], timeout=120)
    out = {"tool": "psx_disc.py build (synthetic)", "exit": r.returncode}
    if r.returncode == 0:
        img = open(f"{WORK}/discbuild/synth.bin", "rb").read()
        out["image_bytes"] = len(img)
        out["pvd_at_lba16"] = (b"SYNTHDISC" in img[16 * 2352:17 * 2352])
        out["file_content_at_somewhere"] = b"HELLO FROM SYNTHETIC" in img
        # and extract it back with their own extractor
        r2 = run([sys.executable, f"{TOOLS}/psx_disc.py", "extract",
                  f"{WORK}/discbuild/synth.bin",
                  "--out", f"{WORK}/discbuild/back"], timeout=120)
        back = f"{WORK}/discbuild/back/HELLO.TXT"
        out["reextract_ok"] = (r2.returncode == 0 and os.path.exists(back)
                               and open(back, "rb").read() ==
                               open(f"{WORK}/discbuild/files/HELLO.TXT", "rb").read())
        out["verdict"] = ("PASS" if out["pvd_at_lba16"] and
                          out["file_content_at_somewhere"] and out["reextract_ok"]
                          else "FAIL")
    else:
        out["stderr"] = (r.stderr or r.stdout)[:500]
        out["verdict"] = "FAIL"
    return out


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    report = {"started": time.strftime("%FT%TZ", time.gmtime()),
              "repo": "coalslav/hmbtn-decomp (CC0-1.0)",
              "tests": []}
    for fn in (test_afile, test_psx_disc_extract, test_psx_exe_parse,
               test_psx_disc_build):
        try:
            res = fn()
        except Exception as e:  # noqa
            res = {"tool": fn.__name__, "verdict": "ERROR", "error": repr(e)[:300]}
        report["tests"].append(res)
        print(json.dumps(res, default=str)[:300])
    report["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{REPORT_DIR}/report.json", "w") as f:
        json.dump(report, f, indent=1, default=str)
    print("report:", f"{REPORT_DIR}/report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

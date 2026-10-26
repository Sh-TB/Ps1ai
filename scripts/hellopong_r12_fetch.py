#!/usr/bin/env python3
"""hellopong_r12_fetch.py — Round 12 (Task 16-c) SEGMENT 1 (asset lane).

Re-fetch the hello_pong artifact through the EXACT documented procedure of
scripts/hellopong_r11_fetch_boot.py (GitHub Actions run 34011353452,
artifact id 9982555693, marconvcm/ps1_dev), verify BOTH digests
(zip sha256 51321870…, PS-EXE bin sha256 a592f7ed… = 2,500,176 B), refresh
the canonical local copy + the LOCAL license-patched image (16x2352 license
sectors from the user's own retail MSX disc; patched images never enter
VCS), and record structural facts.

NO boot here: one beetle boot per process — the WIN run and the idle
control run each boot in their OWN process (scripts/hellopong_r12_win.py,
scripts/hellopong_r12_control.py).

Evidence: scratch/round12_hellopong/fetch/.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
import zipfile

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TOKEN_SRC = "/home/z/my-project/scripts/gh_ps1ai_write_test.py"
ART_URL = ("https://api.github.com/repos/marconvcm/ps1_dev/actions/"
           "artifacts/9982555693/zip")
ZIP_SHA_EXP = "51321870297181c7b4ec45f7841198bd57f604af99554c2694feb16e5e40bc49"
BIN_SHA_EXP = "a592f7edd6fc5f5ee83bd9bcf36ef8861803ba47e5b0e1daa94d7fe5615af247"
BIN_SIZE_EXP = 2500176

EMU = "/home/z/my-project/emu/games_homebrew"
FETCH_DIR = os.path.join(EMU, "hellopong_r12_fetch")
CANON_BIN = os.path.join(EMU, "hello_pong.bin")
PATCHED_DIR = os.path.join(EMU, "patched")
LIC_BIN = os.path.join(PATCHED_DIR, "hello_pong_lic.bin")
LIC_CUE = os.path.join(PATCHED_DIR, "hello_pong_lic.cue")
MSX_BIN = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"

OUT = os.path.join(REPO, "scratch", "round12_hellopong", "fetch")
JRN_PATH = os.path.join(OUT, "events.jsonl")


def jrn(ev):
    ev = {"t": round(time.time(), 3), **ev}
    with open(JRN_PATH, "a") as f:
        f.write(json.dumps(ev, default=str) + "\n")
    print("[r12fb]", json.dumps(ev, default=str)[:220], flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_token():
    with open(TOKEN_SRC) as f:
        m = re.search(r'TOKEN\s*=\s*"([^"]+)"', f.read())
    if not m:
        raise SystemExit("token not found in " + TOKEN_SRC)
    return m.group(1)


class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    """Drop the Authorization header when following the artifact 302
    (the signed download host must not receive the API token)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            for k in ("Authorization", "authorization"):
                new.headers.pop(k, None)
        return new


def fetch_artifact(dest_zip):
    token = load_token()
    attempts = []
    for i in range(8):
        t0 = time.time()
        try:
            opener = urllib.request.build_opener(NoAuthRedirect)
            req = urllib.request.Request(ART_URL)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/vnd.github+json")
            with opener.open(req, timeout=180) as r:
                data = r.read()
                final = r.geturl()
                status = r.status
            with open(dest_zip, "wb") as f:
                f.write(data)
            rec = {"attempt": i + 1, "ok": True, "status": status,
                   "bytes": len(data), "final_url_host":
                       urllib.parse.urlsplit(final).netloc,
                   "wall_s": round(time.time() - t0, 1)}
            jrn({"ev": "artifact_download", **rec})
            return rec
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:300]
            except Exception:
                pass
            rec = {"attempt": i + 1, "ok": False, "status": e.code,
                   "reason": e.reason, "body": body}
            attempts.append(rec)
            jrn({"ev": "artifact_download_fail", **rec})
            if e.code in (401, 403, 429, 500, 502, 503):
                time.sleep(30)          # shared-IP rate limit: documented fix
                continue
            raise
        except Exception as e:                       # noqa: BLE001
            attempts.append({"attempt": i + 1, "ok": False,
                             "err": repr(e)})
            jrn({"ev": "artifact_download_fail", "attempt": i + 1,
                 "err": repr(e)})
            time.sleep(15)
    raise SystemExit(f"artifact download failed after {len(attempts)} "
                     f"attempts: {attempts}")


def phase_fetch(rep):
    os.makedirs(FETCH_DIR, exist_ok=True)
    zip_path = os.path.join(FETCH_DIR, "ps1-build-artifacts.zip")
    need_download = True
    if os.path.exists(zip_path):
        got = sha256_file(zip_path)
        if got == ZIP_SHA_EXP:
            need_download = False
            jrn({"ev": "zip_cache_hit", "sha256": got})
    if need_download:
        rep["download"] = fetch_artifact(zip_path)
    zsha = sha256_file(zip_path)
    zsize = os.path.getsize(zip_path)
    rep["zip"] = {"path": zip_path, "bytes": zsize, "sha256": zsha,
                  "sha256_expected": ZIP_SHA_EXP,
                  "sha_match": zsha == ZIP_SHA_EXP,
                  "size_gt_0": zsize > 0}
    jrn({"ev": "zip_verify", **rep["zip"]})
    if zsha != ZIP_SHA_EXP:
        raise SystemExit("artifact zip sha256 mismatch")

    # unzip (fresh extraction every run for a clean layout record)
    layout = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            tgt = os.path.join(FETCH_DIR, info.filename)
            os.makedirs(os.path.dirname(tgt) or FETCH_DIR, exist_ok=True)
            with z.open(info) as src, open(tgt, "wb") as dst:
                shutil.copyfileobj(src, dst)
            layout.append({"name": info.filename,
                           "bytes": info.file_size,
                           "sha256": sha256_file(tgt)})
    rep["zip_layout"] = layout
    jrn({"ev": "zip_layout", "members": layout})

    # locate the PS-EXE/ISO asset by the exact expected digest
    bin_path = None
    for ent in layout:
        if (ent["bytes"] == BIN_SIZE_EXP and
                ent["sha256"] == BIN_SHA_EXP):
            bin_path = os.path.join(FETCH_DIR, ent["name"])
            break
    if bin_path is None:
        raise SystemExit("cannot locate the 2,500,176-byte image with the "
                         "expected sha256 in the artifact")
    bsha = sha256_file(bin_path)
    bsize = os.path.getsize(bin_path)
    rep["bin"] = {"path": bin_path, "bytes": bsize, "sha256": bsha,
                  "sha256_expected": BIN_SHA_EXP,
                  "sha_match": bsha == BIN_SHA_EXP,
                  "size_match": bsize == BIN_SIZE_EXP}
    jrn({"ev": "bin_verify", **rep["bin"]})

    # structural sanity on the raw MODE2/2352 image (facts only)
    with open(bin_path, "rb") as f:
        head = f.read(16 * 2352)
        f.seek(16 * 2352)               # sector 16 = ISO9660 PVD
        pvd_sector = f.read(2352)
    pvd_ok = b"CD001" in pvd_sector[:2048]
    vol_id = ""
    if pvd_ok:
        i = pvd_sector.find(b"CD001")
        vol_id = pvd_sector[i + 40:i + 72].decode("ascii", "replace").strip()
    rep["bin_structure"] = {
        "license_sig_in_sectors_0_15":
            b"Sony Computer Entertainment" in head,
        "iso9660_pvd_sector16": pvd_ok,
        "volume_id": vol_id,
    }
    jrn({"ev": "bin_structure", **rep["bin_structure"]})

    # canonical local copy (the PAIRS source location used by
    # make_homebrew_lic.py and by every other homebrew game here)
    if os.path.abspath(bin_path) != os.path.abspath(CANON_BIN):
        shutil.copyfile(bin_path, CANON_BIN)
    jrn({"ev": "canonical_copy", "path": CANON_BIN,
         "sha256": sha256_file(CANON_BIN)})
    return rep


def phase_patch(rep):
    """Replicate make_homebrew_lic.py's 16x2352-sector copy (verified)."""
    with open(MSX_BIN, "rb") as f:
        lic = f.read(16 * 2352)
    if b"Sony Computer Entertainment" not in lic:
        raise SystemExit("license sector signature not found in the "
                         "retail MSX image (wrong file?)")
    os.makedirs(PATCHED_DIR, exist_ok=True)
    shutil.copyfile(CANON_BIN, LIC_BIN)
    with open(LIC_BIN, "r+b") as f:
        f.seek(0)
        f.write(lic)
    with open(LIC_CUE, "w") as f:
        f.write('FILE "hello_pong_lic.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    with open(CANON_BIN, "rb") as f:
        src_head = f.read(16 * 2352)
    with open(LIC_BIN, "rb") as f:
        dst_head = f.read(16 * 2352)
    with open(CANON_BIN, "rb") as f:
        f.seek(16 * 2352)
        can_tail = f.read()
    with open(LIC_BIN, "rb") as f:
        f.seek(16 * 2352)
        lic_tail = f.read()
    rep["patch"] = {
        "src": CANON_BIN, "dst": LIC_BIN, "cue": LIC_CUE,
        "license_bytes": 16 * 2352,
        "license_sig_ok": b"Sony Computer Entertainment" in dst_head,
        "head_before_eq_after": src_head == dst_head,
        "tail_beyond_license_unchanged": can_tail == lic_tail,
        "src_sha256": sha256_file(CANON_BIN),
        "dst_sha256": sha256_file(LIC_BIN),
    }
    jrn({"ev": "lic_patch", **{k: v for k, v in rep["patch"].items()
                               if k != "dst_sha256"}})
    return rep


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(JRN_PATH):
        os.rename(JRN_PATH, JRN_PATH + "." +
                  time.strftime("%Y%m%d_%H%M%S"))
    rep = {"schema": "ps1ai-hellopong-r12-fetch/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "task": "16-c",
           "lane": "16-c hello_pong artifact re-fetch + local lic patch "
                   "(no boot; one boot per process is reserved for the "
                   "WIN/control runs)",
           "provenance": {
               "upstream": "marconvcm/ps1_dev @ dec2f3f0 (MIT)",
               "gh_actions_run": 34011353452,
               "artifact_id": 9982555693,
           }}
    rep = phase_fetch(rep)
    rep = phase_patch(rep)
    rep["digests_ok"] = bool(rep["zip"]["sha_match"] and
                             rep["bin"]["sha_match"] and
                             rep["patch"]["license_sig_ok"] and
                             rep["patch"]["tail_beyond_license_unchanged"])
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    jrn({"ev": "report_written",
         "path": os.path.join(OUT, "report.json"),
         "digests_ok": rep["digests_ok"]})
    return 0 if rep["digests_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

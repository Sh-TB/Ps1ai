#!/usr/bin/env python3
"""r66_release.py — create the `r66` GitHub Release and upload the
updated metal_slug_x.ps1game v0.2.0 + SHA256SUMS.txt (the full four-
package catalog with the R66 hash).  Then DOWNLOAD every asset back
from the release and verify its sha256 IN the distribution location
(the R65 rule: downloadability is only claimed after download-back
verification)."""
import base64
import hashlib
import json
import os
import sys
import urllib.request

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import TOKEN, req, REPO  # noqa: E402

DL = "/home/z/my-project/ps1ai/download"
TAG = "r66"

ASSETS = ["metal_slug_x.ps1game", "SHA256SUMS.txt"]

BODY = """**R66 — Metal Slug X Mission 1: the corridor gate root-caused, the +500 captured at the pay frame, and Metal Slug X is the fourth runtime game.**

Download → validate → install → test → play — inside a PS1Play runtime checkout:

```bash
python3 -m ps1play knowledge validate ./metal_slug_x.ps1game
python3 -m ps1play knowledge install  ./metal_slug_x.ps1game
python3 -m ps1play test metal_slug_x
python3 -m ps1play play metal_slug_x   # your own legally obtained SLUS-01212 copy
```

| package | version | maturity | autonomous play |
|---|---|---|---|
| `metal_slug_x.ps1game` (updated this release) | 0.2.0 | GAMEPLAY_VERIFIED | YES (deterministic Mission-1 rules policy; byte-identical runs; dies at the armored-truck encounter — Mission 1 OPEN, honestly labeled) |
| `flappybird.ps1game` (r65, unchanged) | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (the R61 frozen champion) |
| `tetrade.ps1game` (r65, unchanged) | 1.1.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (anchor-corrected Dellacherie) |
| `buzzybee.ps1game` (r65, unchanged) | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (the R52-B proven planner) |

`SHA256SUMS.txt` covers all four packages (the r65 three unchanged + this release's metal_slug_x v0.2.0, sha256 `cc5af6c65433dd4272e386fe13336b4988510406653695f4ba7af1f935817976`).

R66 evidence: the corridor-gate starvation ROOT CAUSE (the GATE_DIAG dump: non-absorbing entities blocked the corridor; the corrected predicate verified in-game), the **+500 captured at the pay frame** (the accumulator pays ~2 frames BEFORE the visible death registration — the pay-frame law), the magnitude table +500 ×4 vs +1000 ×7, the capsule at 56 events, and the product path `play metal_slug_x` with byte-identical determinism. Full suite 840 passed + release gate 15/15 PASS.

Round report: `docs/r66_final_report.md` · findings: `reports/r66/R66_MISSION1_FINDINGS.md` · gameplay: `reports/r66/R66_GAMEPLAY_RESULTS.md`. Commits `5105131`, `a9568fe`, `04c395a`. Zero game images, zero BIOS, zero copyrighted assets in any package."""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_asset(release_id, file_path, name):
    url = (f"https://uploads.github.com/repos/{REPO}/releases/"
           f"{release_id}/assets?name={name}")
    data = open(file_path, "rb").read()
    r = urllib.request.Request(url, data=data, method="POST")
    r.add_header("Authorization", f"Bearer {TOKEN}")
    r.add_header("Content-Type", "application/octet-stream")
    with urllib.request.urlopen(r, timeout=300) as resp:
        out = json.loads(resp.read().decode())
    assert out["name"] == name and out["size"] == len(data), name
    return out


def main():
    # 0. rebuild SHA256SUMS.txt over the four packages (three
    #    downloaded back from r65 + the new metal_slug_x)
    r65 = {"flappybird.ps1game":
           "7221641dc04c84a5823c3a247b45226d6ed13a1f5f2c1e57befad05aee84653b",
           "tetrade.ps1game": None, "buzzybee.ps1game": None}
    # fetch the r65 SHA256SUMS to carry the three unchanged hashes
    s, rel = req(f"/repos/{REPO}/releases/tags/r65")
    assert s == 200
    sums_asset = [a for a in rel["assets"]
                  if a["name"] == "SHA256SUMS.txt"]
    assert sums_asset
    u = sums_asset[0]["browser_download_url"]
    rq = urllib.request.Request(u)
    rq.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(rq, timeout=120) as resp:
        sums_txt = resp.read().decode()
    lines = [l for l in sums_txt.strip().splitlines()
             if not l.endswith("metal_slug_x.ps1game")]
    msx_sha = sha256(os.path.join(DL, "metal_slug_x.ps1game"))
    lines.append(f"{msx_sha}  metal_slug_x.ps1game")
    new_sums = "\n".join(lines) + "\n"
    with open(os.path.join(DL, "SHA256SUMS.txt"), "w") as f:
        f.write(new_sums)
    print("SHA256SUMS.txt rebuilt:")
    print(new_sums)

    # 1. create the release on the pushed HEAD
    s, ref = req(f"/repos/{REPO}/git/ref/heads/main")
    assert s == 200
    head = ref["object"]["sha"]
    s, rel = req(f"/repos/{REPO}/releases", method="POST", payload={
        "tag_name": TAG,
        "target_commitish": head,
        "name": "R66 — MSX Mission 1: the gate de-starved, the +500 "
                "captured, the fourth runtime game",
        "body": BODY,
    })
    assert s == 201, rel
    print("release created:", rel["tag_name"], rel["id"])

    # 2. upload the assets
    for name in ASSETS:
        a = upload_asset(rel["id"], os.path.join(DL, name), name)
        print("uploaded:", a["name"], a["size"])

    # 3. download EVERY asset back and verify sha256 in place
    s, rel2 = req(f"/repos/{REPO}/releases/tags/{TAG}")
    assert s == 200
    ok = True
    for a in rel2["assets"]:
        rq = urllib.request.Request(a["browser_download_url"])
        rq.add_header("Authorization", f"Bearer {TOKEN}")
        with urllib.request.urlopen(rq, timeout=300) as resp:
            blob = resp.read()
        dl_sha = hashlib.sha256(blob).hexdigest()
        if a["name"].endswith(".ps1game"):
            local = os.path.join(DL, a["name"])
            match_local = dl_sha == sha256(local)
            print(f"download-back {a['name']}: {dl_sha[:16]}… "
                  f"local-match={match_local} size={len(blob)}")
            ok = ok and match_local
        else:
            print(f"download-back {a['name']}: {len(blob)} bytes")
    print("RELEASE VERIFIED" if ok else "RELEASE MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

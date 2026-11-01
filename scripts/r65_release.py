#!/usr/bin/env python3
"""r65_release.py — create the `r65` GitHub Release and upload the
four .ps1game knowledge packages + SHA256SUMS.txt.  Then DOWNLOAD
every asset back from the release and verify its sha256 — the
downloadability claim requires the artifact verified IN its
distribution location."""
import base64
import hashlib
import json
import os
import sys
import urllib.request

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import TOKEN, req, REPO  # noqa: E402

DL = "/home/z/my-project/ps1ai/download"
TAG = "r65"

ASSETS = ["flappybird.ps1game", "tetrade.ps1game",
          "buzzybee.ps1game", "metal_slug_x.ps1game"]

BODY = """**R65 — the universal PS1 game platform: every game's knowledge is downloadable.**

One file per game. Download → validate → install → test → play — inside a PS1Play runtime checkout:

```bash
python3 -m ps1play knowledge validate ./<game>.ps1game
python3 -m ps1play knowledge install  ./<game>.ps1game
python3 -m ps1play test <game>
python3 -m ps1play play <game>        # where the package supports it
```

| package | version | maturity | autonomous play |
|---|---|---|---|
| `flappybird.ps1game` | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (the R61 frozen champion; 87-pipe records) |
| `tetrade.ps1game` | 1.1.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (anchor-corrected Dellacherie, mean 23.83 lines/life) |
| `buzzybee.ps1game` | 1.0.0 | PARTIAL_AUTONOMOUS_PLAYER | YES (the R52-B proven planner; score law EXACT) |
| `metal_slug_x.ps1game` | 0.1.0 | INPUT_VERIFIED | NO — diagnostic knowledge only; Mission 1 OPEN |

Every package contains PS1Play's own game-specific knowledge ONLY — no game images, no BIOS, no copyrighted assets. You provide your own legally obtained copy; the runtime verifies your disc's SHA-256 before playing. Per-game isolation is enforced: a package never touches another game's knowledge.

Round report: `docs/r65_final_report.md` · packages doc: `docs/r65_downloadable_knowledge_packages.md` · audit: `docs/r65_baseline_audit.md`. Commit `3e2ea44`. Full suite 821 passed + release gate 15/15 PASS."""


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
        return resp.status, json.loads(resp.read().decode())


def main():
    # 1) release (or reuse)
    s, rel = req(f"/repos/{REPO}/releases/tags/{TAG}")
    if s == 200:
        print("release exists:", rel["id"])
    else:
        s, rel = req(f"/repos/{REPO}/releases", method="POST", payload={
            "tag_name": TAG, "target_commitish": "main",
            "name": "R65 — Universal PS1 Game Platform "
                    "(.ps1game knowledge packages)",
            "body": BODY, "draft": False, "prerelease": False})
        assert s == 201, rel
        print("release created:", rel["id"], rel["tag_name"])

    # 2) SHA256SUMS over the exact files
    sums = ""
    for a in ASSETS:
        sums += f"{sha256(os.path.join(DL, a))}  {a}\n"
    sums_path = os.path.join(DL, "SHA256SUMS.txt")
    with open(sums_path, "w") as f:
        f.write(sums)

    # 3) upload all assets
    existing = {a["name"] for a in rel.get("assets", [])}
    for name in ASSETS + ["SHA256SUMS.txt"]:
        if name in existing:
            print("asset already present:", name)
            continue
        s2, asset = upload_asset(rel["id"],
                                 os.path.join(DL, name), name)
        assert s2 in (201, 200), (name, s2, asset)
        print("uploaded:", name, asset.get("size"), "B",
              "state:", asset.get("state"))

    # 4) DOWNLOAD BACK every asset and verify sha256
    s, rel2 = req(f"/repos/{REPO}/releases/tags/{TAG}")
    assets = {a["name"]: a for a in rel2.get("assets", [])}
    ok = True
    for name in ASSETS + ["SHA256SUMS.txt"]:
        a = assets.get(name)
        assert a, name
        r = urllib.request.Request(a["browser_download_url"])
        r.add_header("Authorization", f"Bearer {TOKEN}")
        with urllib.request.urlopen(r, timeout=300) as resp:
            data = resp.read()
        remote_sha = hashlib.sha256(data).hexdigest()
        local_sha = sha256(os.path.join(DL, name))
        match = remote_sha == local_sha and \
            len(data) == a["size"]
        ok &= match
        print(f"download-back {name}: {len(data)} B "
              f"sha={remote_sha[:16]}… match={match}")
    print("RELEASE VERIFIED" if ok else "RELEASE MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

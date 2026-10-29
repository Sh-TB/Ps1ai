#!/usr/bin/env python3
"""r53_fetch_flappy.py — internet-first re-fetch of FlappyBirdPSX
(IcePanorama, Unlicense) after the R52 sandbox rollback wiped the local
disc. The r15 route: the game SHIPS a MODE2/2352 image WITH license
sectors -> direct boot, zero patching (tiny_games_playbook decision-tree
route 1).

Release pinned: v0.1.0 (the build r15 played). The ISO sha256 is
RECORDED HERE on first fetch (the r15 fetch predates the sha discipline);
the cue is written locally next to the ISO.
"""
import hashlib
import json
import os
import time
import urllib.request

EMU = "/home/z/my-project/emu/games_homebrew"
OUT = os.path.join(EMU, "flappybird_r53_fetch")
URL = ("https://github.com/IcePanorama/FlappyBirdPSX/releases/"
       "download/v0.1.0/flappybirdpsx-v0.1.0.iso")
ISO = os.path.join(OUT, "flappybirdpsx-v0.1.0.iso")
CUE = os.path.join(EMU, "flappybird.cue")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    ev = {"t": time.time()}
    if not os.path.exists(ISO):
        t0 = time.time()
        urllib.request.urlretrieve(URL, ISO)
        ev["download"] = {"ok": True, "wall_s": round(time.time() - t0, 2)}
    sha = sha256_file(ISO)
    size = os.path.getsize(ISO)
    ev["iso"] = {"path": ISO, "bytes": size, "sha256": sha}
    # license check: sector 4 user data carries the Sony license string
    # (the r15 image used double spaces: "Licensed  by")
    with open(ISO, "rb") as f:
        f.seek(4 * 2352 + 24)
        sector4_user = f.read(64)
    lic = b"Licensed" in sector4_user and b"Sony Computer" in sector4_user
    # PVD check at sector 16 (user data starts at +24 in MODE2/2352)
    with open(ISO, "rb") as f:
        f.seek(16 * 2352 + 24)
        pvd = f.read(8)
    is9660 = pvd[1:6] == b"CD001"
    ev["structure"] = {"license_sector4": lic, "pvd_cd001": is9660}
    if not os.path.exists(CUE):
        with open(CUE, "w") as f:
            f.write('FILE "%s" BINARY\n  TRACK 01 MODE2/2352\n'
                    '    INDEX 01 00:00:00\n' % ISO)
    ev["cue"] = CUE
    print(json.dumps(ev, indent=2))
    with open(os.path.join(OUT, "fetch_report.json"), "w") as f:
        json.dump(ev, f, indent=2)


if __name__ == "__main__":
    main()

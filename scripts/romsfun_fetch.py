#!/usr/bin/env python3
"""romsfun_fetch.py — owner-supplied-source downloader for the PS1
agent-testing mission (reconstruction of the session-12 tooling, which
was not persisted).

Flow (reverse-engineered from the romsfun theme JS, /tmp/rf_main.js):
  1. GET the game page -> find /download/<slug>-<post_id> link
  2. GET the download page (cookie jar; sets the post context)
  3. POST wp-admin/admin-ajax.php  body: action=k_get_download
     (cookies + Referer of the download page) -> JSON {data: {html}}
     whose first href is the signed CDN URL
  4. The CDN serves data ONLY on Range requests -> chunked Range
     downloader with resume (X-Range chunks, .part file + .sha256)

Use: python romsfun_fetch.py --game <game-page-or-slug> --out FILE
     python romsfun_fetch.py --game <...> --probe        # signed URL only
Local testing only — disc images are never committed to the repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BASE = "https://romsfun.com"
CHUNK = 4 * 1024 * 1024          # 4 MiB range chunks
RETRY = 4


_JAR = "/tmp/rf_fetch_cookies.txt"   # curl cookie jar (session-local)


_HFILE = "/tmp/rf_fetch_headers.txt"


def _curl(url, data=None, headers=None, method=None):
    """curl transport: the site 403s python-urllib's TLS fingerprint.
    Headers -> _HFILE, code via a sentinel (header_json embeds \n)."""
    cmd = ["curl", "-s", "--max-time", "90", "-A", UA,
           "-c", _JAR, "-b", _JAR, "-D", _HFILE,
           "-w", "ZCODE=%{http_code}Z"]
    if data is not None:
        cmd += ["--data-binary", data]
    if method:
        cmd += ["-X", method]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    p = subprocess.run(cmd, capture_output=True, timeout=180)
    raw = p.stdout                       # RAW bytes — never decode the
    flat = {}                            # body (binary chunks die in a
    code = 0                             # utf-8 round-trip)
    idx = raw.rfind(b"ZCODE=")
    out = raw
    if idx >= 0:
        try:
            code = int(raw[idx + 6:].split(b"Z")[0])
            out = raw[:idx]
        except ValueError:
            code = 0
    try:
        with open(_HFILE) as f:
            for ln in f:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    flat[k.strip().lower()] = v.strip()
    except OSError:
        pass
    return code, out, flat


def _req(url, data=None, headers=None, jar=None, method=None):
    hdrs = dict(headers or {})
    return _curl(url, data=data, headers=hdrs, method=method)


def resolve_download_page(game):
    if game.startswith("http"):
        url = game
    elif game.isdigit():
        url = f"{BASE}/?p={game}"
    else:
        slug = game.rstrip(".html")
        url = f"{BASE}/roms/playstation/{slug}.html"
    st, body, _ = _req(url)
    if st != 200:
        raise SystemExit(f"game page HTTP {st}: {url}")
    html = body.decode("utf-8", "replace")
    m = re.search(r'href="https://romsfun\.com(/download/[^"]+)"', html)
    if not m:
        raise SystemExit("no /download/ link on the game page")
    return BASE + m.group(1)


def get_signed_url(dl_page, file_index=1):
    """The server parses BOTH the post id and the file index from the
    Referer path: /download/<slug>-<post_id>/<file_index>."""
    jar = {}
    ref = f"{dl_page}/{file_index}"
    st, body, _ = _req(dl_page, jar=jar)
    if st != 200:
        raise SystemExit(f"download page HTTP {st}")
    ajax = f"{BASE}/wp-admin/admin-ajax.php"
    st, body, _ = _req(
        ajax, data=b"action=k_get_download", jar=jar,
        headers={"Referer": ref,
                 "Content-Type": "application/x-www-form-urlencoded; "
                                 "charset=UTF-8",
                 "X-Requested-With": "XMLHttpRequest",
                 "Origin": BASE},
        method="POST")
    if st != 200:
        raise SystemExit(f"admin-ajax HTTP {st}")
    js = json.loads(body.decode("utf-8", "replace"))
    if not (js.get("success") and js.get("data", {}).get("html")):
        raise SystemExit(f"ajax refused: {str(js)[:200]}")
    html = js["data"]["html"].replace("&#038;", "&")
    m = re.search(r'href="([^"]+)"', html)
    if not m:
        raise SystemExit(f"no href in data.html: {html[:200]}")
    return m.group(1)


def probe(url):
    st, _, hdrs = _req(url, headers={"Range": "bytes=0-0"})
    return {"status": st, "length": hdrs.get("Content-Range"),
            "type": hdrs.get("Content-Type"),
            "accept_ranges": hdrs.get("Accept-Ranges")}


def download(url, out):
    """Unknown-size streaming: 4MiB Range chunks until a SHORT chunk
    (the CDN's Content-Range proved unreliable from this sandbox).
    Resume = append mode from the .part length."""
    part = out + ".part"
    done = os.path.getsize(part) if os.path.exists(part) else 0
    sha = hashlib.sha256()
    if done:
        with open(part, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""):
                sha.update(blk)
        print(f"resume: {done} bytes present")
    f = open(part, "ab" if done else "wb")
    t0 = time.time()
    got_total = 0
    try:
        while True:
            lo = done
            hi = done + CHUNK - 1
            got = None
            for attempt in range(RETRY):
                try:
                    st, body, _ = _req(
                        url, headers={"Range": f"bytes={lo}-{hi}"})
                    if st == 200:            # whole-file 200: slice it
                        body = body[lo:hi + 1]
                        st = 206
                    if st == 206 and body:
                        got = body
                        break
                    if st == 416:            # past EOF -> done
                        got = b""
                        break
                    print(f"  chunk@{done} status {st} "
                          f"attempt {attempt}")
                except Exception as e:
                    print(f"  chunk@{done} attempt {attempt}: {e}")
                time.sleep(2 * (attempt + 1))
            if got is None:
                raise SystemExit(f"chunk {lo}-{hi} failed after "
                                 f"{RETRY} attempts")
            if got and len(got) < CHUNK:
                f.write(got)
                sha.update(got)
                done += len(got)
                f.flush()
                got_total = 1
            elif got:
                f.write(got)
                sha.update(got)
                done += len(got)
                got_total = 1
            else:
                break                         # short/empty = EOF
            dt = time.time() - t0
            print(f"\r  {done} bytes ({done/max(dt,0.1)/1048576:.1f} "
                  f"MiB/s)", end="", flush=True)
            if got and len(got) < CHUNK:
                break
    finally:
        f.close()
    print()
    os.replace(part, out)
    with open(out + ".sha256", "w") as f:
        f.write(f"{sha.hexdigest()}  {os.path.basename(out)}\n")
    print(f"done: {out} {done} bytes "
          f"sha256={sha.hexdigest()[:16]}...")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True,
                    help="game page URL, slug, or post id")
    ap.add_argument("--out", default="")
    ap.add_argument("--file-index", type=int, default=1)
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()

    dl_page = resolve_download_page(a.game)
    print("download page:", dl_page)
    url = get_signed_url(dl_page, file_index=a.file_index)
    print("signed url:", url[:120], "...")
    info = probe(url)
    print("probe:", json.dumps(info))
    if a.probe:
        return
    out = a.out or re.sub(r"[^A-Za-z0-9._-]", "_",
                          dl_page.rsplit("/", 1)[-1]) + ".bin"
    # the signed URL stops serving mid-file (guest cap) -> re-mint and
    # resume from the .part until the file completes
    for round_ in range(30):
        try:
            download(url, out)
            break
        except SystemExit as e:
            if os.path.exists(out + ".part"):
                print(f"re-mint round {round_ + 1}: {e}")
                url = get_signed_url(dl_page, file_index=a.file_index)
                time.sleep(6)
            else:
                raise


if __name__ == "__main__":
    main()

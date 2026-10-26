#!/usr/bin/env python3
"""nortis_r12_license_check.py — Round 12 (Task 16-c) part B.

Nortis was blocked from artifact acceptance SOLELY by the missing license
(manifest rejected[]: 2026-10-22 -> 88 files / 0 license files;
2026-10-25 re-probe -> 98 files / 0 license files; the game itself boots
and plays locally through the shared core with a license-patched image).

This monitor re-checks the upstream repo TODAY through the shared GitHub
API helper (gh_api.req -> (code, obj)):

  1. GET /repos/jbreckmckye/nortis            -> license field + metadata
  2. GET /repos/jbreckmckye/nortis/contents/  -> root listing, LICENSE* scan
  3. GET /repos/jbreckmckye/nortis/commits    -> latest commits (activity)

Verdict (honest, binary):
  LICENSE_PRESENT  -> name the license + acceptance implication
  MONITORED-NO-CHANGE -> still no license, dated, integration stays blocked

Evidence: scratch/round12_nortis/ (json + raw api excerpts).
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req  # noqa: E402  (returns TUPLE (code, obj); GET: no payload)

REPO_ROOT = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO_ROOT, "scratch", "round12_nortis")
UPSTREAM = "jbreckmckye/nortis"
PRIOR_CHECKS = [
    {"date": "2026-10-22", "files": 88, "license_files": 0,
     "source": "manifest rejected[] re-verification via API"},
    {"date": "2026-10-25", "files": 98, "license_files": 0,
     "source": "round-4 license re-probe via API"},
]
LICENSE_PAT = ("licence", "license", "copying", "copyright", "unlicense",
               "legal", "notice", "patents")


def main():
    os.makedirs(OUT, exist_ok=True)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    ev = {"schema": "ps1ai-nortis-license-monitor/1",
          "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
          "task": "16-c", "upstream": UPSTREAM,
          "api_helper": "/home/z/my-project/scripts/gh_api.py (token 2)",
          "prior_checks": PRIOR_CHECKS, "checks": {}}

    # ---- 1. repo metadata + GitHub's license detection ----
    code, repo = req(f"/repos/{UPSTREAM}")
    ev["checks"]["repo"] = {
        "http": code,
        "full_name": repo.get("full_name"),
        "default_branch": repo.get("default_branch"),
        "size_kb": repo.get("size"),
        "pushed_at": repo.get("pushed_at"),
        "updated_at": repo.get("updated_at"),
        "archived": repo.get("archived"),
        "github_license_field": repo.get("license"),
        "message": repo.get("message") if code != 200 else None,
    }

    # ---- 2. root listing -> LICENSE* file scan ----
    code_c, contents = req(f"/repos/{UPSTREAM}/contents/")
    listing = []
    if code_c == 200 and isinstance(contents, list):
        for ent in contents:
            listing.append({"name": ent.get("name"), "type": ent.get("type"),
                            "size": ent.get("size")})
    lic_hits = [e["name"] for e in listing
                if e["name"] and any(p in e["name"].lower()
                                     for p in LICENSE_PAT)]
    ev["checks"]["contents"] = {
        "http": code_c, "n_entries": len(listing),
        "root_names": [e["name"] for e in listing],
        "license_like_files": lic_hits,
        "release_zip_present": any(e["name"] == "release.zip"
                                   for e in listing),
    }

    # ---- 2b. full-tree scan (matches the prior 88/98-file methodology) ----
    branch = ev["checks"]["repo"].get("default_branch") or "master"
    code_t, tree = req(f"/repos/{UPSTREAM}/git/trees/{branch}?recursive=1")
    blobs, lic_tree_hits, zip_hits = [], [], []
    if code_t == 200 and isinstance(tree, dict):
        for e in tree.get("tree", []):
            if e.get("type") != "blob":
                continue
            p = e.get("path", "")
            blobs.append(p)
            base = p.lower().rsplit("/", 1)[-1]
            if any(pat in base for pat in LICENSE_PAT):
                lic_tree_hits.append(p)
            if base.endswith(".zip"):
                zip_hits.append(p)
    ev["checks"]["tree"] = {
        "http": code_t, "truncated": tree.get("truncated")
        if isinstance(tree, dict) else None,
        "n_blobs": len(blobs),
        "license_like_paths": lic_tree_hits,
        "zip_files": zip_hits,
    }

    # ---- 3. latest commits (activity + sha for the record) ----
    code_m, commits = req(f"/repos/{UPSTREAM}/commits?per_page=5")
    cl = []
    if code_m == 200 and isinstance(commits, list):
        for c in commits:
            cl.append({"sha": (c.get("sha") or "")[:12],
                       "date": (c.get("commit") or {}).get("author", {})
                       .get("date"),
                       "msg": ((c.get("commit") or {}).get("message") or
                               "").splitlines()[0][:100]})
    ev["checks"]["commits"] = {"http": code_m, "latest": cl}

    # ---- verdict ----
    gh_lic = ev["checks"]["repo"].get("github_license_field")
    if (code == 200) and (gh_lic or lic_hits):
        verdict = "LICENSE_PRESENT"
        detail = {"github_license_field": gh_lic,
                  "license_like_files": lic_hits}
    elif code == 200:
        verdict = "MONITORED-NO-CHANGE"
        detail = {"github_license_field": None,
                  "license_like_files_root": lic_hits,
                  "license_like_paths_tree": ev["checks"]["tree"]
                  .get("license_like_paths"),
                  "files_root_today": len(listing),
                  "files_tree_today": ev["checks"]["tree"].get("n_blobs"),
                  "checked_date": today}
    else:
        verdict = f"CHECK-FAILED(http {code})"
        detail = {"message": ev["checks"]["repo"].get("message")}
    ev["verdict"] = {"label": verdict, "detail": detail, "date": today}

    # acceptance implication (explicit, honest)
    if verdict == "LICENSE_PRESENT":
        lic_name = (gh_lic or {}).get("spdx_id") if gh_lic else None
        ev["implication"] = (
            f"Upstream now exposes a license "
            f"({(gh_lic or {}).get('name') if gh_lic else lic_hits}); "
            f"spdx_id={lic_name}. If SPDX is an accepted permissive license "
            f"(MIT/BSD/Zlib-class), the sole acceptance blocker for Nortis "
            f"is lifted: re-verify the pinned artifact digest, re-run the "
            f"boot+input gate on a LOCAL license-patched image, then move "
            f"nortis from manifest rejected[] to accepted[].")
    elif verdict == "MONITORED-NO-CHANGE":
        tr = ev["checks"]["tree"]
        ev["implication"] = (
            f"Still no LICENSE file and no GitHub-detected license upstream "
            f"(root {len(listing)} entries, full tree {tr.get('n_blobs')} "
            f"blobs, 0 license-like paths); redistribution rights remain "
            "unverified -> artifact acceptance stays blocked (manifest "
            "rejected[] unchanged). Local-only license-patched testing "
            "remains the only permitted use. Re-check on a later round "
            f"(this check dated {today}).")
    else:
        ev["implication"] = ("API check did not return 200; no conclusion "
                             "this round - re-run the monitor.")

    with open(os.path.join(OUT, "nortis_license_check.json"), "w") as f:
        json.dump(ev, f, indent=1)
    print(json.dumps({"verdict": ev["verdict"], "implication":
                      ev["implication"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

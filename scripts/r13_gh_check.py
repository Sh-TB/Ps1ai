#!/usr/bin/env python3
"""r13_gh_check.py — Round 13 GitHub recon: issue activity + search for
a NEW tiny PS1 homebrew game (with a downloadable binary artifact)."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO                                     # noqa: E402

s, issues = req(f"/repos/{REPO}/issues?state=all&per_page=20&sort=updated")
print("=== ISSUES (recent) ===")
for i in issues:
    print(f"#{i['number']} [{i['state']}] c={i['comments']} "
          f"{i['title'][:80]} (upd {i['updated_at'][:10]})")

print("\n=== ISSUE #6 last 2 comments (titles/teasers) ===")
s, cs = req(f"/repos/{REPO}/issues/6/comments?per_page=100")
if s == 200 and cs:
    for c in cs[-2:]:
        body = c["body"][:220].replace("\n", " ")
        print(f"- {c['created_at'][:16]} {body}")

print("\n=== SEARCH: tiny PS1 homebrew games ===")
QUERIES = [
    "/search/repositories?q=ps1+homebrew+game&sort=updated&per_page=15",
    "/search/repositories?q=psx+homebrew+game&sort=stars&per_page=15",
    "/search/repositories?q=playstation+homebrew+game+in:name,description"
    "&sort=stars&per_page=15",
]
seen = set()
for q in QUERIES:
    s, d = req(q)
    if s != 200:
        print(f"  search failed: {s} {str(d)[:120]}")
        continue
    for r in d.get("items", []):
        fn = r["full_name"]
        if fn in seen:
            continue
        seen.add(fn)
        print(f"  {fn} ★{r['stargazers_count']} "
              f"push {r['pushed_at'][:10]} — {(r['description'] or '')[:90]}")

print("\n=== RELEASES check on promising candidates ===")
CANDS = ["marconvcm/ps1_dev", "ps1homebrew/Deflektor-Xtreme"]
for fn in list(seen)[:0] + CANDS:
    s, d = req(f"/repos/{fn}/releases?per_page=3")
    if s == 200 and d:
        for rel in d[:2]:
            assets = [(a["name"], a["size"], a["browser_download_url"])
                      for a in rel.get("assets", [])]
            print(f"  {fn} rel '{rel['tag_name']}': "
                  f"{assets if assets else 'NO ASSETS'}")
    else:
        print(f"  {fn}: no releases ({s})")

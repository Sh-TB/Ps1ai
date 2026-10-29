#!/usr/bin/env python3
"""R38 step 1: non-destructive reconciliation against GitHub (issues 5, 9, 10)."""
import json
import urllib.request
import sys

REPO = "Sh-TB/Ps1ai"
HDR = {"User-Agent": "ps1ai-r38-recon", "Accept": "application/vnd.github+json"}


def get(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    # repo head
    try:
        branch = get(f"https://api.github.com/repos/{REPO}/branches/main")
        print("origin/main on GitHub:", branch["commit"]["sha"])
    except Exception as e:
        print("branch fetch failed:", e)
        return 1

    for num in (5, 9, 10):
        try:
            issue = get(f"https://api.github.com/repos/{REPO}/issues/{num}")
            print(f"\n=== Issue #{num} [{issue['state']}] {issue['title']}")
            body = (issue.get("body") or "")[:300].replace("\n", " | ")
            print("  body[:300]:", body)
            comments = get(
                f"https://api.github.com/repos/{REPO}/issues/{num}/comments?per_page=100"
            )
            print(f"  comments: {len(comments)}")
            # print id + first 220 chars of each comment, and search for clear claims
            for c in comments:
                txt = c.get("body") or ""
                low = txt.lower()
                flag = ""
                for kw in ("clear", "cleared", "banner", "complete screen",
                           "mission end", "verified", "3/3", "divergence"):
                    if kw in low:
                        flag += f" <{kw}>"
                        break
                head = " ".join(txt[:200].split())
                print(f"  - id={c['id']} {c['created_at'][:10]}{flag}")
                print(f"      {head}")
        except Exception as e:
            print(f"issue {num} fetch failed:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())

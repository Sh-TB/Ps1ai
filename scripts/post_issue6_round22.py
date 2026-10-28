#!/usr/bin/env python3
"""post_issue6_round22.py — post the Round 22 report to lab-log Issue #6."""
import pathlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import REPO, req  # noqa: E402

BODY = pathlib.Path("docs/issue6_r22_report.md").read_text()
BODY = f"Round 22 lab log (commit df86823, suite 565+1xfail):\n\n{BODY}"

status, r = req(f"/repos/{REPO}/issues/6/comments", method="POST", payload={"body": BODY})
print("status:", status, "id:", r.get("id"), "url:", r.get("html_url"))

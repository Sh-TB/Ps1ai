#!/usr/bin/env python3
"""post_issue6_round21.py — post the Round 21 report to lab-log Issue #6."""
import pathlib
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import REPO, req  # noqa: E402

BODY = pathlib.Path("docs/issue6_r21_report.md").read_text()
BODY = f"Round 21 lab log (commit 6889f07, push a40ab07..6889f07, suite 565+1xfail):\n\n{BODY}"

r = req(f"/repos/{REPO}/issues/6/comments", method="POST", payload={"body": BODY})
print("posted:", r.get("html_url", r))

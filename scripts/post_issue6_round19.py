#!/usr/bin/env python3
"""post_issue6_round19.py — Round 19 (ten-train fleet) report on Issue #6."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO                                     # noqa: E402

with open("/home/z/my-project/ps1ai/docs/issue6_r19_report.md",
          encoding="utf-8") as f:
    BODY = f.read().replace("<>FILL_AT_SEND<>", "`d5f12f9`")

s, d = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": BODY})
print("status:", s, "| id:", d.get("id"), "| url:", d.get("html_url"))

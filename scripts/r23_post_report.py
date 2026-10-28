#!/usr/bin/env python3
"""r23_post_report.py — post the Round 23 report to Issue #6."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

body = open("/home/z/my-project/ps1ai/docs/issue6_r23_report.md").read()
header = ("## Round 23 — MSPSX RUNNING · BuzzyBee GAMEPLAY_CONFIRMED "
          "(game #10) · PAL display-path root cause\n\n")
s, r = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": header + body})
print("HTTP", s, "comment id:", r.get("id"),
      "url:", r.get("html_url", r.get("message", "")))

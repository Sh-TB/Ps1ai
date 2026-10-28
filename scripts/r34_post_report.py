#!/usr/bin/env python3
"""r34_post_report.py — post the Round 34 report to Issue #6."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

body = open("/home/z/my-project/ps1ai/docs/issue6_r34_report.md").read()
header = ("## Round 34 — the recorded lever executed: instrumented "
          "beetle proves the pad bus healthy for BOTH games; r30-r32 "
          "'input regression' REFUTED as an observation artifact "
          "(raw 0x8005xxxx reads); BuzzyBee deep systems COMPLETE "
          "(ALL_PHASES_OK) — mspSX was already PLAYING #9: both "
          "games of the completion directive now closed\n\n")
s, r = req(f"/repos/{REPO}/issues/6/comments", method="POST",
           payload={"body": header + body})
print("HTTP", s, "comment id:", r.get("id"),
      "url:", r.get("html_url", r.get("message", "")))

#!/usr/bin/env python3
"""hmbtn_text.py — Harvest Moon: Back to Nature (SLUS-01115) text/decorpus tool.

Knowledge base: coalslav/hmbtn-decomp (CC0) documents the game's u16 glyph
charset (text_bank.c header, src/main/text/text.h enums) and the A_FILE.BIN
member map (disc/a_file.txt): members 02..06 = messege0..4.bin, the dialogue
banks, unpacked from the user's own disc with tools/afile.py.

Subcommands
  glyphs  — learn/verify the glyph map against every commented plaintext in
            the decomp source (comment text <-> u16 array pairs)
  corpus  — extract + decode every commented plaintext into a local corpus
            (markdown + JSON; game text stays LOCAL, only stats are committed)
  decode  — decode a literal u16 stream from --hex
  afile   — disc mode (pending the user's disc): list/extract A_FILE.BIN
            members and decode the messege*.bin dialogue banks

No game text is ever committed: corpus output paths default under scratch/.
"""
import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------- charset
# Blocks documented in hmbtn-decomp src/main/text/text_bank.c + text.h.
UPPER_BASE, LOWER_BASE, DIGIT_BASE = 0x0000, 0x0020, 0x0040
CODE_SPACE = 0x0FFD
CODE_LINE_BREAK = 0xFFFE
CODE_END = 0xFFFF

RANGES_CTRL = [
    (0x0FF1, 0x0FFC, "ctrl"),   # scroll hold / face / choices / page marks
    (0x0E25, 0x0E2F, "wait"),   # TEXT_CODE_WAIT_FIRST..LAST
    (0x0E38, 0x0FEF, "face"),   # TEXT_CODE_FACE_FIRST..LAST
]


def classify(v):
    if v == CODE_SPACE:
        return "space"
    if v == CODE_LINE_BREAK:
        return "linebreak"
    if v == CODE_END:
        return "end"
    if UPPER_BASE <= v < UPPER_BASE + 26:
        return "upper"
    if LOWER_BASE <= v < LOWER_BASE + 26:
        return "lower"
    if DIGIT_BASE <= v < DIGIT_BASE + 10:
        return "digit"
    for lo, hi, tag in RANGES_CTRL:
        if lo <= v <= hi:
            return tag
    if 0x4000 <= v < 0x8000:
        return "insert"
    return "other"


# ------------------------------------------------------------------ parsing
C_COMMENT_TEXT = re.compile(r'/\*\s*"((?:[^"\\]|\\.)*)"\s*\*/')
C_HEX_VALUES = re.compile(r"\{((?:\s*0[xX][0-9A-Fa-f]{1,4}\s*,?)+)\s*\}")
C_ESCAPES = {"\\n": "\n", "\\t": "\t", '\\"': '"', "\\\\": "\\"}


def unescape_comment(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            two = s[i:i + 2]
            if two in C_ESCAPES:
                out.append(C_ESCAPES[two])
                i += 2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def iter_commented_arrays(path):
    """Yield (comment_text, [u16 values]) for every `/* "..." */` comment
    immediately followed (same or next lines) by a hex u16 brace list."""
    lines = Path(path).read_text(errors="replace").splitlines()
    pending = None
    buf = []
    for ln in lines:
        m = C_COMMENT_TEXT.search(ln)
        if m:
            pending = unescape_comment(m.group(1))
            buf = [ln[m.end():]]
            continue
        if pending is not None:
            buf.append(ln)
            joined = "\n".join(buf)
            hm = C_HEX_VALUES.search(joined)
            if hm:
                vals = [int(x, 16) for x in re.findall(r"0[xX][0-9A-Fa-f]{1,4}", hm.group(1))]
                if vals:
                    yield pending, vals
                pending = None
                buf = []
            elif len(buf) > 12:
                pending = None
                buf = []


# ---------------------------------------------------------------- decoding
# Punctuation/contraction glyphs outside the documented blocks. Learned
# offline from the decomp's own comment<->array pairs where 1:1 alignment
# breaks (multi-char expansions), each backed by >=3 independent contexts:
#   0x0050 "'"  — "Didn<0050>t feed animal" <-> "Didn't feed animal" (+Don<0050>t, Can<0050>t)
#   0x0051 "'s" — "Covet other<0051> girl" <-> "Covet other's girl" (+Farm/Dog/This month<0051>)
#   0x0054 "'m" — "Hi, I<0054> back" <-> "Hi, I'm back"
#   0x0066 ":"  — "Birthday<0066>" (+Your name <0066>, Farm<0051> name<0066>)
#   0x0071 "/"  — "cows<0071>sheep" (x3 contexts, + standalone separator rows)
DEFAULT_OTHER = {0x0050: "'", 0x0051: "'s", 0x0054: "'m", 0x0066: ":", 0x0071: "/"}


def decode_stream(values, extra=None):
    """u16 glyph stream -> text (+ per-value classes). Control codes render
    as <tag[:v]> placeholders; inserts as <insert:v>."""
    extra = extra or {}
    out = []
    for v in values:
        c = classify(v)
        if c == "space":
            out.append(" ")
        elif c == "linebreak":
            out.append("\n")
        elif c == "end":
            break
        elif c == "upper":
            out.append(chr(ord("A") + v - UPPER_BASE))
        elif c == "lower":
            out.append(chr(ord("a") + v - LOWER_BASE))
        elif c == "digit":
            out.append(chr(ord("0") + v - DIGIT_BASE))
        elif c in ("ctrl", "wait", "face"):
            out.append(f"<{c}:{v:04X}>")
        elif c == "insert":
            out.append(f"<insert:{v - 0x4000}>")
        else:
            if v in extra:
                out.append(extra[v])
            elif v in DEFAULT_OTHER:
                out.append(DEFAULT_OTHER[v])
            else:
                out.append(f"<{v:04X}>")
    return "".join(out)


def align_votes(comment, values, votes, stats):
    """Vote value->char for glyphs outside the documented blocks by aligning
    a decoded-with-knowns stream to the comment text."""
    dec = []
    for v in values:
        c = classify(v)
        if c == "end":
            break
        dec.append((v, c))
    plain = []
    for v, c in dec:
        if c == "space":
            plain.append(" ")
        elif c == "upper":
            plain.append(chr(ord("A") + v - UPPER_BASE))
        elif c == "lower":
            plain.append(chr(ord("a") + v - LOWER_BASE))
        elif c == "digit":
            plain.append(chr(ord("0") + v - DIGIT_BASE))
        elif c == "linebreak":
            plain.append("\n")
        elif c == "other":
            plain.append(None)
        else:
            return False  # ctrl/face/insert pairs can't be aligned 1:1
    if len(plain) != len(comment):
        stats["len_mismatch"] += 1
        return False
    ok = True
    for i, (v, _c) in enumerate(dec):
        want = comment[i]
        got = plain[i]
        if got is None:
            # unknown glyph: vote for the comment's character at this position
            votes[v][want] += 1
            ok = False
        elif got != want:
            stats["mismatch"] += 1
            ok = False
        else:
            stats["match"] += 1
    return ok


def learn_glyph_map(src_root):
    from collections import defaultdict
    votes = defaultdict(lambda: defaultdict(int))
    stats = {"match": 0, "mismatch": 0, "len_mismatch": 0, "pairs": 0, "aligned": 0}
    for path in sorted(Path(src_root).rglob("*.c")):
        for comment, vals in iter_commented_arrays(path):
            stats["pairs"] += 1
            align_votes(comment, vals, votes, stats)
    learned = {}
    for v, counter in sorted(votes.items()):
        ranked = sorted(counter.items(), key=lambda kv: -kv[1])
        ch, n = ranked[0]
        total = sum(counter.values())
        if n / total >= 0.9 and classify(v) == "other":
            learned[v] = ch
    return learned, stats, votes


def extract_corpus(src_root, extra):
    rows = []
    for path in sorted(Path(src_root).rglob("*.c")):
        rel = str(path.relative_to(src_root))
        for comment, vals in iter_commented_arrays(path):
            text = decode_stream(vals, extra)
            rows.append({"file": rel, "comment": comment, "decoded": text,
                         "n_values": len(vals)})
    return rows


# ------------------------------------------------------------- A_FILE (disc)
AFILE_HEADER = struct.Struct("<I")


def afile_list(blob):
    """A_FILE.BIN: u32 LE member count, then u32 LE offsets (count+1)."""
    (n,) = AFILE_HEADER.unpack_from(blob, 0)
    offs = struct.unpack_from(f"<{n + 1}I", blob, 4)
    return n, offs


def afile_member(blob, idx):
    n, offs = afile_list(blob)
    return blob[offs[idx]:offs[idx + 1]]


def u16_stream(blob):
    vals = []
    for (v,) in struct.iter_unpack("<H", blob[: len(blob) // 2 * 2]):
        vals.append(v)
    return vals


# --------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("glyphs")
    p.add_argument("--src", required=True)
    p.add_argument("--json-out")

    p = sub.add_parser("corpus")
    p.add_argument("--src", required=True)
    p.add_argument("--out-json")
    p.add_argument("--out-md")

    p = sub.add_parser("decode")
    p.add_argument("--hex", required=True)

    p = sub.add_parser("afile")
    p.add_argument("--afile", required=True)
    p.add_argument("--member-index", type=int)
    p.add_argument("--json-out")

    args = ap.parse_args()

    if args.cmd == "glyphs":
        learned, stats, votes = learn_glyph_map(args.src)
        print(f"pairs={stats['pairs']} aligned_char_matches={stats['match']} "
              f"mismatches={stats['mismatch']} len_mismatches={stats['len_mismatch']}")
        print("learned punctuation glyphs:")
        for v, ch in sorted(learned.items()):
            print(f"  0x{v:04X} -> {ch!r}  ({sum(votes[v].values())} votes)")
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(
                {"stats": stats, "learned": {f"0x{k:04X}": v for k, v in learned.items()}},
                indent=1))
        return 0

    if args.cmd == "corpus":
        learned, stats, _ = learn_glyph_map(args.src)
        rows = extract_corpus(args.src, learned)
        verified = sum(1 for r in rows if r["decoded"] == r["comment"])
        print(f"rows={len(rows)} verified_exact={verified} "
              f"({100 * verified / max(1, len(rows)):.1f}%)")
        if args.out_json:
            Path(args.out_json).write_text(json.dumps(rows, indent=1))
        if args.out_md:
            lines = ["# HMBTN local decorpus (DO NOT COMMIT — game-derived text)\n"]
            cur = None
            for r in rows:
                if r["file"] != cur:
                    cur = r["file"]
                    lines.append(f"\n## {cur}\n")
                mark = "OK " if r["decoded"] == r["comment"] else "?? "
                text = r["decoded"].replace("\n", "\\n")
                lines.append(f"- {mark}{text}\n")
            Path(args.out_md).write_text("".join(lines))
        return 0

    if args.cmd == "decode":
        vals = [int(x, 16) for x in re.findall(r"0[xX][0-9A-Fa-f]{1,4}", args.hex)]
        print(decode_stream(vals))
        return 0

    if args.cmd == "afile":
        blob = Path(args.afile).read_bytes()
        n, offs = afile_list(blob)
        print(f"members={n}")
        if args.member_index is not None:
            m = afile_member(blob, args.member_index)
            text = decode_stream(u16_stream(m), {})
            print(text)
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(
                {"members": n, "offsets": list(offs)}, indent=1))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

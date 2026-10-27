#!/usr/bin/env python3
"""hmbtn_text.py — Harvest Moon: Back to Nature (SLUS-01115) text/decorpus tool.

Knowledge base: coalslav/hmbtn-decomp (CC0) documents the game's u16 glyph
charset (text_bank.c header, src/main/text/text.h enums) and the A_FILE.BIN
member map (disc/a_file.txt): members 02..06 = messege0..4.bin, the dialogue
banks, unpacked from the user's own disc with tools/afile.py.

Round 19 cross-validation (disc-free) against GabriPires/traducao-hm-btn-ptbr
(MIT, tables/hmbtn.tbl + docs/): the punctuation map below now agrees with
BOTH the decomp's own comment<->array corpus AND the PT-BR project's
font-rendered table. One contradiction was found and fixed: 0x0050 renders
"'t", not "'" (the decomp array for "Didn't feed animal" is
D i d n <0050> _ f e e d — one value shorter than the comment, exactly the
't; the PT-BR table says the same).

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
# Punctuation/contraction glyphs outside the documented blocks. Round 19 map —
# every entry is backed by at least one of:
#   [d] the hmbtn-decomp comment<->array corpus (decodes byte-exact there),
#   [t] the PT-BR translation's font-rendered table (tables/hmbtn.tbl),
#   [e] hmbtn-decomp src/main/text/text.c enum TextGlyph,
#   [m] hm-btn-mod-tool src/hm_btn_tool/text.py (Suphanat1722, MIT).
# Corpus status with this map: 314/353 rows byte-exact (89.0%), and 343/353
# (97.2%) when control codes are rendered in the decomp comments' own style.
# (r16 note, now corrected: 0x0050 was read as "'" — wrong. The decomp array
# for "Didn't feed animal" is D i d n <0050> _ f e e d, one value short of the
# comment by exactly the "'t"; 0x0050 = "'t" per the corpus, the PT-BR table
# AND hm-btn-mod-tool. Likewise 0x0055='r is proven by mg3's
# "You<55> out of ...". Known source disagreement, resolved by corpus votes:
# 0x006C='.' (39+ decomp votes) though mod-tool lists ',' there.)
DEFAULT_OTHER = {
    # contraction glyphs: one value draws apostrophe + letter [d][t]
    0x0050: "'t",   # [d][t] "Didn<50> feed" <-> "Didn't feed"
    0x0051: "'s",   # [d][t] "Farm<51> name" <-> "Farm's name"
    0x0052: "'l",   # [t]
    0x0053: "'d",   # [t]
    0x0054: "'m",   # [d][t] "I<54> back" <-> "I'm back"
    0x0055: "'r",   # [d][t] mg3 "You<55> out" <-> "You're out"
    0x0056: "'v",   # [t]
    # punctuation
    0x0062: "?",    # [d][t][e] TEXT_GLYPH_QUESTION
    0x0063: "!",    # [d][t][e] TEXT_GLYPH_EXCLAIM
    0x0065: "•",    # [m] bullet (hm-btn-mod-tool text.py; PT-BR leaves it
                    #     undocumented; 0 occurrences in the decomp corpus)
    0x0066: ":",    # [d][t]
    0x0067: ";",    # [t]
    0x0068: "+",    # [t]
    0x0069: "-",    # [d][t][e] TEXT_GLYPH_MINUS
    0x006A: "(",    # [t][e] TEXT_GLYPH_LPAREN
    0x006B: ")",    # [t][e] TEXT_GLYPH_RPAREN
    0x006C: ".",    # [d][t]
    0x0071: "/",    # [t] button-action separator; "cows<71>sheep" (decomp comments raw)
    0x0074: "~",    # [t]
    0x0076: "&",    # [d][t] "Earnings <76> expenses" <-> "Earnings & expenses"
    0x007F: "…",    # [t] single-glyph ellipsis
    0x0080: "♥",    # [d][t] after names/farewells ("See you later <80>")
    0x008C: ",",    # [d][t]
    0x008D: "'",    # [t] the two-character 's fallback apostrophe
    0x008E: '"',    # [t]
    0x008F: "%",    # [t]
}

# Insert halfwords: TEXT_INSERT_FLAG | id, id = low 12 bits [e][t]:
#   0x400A player, 400B horse, 400C dog, 400D farm, 400E child, 400F wife's
#   nickname (Honey/Darling), 401B-4020 dead-animal lists (PT-BR docs/02,
#   jump table at EXE 0x800100DC).
INSERT_FLAG = 0x4000
INSERT_ID_MASK = 0x0FFF


def decode_stream(values, extra=None, faithful=False):
    """u16 glyph stream -> text (+ per-value classes). Control codes render
    as <tag[:v]> placeholders; inserts as <insert:v>.

    faithful=True renders placeholders the way the hmbtn-decomp source comments
    do (inserts as the raw <400a> value, ctrl/wait/face as {ffb}-style raw
    codes) — used to measure byte-exact corpus coverage."""
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
            out.append(f"<{c}:{v:04X}>" if not faithful else f"{{{v:x}}}")
        elif c == "insert":
            out.append(f"<insert:{v - 0x4000}>" if not faithful else f"<{v:04x}>")
        else:
            if v in extra:
                out.append(extra[v])
            elif v in DEFAULT_OTHER:
                out.append(DEFAULT_OTHER[v])
            else:
                out.append(f"<{v:04X}>" if not faithful else
                           (f"{{{v:02x}}}" if v < 0x100 else f"{{{v:04x}}}"))
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


def extract_corpus(src_root, extra, faithful=False):
    rows = []
    for path in sorted(Path(src_root).rglob("*.c")):
        rel = str(path.relative_to(src_root))
        for comment, vals in iter_commented_arrays(path):
            text = decode_stream(vals, extra, faithful=faithful)
            rows.append({"file": rel, "comment": comment, "decoded": text,
                         "n_values": len(vals)})
    return rows


# ------------------------------------------------------------ dialogue records
# A_FILE.BIN/A_FILE.HDT (tools/afile.py, hmbtn-decomp): HDT = u32 LE byte
# offsets into BIN, one per member plus a final = archive size; every member is
# zero-padded to whole 2048-byte sectors. Dialogue members 02..06 = fixed-size
# records (PT-BR docs/02-dialogos.md, decomp menu_window.c + name_entry.c):
#   record r of member m at byte offset m_off + r*RECORD_SIZE (0x2000)
#     0x0000  s32 portrait bank id (-1 none) + portrait texture pack
#     0x1800  u16 glyph stream, up to 1023 values + 0xFFFF, zero padding
# No index: the game computes r * 0x2000 directly (menu_data_index << 13).
AFILE_SECTOR = 0x800
RECORD_SIZE = 0x2000
RECORD_TEXT_OFFSET = 0x1800
RECORD_MAX_VALUES = (RECORD_SIZE - RECORD_TEXT_OFFSET) // 2 - 1
DIALOGUE_MEMBERS = (2, 3, 4, 5, 6)  # messege0..4.bin (menu_window_values)


def split_prefix(values):
    """Length of the leading control-code run (0x0E00..0x0FFF except space
    0x0FFD): portrait/window prefix, per the PT-BR exporter's split_prefix."""
    n = 0
    while n < len(values) and 0x0E00 <= values[n] <= 0x0FFF and values[n] != 0x0FFD:
        n += 1
    return n


def record_u16_stream(record):
    """The u16 text stream of one 0x2000-byte record (stops at 0xFFFF)."""
    vals = u16_stream(record[RECORD_TEXT_OFFSET:RECORD_SIZE])
    for i, v in enumerate(vals):
        if v == CODE_END:
            return vals[:i]
    return vals


# ------------------------------------------------------------- A_FILE (disc)
AFILE_HEADER = struct.Struct("<I")


def afile_list(blob, hdt=None):
    """A_FILE archive directory.

    Real format (hmbtn-decomp tools/afile.py + afile.c): A_FILE.HDT is the
    directory — u32 LE byte offsets into A_FILE.BIN, one per member plus a
    final entry equal to the BIN size; members are 2048-sector-aligned.
    Pass the .HDT bytes as `hdt`. Without it, falls back to the legacy
    embedded layout (u32 count + count+1 offsets at the BIN start)."""
    if hdt is not None:
        offs = struct.unpack(f"<{len(hdt) // 4}I", hdt)
        return len(offs) - 1, offs
    (n,) = AFILE_HEADER.unpack_from(blob, 0)
    offs = struct.unpack_from(f"<{n + 1}I", blob, 4)
    return n, offs


def afile_member(blob, idx, hdt=None):
    n, offs = afile_list(blob, hdt)
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
    p.add_argument("--hdt", help="A_FILE.HDT directory (real game format)")
    p.add_argument("--member-index", type=int)
    p.add_argument("--records", action="store_true",
                   help="decode the 0x2000-byte dialogue records of a "
                        "messege member (02..06) instead of a flat stream")
    p.add_argument("--limit", type=int, default=0,
                   help="only decode the first N records")
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
        extra = {**DEFAULT_OTHER, **learned}
        rows = extract_corpus(args.src, extra)
        frows = extract_corpus(args.src, extra, faithful=True)
        verified = sum(1 for r in rows if r["decoded"] == r["comment"])
        fverified = sum(1 for r in frows if r["decoded"] == r["comment"])
        print(f"rows={len(rows)} verified_exact={verified} "
              f"({100 * verified / max(1, len(rows)):.1f}%) "
              f"comment_faithful={fverified} "
              f"({100 * fverified / max(1, len(frows)):.1f}%)")
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
        hdt = Path(args.hdt).read_bytes() if args.hdt else None
        n, offs = afile_list(blob, hdt)
        print(f"members={n}")
        if args.member_index is not None:
            m = afile_member(blob, args.member_index, hdt)
            if args.records:
                count = len(m) // RECORD_SIZE
                if count * RECORD_SIZE != len(m):
                    print(f"warning: member {args.member_index} size "
                          f"{len(m)} is not a multiple of {RECORD_SIZE}")
                shown = 0
                out_rows = []
                for r in range(count):
                    rec = m[r * RECORD_SIZE:(r + 1) * RECORD_SIZE]
                    vals = record_u16_stream(rec)
                    if not vals:
                        continue
                    rid = f"{args.member_index:02d}-{r + 1:04d}"
                    off = offs[args.member_index] + r * RECORD_SIZE \
                        + RECORD_TEXT_OFFSET
                    prefix_n = split_prefix(vals)
                    prefix = decode_stream(vals[:prefix_n], faithful=True) \
                        if prefix_n else ""
                    text = decode_stream(vals, faithful=True)
                    print(f"{rid} @0x{off:X} n={len(vals)} "
                          f"prefix={prefix} text={text!r}")
                    out_rows.append({"id": rid, "afile_byte_offset": off,
                                     "prefix": prefix, "text": text,
                                     "n_values": len(vals)})
                    shown += 1
                    if args.limit and shown >= args.limit:
                        break
                if args.json_out:
                    Path(args.json_out).write_text(json.dumps(
                        {"member": args.member_index, "records": count,
                         "decoded": out_rows}, indent=1, ensure_ascii=False))
            else:
                text = decode_stream(u16_stream(m), {})
                print(text)
        if args.json_out and not args.records:
            Path(args.json_out).write_text(json.dumps(
                {"members": n, "offsets": list(offs)}, indent=1))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""r21t1_bkbs_wrap.py — build a bootable disc for BKBS (hardrockbluesky/BKBS_PSX)
from the GitHub source tree artifacts (task r21t1).

Why this route: the GitHub repo ships NO releases; the prebuilt PS-X EXE
(BKBS/MAIN.EXE, 172,032 B) + 11 data files + two CDDA WAVs are in the repo
tree itself. The game (one-song rhythm game, PSY-Q/LibGS) does:
  - cd_read_file("\\NAME;1") for 11 files  -> must all be on the ISO
  - DsCommand(CdlPlay, MSF 00:22:55) in PlaySyncedTrack() then HARD-WAITS
    for CD status 0x82 (CDDA playing) -> an audio track whose INDEX 01 sits
    exactly at that MSF is REQUIRED or the game hangs before its first frame.
    (Audio.c: songLoc = 00:22:55 BCD == LBA 2485.)

Layout (mirrors BKBS/mkpsxiso/cuesheet.xml semantics with iso9660_min):
  LBA 0..15     license sectors (copy 16 from the user's own retail MSX disc,
                local-only, same unblock as make_homebrew_lic.py)
  LBA 16..      iso9660_min data track: SYSTEM.CNF, MAIN.EXE + 11 data files
  LBA ..2334    dummy zero sectors (pads the data track)
  LBA 2335      TRACK 02 AUDIO INDEX 00 (2 s silence pregap)   [cue 00:33:10]
  LBA 2485      TRACK 02 AUDIO INDEX 01 = Bambi.wav PCM        [cue 00:35:10]
                == songLoc MSF 00:22:55 (BCD) == LBA 2485
  LBA ..        TRACK 03 AUDIO INDEX 00 (2 s pregap), INDEX 01 = untitled.wav

Output: emu/games_homebrew/patched/bkbs_lic.bin/.cue — LOCAL ONLY, never
committed (game bytes + license policy, see data/homebrew/manifest.json).
"""
import hashlib
import os
import struct
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import iso9660_min  # noqa: E402

SRC = "/home/z/my-project/emu/games_homebrew/bkbs"
MSX = os.environ.get(
    "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
BIN_NAME = "bkbs_lic.bin"

SEC = 2352
USER = 2048
# PlaySyncedTrack(): songLoc.minute=0x00 second=0x22 sector=0x55 (BCD)
# -> 34 s + 85 frames -> LBA = 34*75 + 85 - 150 = 2485
SONG_LBA = 0x22 * 75 + 0x55 - 150
PREGAP = 150                       # 2 s INDEX 00 before each audio track
DATA_END = SONG_LBA - PREGAP       # data track must end exactly here (2335)


def msf(lba):
    """Cue-sheet MSF string for an absolute LBA (cue time = LBA + 150)."""
    t = lba + 150
    return f"{t // (75 * 60):02d}:{(t // 75) % 60:02d}:{t % 75:02d}"


def wav_pcm(path):
    """Extract 16-bit LE stereo PCM from a RIFF/WAVE file (44100 Hz expected)."""
    b = open(path, "rb").read()
    assert b[:4] == b"RIFF" and b[8:12] == b"WAVE", path
    off, fmt = 12, None
    while off + 8 <= len(b):
        cid, sz = b[off:off + 4], struct.unpack_from("<I", b, off + 4)[0]
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", b, off + 8)
        if cid == b"data":
            assert fmt and fmt[0] == 1 and fmt[1] == 2 and fmt[2] == 44100 \
                and fmt[5] == 16, f"unexpected format {fmt} in {path}"
            return b[off + 8:off + 8 + sz]
        off += 8 + sz + (sz % 2)
    raise AssertionError("no data chunk")


def main():
    exe = open(os.path.join(SRC, "MAIN.EXE"), "rb").read()
    assert exe[:8] == b"PS-X EXE", "not a PS-X EXE"
    print(f"psexe: {len(exe)} bytes sha256={hashlib.sha256(exe).hexdigest()}")
    cnf = open(os.path.join(SRC, "SYSTEM.CNF"), "rb").read()

    # 11 data files, names exactly as cd_read_file() asks them
    data_files = [
        ("HOUSE1.TMD", "HOUSE1.TMD"), ("HOUSE1.TIM", "house1.tim"),
        ("HOUSE2.TMD", "HOUSE2.TMD"), ("HOUSE2.TIM", "house2.tim"),
        ("HOUSE3.TMD", "HOUSE3.TMD"), ("HOUSE3.TIM", "house3.tim"),
        ("HOUSE4.TMD", "HOUSE4.TMD"), ("HOUSE4.TIM", "house4.tim"),
        ("CHART.BIN", "BambiCSV.bin"),
        ("RIPPLE.TIM", "RIPPLE.TIM"), ("ARROWS.TIM", "arrows.tim"),
    ]
    files = [("SYSTEM.CNF", cnf), ("MAIN.EXE", exe)]
    for disc_name, src_name in data_files:
        files.append((disc_name, open(os.path.join(SRC, src_name), "rb").read()))

    bin_data, cue = iso9660_min.build_image(files)
    m = len(bin_data) // SEC
    print(f"data track: {m} sectors (volume space)")
    assert m <= DATA_END, f"data track too big: {m} > {DATA_END}"

    # license sectors from the user's own retail disc (local-only unblock)
    lic = open(MSX, "rb").read(16 * SEC)
    assert b"Sony Computer Entertainment" in lic, "MSX license not found"
    bin_data = bytearray(bin_data)
    bin_data[:16 * SEC] = lic

    # dummy pad -> track 02 INDEX 01 lands exactly on songLoc LBA
    for i in range(m, DATA_END):
        bin_data += iso9660_min.raw_mode2(i, b"\x00" * USER)
    print(f"padded data track to {DATA_END} sectors "
          f"({DATA_END - m} dummy sectors)")

    # audio tracks: 2 s silence pregap + PCM, zero-padded to sector size
    t2 = wav_pcm(os.path.join(SRC, "Bambi.wav"))
    t3 = wav_pcm(os.path.join(SRC, "untitled.wav"))
    bin_data += b"\x00" * (PREGAP * SEC)
    t2_lba, t3_lba = SONG_LBA, SONG_LBA + (len(t2) + SEC - 1) // SEC + PREGAP
    bin_data += t2 + b"\x00" * (-len(t2) % SEC)
    bin_data += b"\x00" * (PREGAP * SEC)
    bin_data += t3 + b"\x00" * (-len(t3) % SEC)
    bin_data = bytes(bin_data)

    cue = (f'FILE "{BIN_NAME}" BINARY\n'
           f"  TRACK 01 MODE2/2352\n"
           f"    INDEX 01 00:02:00\n"
           f"  TRACK 02 AUDIO\n"
           f"    INDEX 00 {msf(DATA_END)}\n"
           f"    INDEX 01 {msf(SONG_LBA)}\n"
           f"  TRACK 03 AUDIO\n"
           f"    INDEX 00 {msf(t3_lba - PREGAP)}\n"
           f"    INDEX 01 {msf(t3_lba)}\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    bin_path = os.path.join(OUT_DIR, BIN_NAME)
    with open(bin_path, "wb") as f:
        f.write(bin_data)
    with open(bin_path.replace(".bin", ".cue"), "w") as f:
        f.write(cue)
    print(f"wrote {bin_path}: {len(bin_data)} bytes "
          f"({len(bin_data) // SEC} sectors) "
          f"sha256={hashlib.sha256(bin_data).hexdigest()}")
    print(f"track02 INDEX01 @ LBA {SONG_LBA} = MSF {msf(SONG_LBA)} "
          f"(game songLoc 00:22:55 BCD)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

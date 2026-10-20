#!/usr/bin/env python3
"""iso9660_min.py — minimal pure-Python ISO9660 MODE2/2352 PS1 disc writer.

Why this exists: the previous padtest packer depended on the external
mkpsxiso binary under /tmp, which vanishes between sessions. This module
removes the external dependency so the lawful self-generated test disc is
reproducible with the standard library alone.

What it writes (single data track, exactly what the PS1 boot shell needs):

  sector 0..15   system area (zeros)
  sector 4       the region marker line ("Licensed by ... Ameri") that the
                 retail firmware's region detection (CalcDiscSCEx) reads;
                 the text is typed verbatim from public PS1 documentation
                 and carries zero Sony binary content
  sector 16      Primary Volume Descriptor
  sector 17      Volume Descriptor Set Terminator
  sector 18      L path table
  sector 19      M path table
  sector 20      root directory records (".", "..", files)
  sector 21..    file data, each file at a sector boundary

Every data sector is written as raw MODE2/2352 form1 with a correct EDC
(subheader + 2048 user bytes, CRC table poly 0xD8018001) because the
core's CDC layer validates EDC on data reads (mednafen/psx/cdc.c
edc_lec_check_and_correct). ECC fields are zero-filled; the CDC only
invokes ECC correction when the EDC check fails.

Zero third-party code, zero copyrighted content.
"""
import struct

RAW = 2352
USER = 2048
SYNC = bytes([0x00] + [0xFF] * 10 + [0x00])

# Region marker line for NTSC-U detection. The core's region autodetect
# (libretro.c CalcDiscSCEx) strips non-printable characters from sector 4,
# lowercases the remainder and searches for "licensedby" plus a region
# keyword ("america" -> REGION_NA). The line below is public documentation
# text written for that detector; it carries zero Sony binary content.
LICENSE_TEXT = (b"          Licensed  by          "
                b"Sony Computer Entertainment America ")
assert len(LICENSE_TEXT) == 68

VOL_ID = b"PADTEST"
SYS_ID = b"PLAYSTATION"
PUBLISHER = b"PS1PLAY-SELFTEST"


def _edc_table():
    """CRC table for the CD-ROM LEC EDC (reflected poly 0xD8018001)."""
    tab = []
    for i in range(256):
        edc = i
        for _ in range(8):
            edc = (edc >> 1) ^ 0xD8018001 if edc & 1 else edc >> 1
        tab.append(edc)
    return tab


_EDC_TAB = _edc_table()


def edc_calc(data):
    """LEC EDC of a byte string (e.g. the 2052-byte subheader+data span)."""
    edc = 0
    tab = _EDC_TAB
    for b in data:
        edc = (edc >> 8) ^ tab[(edc ^ b) & 0xFF]
    return edc & 0xFFFFFFFF


def _bcd(v):
    return ((v // 10) << 4) | (v % 10)


def raw_mode2(lba, user):
    """One raw MODE2/2352 form1 sector from 2048 user bytes.

    Layout (verified against mednafen CDAccess_PBP fix_sector and the
    cdc.c EDC check): sync 12 | header 4 | subheader 8 (4 + identical
    repeat) | user 2048 | EDC 4 at 0x818 (CRC over 0x10..0x817, i.e.
    subheader + user = 2056 bytes) | ECC 276 (zero-filled).
    """
    assert len(user) == USER
    m, s, f = lba // (75 * 60), (lba // 75) % 60, lba % 75
    head = SYNC + bytes([_bcd(m), _bcd(s), _bcd(f), 0x02])
    sub = bytes([0x00, 0x00, 0x08, 0x00]) * 2     # data, form1 (repeated)
    body = head + sub + user                      # 16 + 8 + 2048 = 0x818
    edc = edc_calc(body[0x10:0x818])              # subheader + user data
    raw = body + struct.pack("<I", edc) + b"\x00" * 276
    assert len(raw) == RAW
    return raw


def _both32(x):
    """LE+BE pair as ISO9660 stores both-endian u32 values."""
    return struct.pack("<I", x) + struct.pack(">I", x)


def _both16(x):
    return struct.pack("<H", x) + struct.pack(">H", x)


def _spad(s, n):
    assert len(s) <= n, (s, n)
    return s + b" " * (n - len(s))


def _dir_record(name, extent, size, flags):
    """One ISO9660 directory record, padded to an even length."""
    date = bytes([124, 1, 1, 0, 0, 0, 0])          # 2024-01-01 00:00:00
    rec = struct.pack("<B", 0)                      # placeholder for length
    rec = bytes([0]) + bytes([0]) + _both32(extent) + _both32(size) + date
    rec += bytes([flags, 0, 0]) + _both16(1)
    rec += bytes([len(name)]) + name
    if len(rec) % 2:
        rec += b"\x00"
    rec = bytes([len(rec)]) + rec[1:]
    return rec


def _pvd(space_size, pt_size, lpt_lba, root_lba, root_size):
    d = bytearray(USER)
    d[0] = 0x01
    d[1:6] = b"CD001"
    d[6] = 0x01                                     # version
    d[8:40] = _spad(SYS_ID, 32)
    d[40:72] = _spad(VOL_ID, 32)
    d[80:88] = _both32(space_size)
    d[120:124] = _both16(1)                         # volume set size = 1
    d[124:128] = _both16(1)                         # volume seq = 1
    d[128:132] = _both16(USER)                      # logical block size
    d[132:140] = _both32(pt_size)                   # path table size (both-endian 32)
    d[140:144] = struct.pack("<I", lpt_lba)         # L path table location
    d[144:148] = struct.pack("<I", lpt_lba)         # optional L (reuse)
    d[148:152] = struct.pack(">I", lpt_lba + 1)     # M path table location
    d[152:156] = struct.pack(">I", lpt_lba + 1)     # optional M (reuse)
    root = _dir_record(b"\x00", root_lba, USER, 0x02)
    assert len(root) == 34
    d[156:190] = root
    d[190:318] = b"\x00" * 128                      # root dir name field
    d[318:446] = _spad(VOL_ID, 128)                 # volume set id
    d[446:574] = _spad(PUBLISHER, 128)              # publisher
    d[574:702] = _spad(PUBLISHER, 128)              # data preparer
    d[702:830] = _spad(PUBLISHER, 128)              # application
    date = b"2024010100000000\x00"
    d[813:830] = date                               # volume creation date
    d[830:847] = date                               # modification
    d[847:864] = date                               # expiration
    d[864:881] = date                               # effective
    d[881] = 0x01                                   # file structure version
    return bytes(d)


def _path_table_entry(extent, big_endian):
    """Root path table entry: name is the single 0x00 byte."""
    name = b"\x00"
    if big_endian:
        body = struct.pack(">I", extent) + struct.pack(">H", 1) + name
    else:
        body = struct.pack("<I", extent) + struct.pack("<H", 1) + name
    ent = bytes([len(name), 0]) + body
    if len(ent) % 2:
        ent += b"\x00"
    return ent


def build_image(files, license_text=LICENSE_TEXT):
    """files: list of (name_on_disc, content_bytes). Returns (bin, cue).

    Layout is deterministic; the EXE must be the LAST file so its extent
    is stable if SYSTEM.CNF changes size.
    """
    lba = 22                                        # 0..21 fixed layout
    entries = []
    for name, data in files:
        sectors = (len(data) + USER - 1) // USER
        entries.append((name, data, lba, sectors))
        lba += sectors
    space = lba

    # ---- user-data plane ---------------------------------------------
    plane = {}

    def put(lba_, user):
        """Write user bytes across consecutive sectors (zero-padded tail)."""
        n = (len(user) + USER - 1) // USER
        for k in range(n):
            chunk = user[k * USER:(k + 1) * USER]
            buf = bytearray(USER)
            buf[:len(chunk)] = chunk
            plane[lba_ + k] = bytes(buf)

    put(4, license_text)                            # region marker
    plane[16] = _pvd(space, 10, 18, 20, USER)
    plane[17] = b"\xFF" * USER
    lpt = _path_table_entry(20, False)
    mpt = _path_table_entry(20, True)
    assert len(lpt) == len(mpt) == 10
    plane[18] = lpt + b"\x00" * (USER - len(lpt))
    plane[19] = mpt + b"\x00" * (USER - len(mpt))
    root = bytearray()
    root += _dir_record(b"\x00", 20, USER, 0x02)    # "."
    root += _dir_record(b"\x01", 20, USER, 0x02)    # ".."
    for name, data, ext, _sec in entries:
        disc_name = name.upper().encode() + b";1"
        root += _dir_record(disc_name, ext, len(data), 0x00)
    plane[20] = bytes(root.ljust(USER, b"\x00"))
    for name, data, ext, _sec in entries:
        put(ext, data)

    # ---- raw sector plane ---------------------------------------------
    out = bytearray()
    for i in range(space):
        out += raw_mode2(i, plane.get(i, b"\x00" * USER))

    cue = (f'FILE "image.bin" BINARY\n'
           f"  TRACK 01 MODE2/2352\n"
           f"    INDEX 01 00:02:00\n")
    return bytes(out), cue


def _root_dir_size(entries):
    """Kept for API stability: a one-sector directory record area."""
    return USER


def parse_dir_sector(user):
    """Tiny read-back parser used by tests: [(name, extent, size, flags)]."""
    out = []
    off = 0
    while off < len(user) and user[off]:
        ln = user[off]
        rec = user[off:off + ln]
        extent = struct.unpack_from("<I", rec, 2)[0]
        size = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        nlen = rec[32]
        name = rec[33:33 + nlen]
        out.append((name.decode(), extent, size, flags))
        off += ln
    return out

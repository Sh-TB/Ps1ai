"""Memory tools: live views, digests, structural diff — 100% observe-only."""
import hashlib
import numpy as np


def digest(arr, n=8):
    """Compact digest of a memory snapshot (token-cheap identity)."""
    return hashlib.blake2b(arr.tobytes(), digest_size=n).hexdigest()[:16]


def as_u16(u8):
    return np.frombuffer(u8.tobytes() if not isinstance(u8, np.ndarray) else u8,
                         dtype="<u2") if False else u8.view("<u2")


def as_u32(u8):
    return u8.view("<u4")


def diff_regions(prev, cur, max_len_gap=4, top=24):
    """Byte-level diff -> merged contiguous regions.

    Returns dict: {bytes_changed, regions:[(start,end,count)]} sorted by count.
    """
    if prev is None or len(prev) != len(cur):
        return {"bytes_changed": -1, "regions": []}
    changed = np.flatnonzero(prev != cur)
    if changed.size == 0:
        return {"bytes_changed": 0, "regions": []}
    # split where gap > max_len_gap, then merge tiny neighbors
    gaps = np.flatnonzero(np.diff(changed) > max_len_gap)
    starts = np.concatenate(([0], gaps + 1))
    ends = np.concatenate((gaps, [changed.size - 1]))
    regions = []
    for s, e in zip(starts, ends):
        a, b = int(changed[s]), int(changed[e])
        regions.append((a, b + 1, e - s + 1))
    regions.sort(key=lambda r: -r[2])
    return {"bytes_changed": int(changed.size), "regions": regions[:top]}


class MemoryView:
    """Convenience reader over the live RAM array (little-endian PS1)."""

    def __init__(self, ram: np.ndarray):
        self.ram = ram

    def __len__(self):
        return len(self.ram)

    def snapshot(self):
        return self.ram.copy()

    def u8(self, addr):
        return int(self.ram[addr])

    def u16(self, addr):
        # int() casts BEFORE shifting: numpy uint8 << 8 wraps to 0,
        # which silently truncated every u16 read to its low byte.
        return int(self.ram[addr]) | (int(self.ram[addr + 1]) << 8)

    def u32(self, addr):
        return (int(self.ram[addr]) | (int(self.ram[addr + 1]) << 8)
                | (int(self.ram[addr + 2]) << 16)
                | (int(self.ram[addr + 3]) << 24))

    def hexdump(self, addr, n=32, width=16):
        rows = []
        for off in range(0, n, width):
            chunk = self.ram[addr + off:addr + off + width]
            rows.append(f"{addr + off:06X}: "
                        + bytes(bytearray(chunk)).hex(" "))
        return "\n".join(rows)

    def stats(self):
        nz = int(np.count_nonzero(self.ram))
        return {"size": int(len(self.ram)), "nonzero": nz,
                "digest": digest(self.ram)}

#!/usr/bin/env python3
"""psxmc_r10_lib.py — shared helpers for PSX-Minecraft round 10 (place7).

Round-9 mandatory instrument fixes implemented here:

FIX-1  bit-exact stability gate usable IMMEDIATELY BEFORE EACH attempt
       (stability_gate: last N grabs bit-exact, or a logged unstable-world
       fallback with a matched no-input drift-control window).

FIX-2  the R2 breaking-state raycast oracle is parsed from SNAPSHOTS TAKEN
       WHILE STILL HOLDING R2 (the r9 probe read live RAM after release; the
       chunk-mesh reset path zeroes the state, so r9 saw nothing).  Helpers:
       breaking_candidates / parse_breaking_from_snap.

New in round 10 (all source-derived, upstream clone @ infdev_2025_04_18):
  * full in-world block read: World struct walk (world.c worldGetBlock
    mirrored in Python) -> chunk -> blocks[chunkBlockIndex] -> Block.id.
  * hotbar chain read (Hotbar.ui/Slot/Item layout) as an independent
    stack sensor + inventory.ui.active UI detector.

Conventions carried over from psxmc_r7_lib: one beetle boot per process,
honest verdict vocabulary, madiff/changed_px evidence helpers.
"""
import hashlib

import numpy as np

# ---- game constants (upstream source, infdev_2025_04_18) -------------------
PITCH_MOD = 1 << 24
DEG = PITCH_MOD / 360.0
ONE_BLOCK = 286720          # ONE * BLOCK_SIZE
ONE = 4096                  # FIXED_POINT_SHIFT 12
CHUNK_SIZE = 8              # chunk_defines.h
WORLD_HEIGHT = 8            # WORLD_CHUNKS_HEIGHT(1) * CHUNK_SIZE
LOADED_CHUNKS_RADIUS = 2    # world_defines.h
SHIFT_ZONE = 1
AXIS_CHUNKS = ((LOADED_CHUNKS_RADIUS + SHIFT_ZONE) * 2) + 1   # = 7
PLAYER_REACH = 6.0          # player.h:27
CAMERA_OFFSET_B = 1.7       # PLAYER_CAMERA_OFFSET 487424 / ONE_BLOCK
Y_OFFSET_B = 1.62           # player_physics_object_config.y_offset
ITEMID_CRAFTING_TABLE = 58
BLOCKID = {"AIR": 0, "STONE": 1, "GRASS": 2, "DIRT": 3, "COBBLESTONE": 4,
           "CRAFTING_TABLE": 58}
DIG_TICKS_BUDGET = 15       # grass ~18 / dirt ~15 ticks by hand (r10 calc)

A_PLAYER = 0x3C608          # map symbol `player` (live-verified r3)
A_WORLD = 0x3C61C           # map symbol `world`
A_INPUT = 0x3C73C
STACK_ADDR = 0x7CDA0        # live-verified r7 stack_size of selected item
HEAP_LO, HEAP_HI = 0x10000, 0x1F8000

HUD_BAND = (56, 208, 264, 240)      # x0,y0,x1,y1 hotbar band (place4)
SKY_ROWS = 78                       # above this row: sky band (clouds)


def s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def ring_diff(a, b):
    """Signed shortest difference b-a on the 2^24 rotation ring."""
    return (b - a + (PITCH_MOD >> 1)) % PITCH_MOD - (PITCH_MOD >> 1)


def pos_mod(v, m):
    return int(v) % m


def floor_div(v, m):
    return int(np.floor_divide(int(v), m))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def is_heap(v):
    return (v & 3) == 0 and HEAP_LO < (v & 0x1FFFFF) < HEAP_HI


def phys(v):
    """KUSEG virtual -> beetle 2MB RAM physical offset."""
    return v & 0x1FFFFF


# ---------------- memory-backed struct readers ------------------------------
class WorldReader:
    """Mirror of world.c worldGetBlock: World* -> chunks[az][ax][0] ->
    Chunk -> blocks[chunkBlockIndex(x,y,z)] -> Block.id (@+0).

    Round-10 static ground truth (capstone disasm of the FIXED
    infdev_2025_04_18 binary, worldGetChunkBlock @0x80025ab0 /
    chunkGetBlock @0x8001c120 — see scripts/psxmc_disasm_offsets.py):
      chunks[] base = World + 0x3144, index ax + 7*az (ax innermost),
        entries are Chunk* and MAY BE NULL (unloaded chunks — the r10
        '49 consecutive heap pointers' runtime scan failed exactly
        because a 5x5-loaded window inside the 7x7 array breaks the
        run);
      blocks[] base = Chunk + 0x8C, index x + 8*z + 64*y (x innermost:
        disasm ((y*8+z)*8+x), NOT the x-outermost guess), entries are
        IBlock*, NULL => air.
    The runtime pointer-run scan is kept only as a fallback.
    """

    STATIC_CHUNKS_OFF = 0x3144
    STATIC_BLOCKS_OFF = 0x8C

    def __init__(self, mem, world_sym=A_WORLD):
        self.m = mem
        self.world_sym = world_sym
        self.W = None
        self.chunks_off = None
        self.blocks_off = None
        self.centre = None
        self.head = None

    def _u32(self, a):
        return self.m.u32(phys(a))

    def _u8(self, a):
        return self.m.u8(phys(a))

    def discover(self, scan_span=0x4000):
        W = phys(self._u32(self.world_sym))
        if not is_heap(W):
            raise RuntimeError(f"world ptr invalid: {hex(W)}")
        self.W = W
        self.centre = [s32(self._u32(W)), s32(self._u32(W + 4)),
                       s32(self._u32(W + 8))]
        self.head = [self._u32(W + 24), self._u32(W + 28)]
        # static disasm offsets (NULL-tolerant by construction)
        self.chunks_off = self.STATIC_CHUNKS_OFF
        self.blocks_off = self.STATIC_BLOCKS_OFF
        self.offset_source = "static-disasm"
        chunk0 = None
        # the player's chunk is the WINDOW CENTRE (ax=az=3 -> idx 24),
        # NOT slot 0: unloaded-behind slots legitimately read NULL.
        # (r10 fix v2: probing only slot 0 mis-triggered the fallback,
        # whose window landed at 0x32A8 and read AIR below the feet.)
        for probe_idx in (24, 0):
            try:
                c0 = phys(self._u32(W + self.chunks_off + 4 * probe_idx))
                if is_heap(c0):
                    chunk0 = c0
                    self.center_idx = probe_idx
                    break
            except Exception:                      # noqa: BLE001
                pass
        if chunk0 is None:
            # fallback: NULL-tolerant scan (majority-heap window)
            buf = bytes(self.m.snapshot()[W:W + scan_span])
            words = np.frombuffer(buf, "<u4")
            self.chunks_off = self._find_ptr_run_nulltol(
                words, AXIS_CHUNKS * AXIS_CHUNKS)
            self.offset_source = "runtime-scan"
        return {"world": hex(W), "centre": self.centre, "head": self.head,
                "chunks_off": self.chunks_off, "blocks_off": self.blocks_off,
                "chunk0": hex(chunk0) if chunk0 else None,
                "offset_source": self.offset_source}

    @staticmethod
    def _find_ptr_run_nulltol(words, need, tol=4):
        """First offset whose `need`-word window has >= need-tol heap
        pointers (unloaded chunk slots are NULL)."""
        ok = np.zeros(len(words), bool)
        for i, w in enumerate(words):
            v = int(w)
            ok[i] = (v & 3) == 0 and HEAP_LO < (v & 0x1FFFFF) < HEAP_HI
        run = 0
        for i in range(len(words)):
            run = run + 1 if ok[i] else 0
            if run >= need - tol:
                return (i - (need - tol) + 1) * 4
        raise RuntimeError("no pointer run found (null-tolerant)")

    @staticmethod
    def _find_ptr_run(words, need):
        """First offset where `need` consecutive words are heap pointers."""
        ok = np.zeros(len(words), bool)
        for i, w in enumerate(words):
            v = int(w)
            ok[i] = (v & 3) == 0 and HEAP_LO < (v & 0x1FFFFF) < HEAP_HI
        run = 0
        for i in range(len(words)):
            run = run + 1 if ok[i] else 0
            if run >= need:
                return (i - need + 1) * 4
        raise RuntimeError("no pointer run found")

    def _array_coord(self, axis, value, is_x=True):
        head = self.head[0] if is_x else self.head[1]
        centre = self.centre[0] if is_x else self.centre[2]
        return pos_mod(int(head) + (int(value) - (centre - LOADED_CHUNKS_RADIUS
                                                  - SHIFT_ZONE)), AXIS_CHUNKS)

    def chunk_ptr(self, cx, cy, cz):
        ax = self._array_coord(0, cx, is_x=True)
        az = self._array_coord(2, cz, is_x=False)
        base = self.W + self.chunks_off + 4 * ((az * AXIS_CHUNKS) + ax)
        return self._u32(base), ax, az

    def block_addr(self, bx, by, bz):
        """RAM address of the IBlock* slot for world block (bx,by,bz), or
        None when the walk fails (out of world / unloaded)."""
        if not (0 <= by < WORLD_HEIGHT):
            return None
        cx, cy, cz = (floor_div(bx, CHUNK_SIZE), floor_div(by, CHUNK_SIZE),
                      floor_div(bz, CHUNK_SIZE))
        if cy != 0:
            return None
        C, _, _ = self.chunk_ptr(cx, cy, cz)
        C = phys(C)
        if not is_heap(C):
            return None
        lx, ly, lz = (pos_mod(bx, CHUNK_SIZE), pos_mod(by, CHUNK_SIZE),
                      pos_mod(bz, CHUNK_SIZE))
        # disasm chunkGetBlock @0x8001c120: idx = ((y*8+z)*8+x)
        # (x innermost); entry = Chunk + 0x8C + 4*idx, value = IBlock*
        idx = lx + CHUNK_SIZE * lz + ly * CHUNK_SIZE * CHUNK_SIZE
        return C + self.blocks_off + 4 * idx

    def block_id(self, bx, by, bz):
        """BlockID at world cell, or None (outside/unknown).

        Static ABI (callers of worldGetBlock, e.g. 0x80013014):
          p = *(u32*)(IBlock+0)   # pointer to the embedded Block struct
          id = *(u8*)p            # Block.id, u8 (block.h)
        """
        a = self.block_addr(bx, by, bz)
        if a is None:
            return None
        bp = phys(self._u32(a))
        if not is_heap(bp):
            return BLOCKID["AIR"]          # NULL IBlock* => treated as air
        blk = phys(self._u32(bp))          # IBlock+0 -> Block* (u32)
        return self._u8(blk)               # Block.id (u8)


def camera_world_y(pos_vy_raw):
    """Raycast-space camera Y in blocks (world_raycast.c origin[1] =
    -camera.position.vy / ONE_BLOCK with camera.vy = -(feet) - 1.7*ONE_BLOCK;
    feet = position.vy - y_offset 1.62)."""
    feet = s32(pos_vy_raw) / ONE_BLOCK - Y_OFFSET_B
    return feet + CAMERA_OFFSET_B, feet


def expected_surface_y(bx, bz):
    """Flatland generator: grass y==4, bump grass y==5 at x%3==0&&z%3==0."""
    return 5 if (bx % 3 == 0 and bz % 3 == 0) else 4


# ---------------- FIX-2 oracle: breaking-state parsing ----------------------
def breaking_candidates(snap_hold, snap_base, P, cam_y_blocks,
                        pos_blocks, search=0x400):
    """Diff a WHILE-HOLDING-R2 snapshot against the pre-probe snapshot.

    The BreakingState (player.c:134) latches raycast hit: position VECTOR
    (block coords) + IBlock* block; the r9 defect was reading AFTER release
    (chunk-mesh reset zeroes it).  Candidate = i32-triple K in the player
    window that changed vs base, is plausible (small box, at/below the
    camera), with a heap pointer at K+12..K+20, and nonzero block ptr.
    Returns list of dicts (offsets relative to P).
    """
    a = np.frombuffer(snap_hold, "<i4")
    b = np.frombuffer(snap_base, "<i4")
    aw = np.frombuffer(snap_hold, "<u4")
    lo, hi = P >> 2, min((P + search) >> 2, len(a) - 6)
    pxb = pos_blocks[0] / ONE_BLOCK
    pyb = pos_blocks[1] / ONE_BLOCK
    pzb = pos_blocks[2] / ONE_BLOCK
    out = []
    for i in range(lo, hi):
        x, y, z = int(a[i]), int(a[i + 1]), int(a[i + 2])
        if (x, y, z) == (int(b[i]), int(b[i + 1]), int(b[i + 2])):
            continue
        if not (-32 <= x <= 32 and -1 <= y <= 48 and -32 <= z <= 32):
            continue
        if y > cam_y_blocks + 1:
            continue                      # raycast hits AT/below the camera
        ptr = None
        for pk in range(i + 3, i + 6):    # ptr within K+12..K+20
            if pk < len(aw) and is_heap(int(aw[pk])):
                ptr = pk * 4
                break
        if ptr is None:
            continue
        out.append({"off": i * 4 - P, "ptr_off": ptr - P,
                    "hit": [x, y, z],
                    "dxy": [round(x - pxb, 2), round(z - pzb, 2)],
                    "below_cam": y <= cam_y_blocks})
    # collapse word-slide duplicates: same pointer slot + overlapping triple
    # => keep the best-ranked representative (canonical layout: ptr at +16,
    # tick counter nonzero at K-4, non-zero hit coords)
    def rank(c):
        ticks = int(aw[(P + c["off"] - 4) >> 2]) if c["off"] >= 4 else 0
        return (abs(c["ptr_off"] - c["off"] - 16), 0 if ticks else 1,
                0 if c["hit"] != [0, 0, 0] else 1, c["off"])
    groups = {}
    for c in out:
        groups.setdefault(c["ptr_off"], []).append(c)
    dedup = [min(g, key=rank) for g in groups.values()]
    dedup.sort(key=rank)
    return dedup


def parse_breaking_from_snap(snap, P, off, ptr_off):
    a = np.frombuffer(snap, "<i4")
    aw = np.frombuffer(snap, "<u4")
    i = (P + off) >> 2
    return ([int(a[i]), int(a[i + 1]), int(a[i + 2])], int(aw[(P + ptr_off) >> 2]))


def hit_geometry(hit, pos_blocks, cam_y):
    """Euclidean t (reach check) + relative direction of a raycast hit."""
    if not hit:
        return None
    pxb, pyb, pzb = [v / ONE_BLOCK for v in pos_blocks]
    t = ((hit[0] + 0.5 - pxb) ** 2 + (hit[1] + 0.5 - cam_y) ** 2 +
         (hit[2] + 0.5 - pzb) ** 2) ** 0.5
    return {"t": round(t, 2), "in_reach": bool(t <= PLAYER_REACH),
            "dx": hit[0] - int(np.floor(pxb)),
            "dz": hit[2] - int(np.floor(pzb))}


def validate_known_hit(hit, pos_blocks, cam_y, max_lateral=1):
    """FIX-2 known-hit config: straight-down aim must report a hit in the
    player's own column, at/below the camera, within reach."""
    if not hit or hit == [0, 0, 0]:
        return False, "no hit"
    g = hit_geometry(hit, pos_blocks, cam_y)
    if abs(g["dx"]) > max_lateral or abs(g["dz"]) > max_lateral:
        return False, f"not in player column dx={g['dx']} dz={g['dz']}"
    if hit[1] > cam_y:
        return False, "hit above camera"
    if not g["in_reach"]:
        return False, f"out of reach t={g['t']}"
    return True, g


# ---------------- hotbar chain (independent stack + UI sensors) -------------
def find_hotbar(m, P, expect_item=ITEMID_CRAFTING_TABLE, search=0x40):
    """Locate Player -> IUI hotbar (.self) by chain validation:
    H+8 in {0,1} (ui.active), H+28+8*sel item ptr chain resolves to an Item
    with Item.id == expect_item.  Returns dict or None."""
    for off in range(0x40, 0x40 + search, 4):
        H = phys(m.u32(P + off))
        if not is_heap(H):
            continue
        active = m.u8(H + 8)
        if active not in (0, 1):
            continue
        sel = m.u8(H + 100)
        if sel > 8:
            continue
        d = phys(m.u32(H + 28 + 8 * sel))
        item = d
        via = "item"
        if is_heap(d):
            if m.u32(item) != expect_item:
                # Slot.data.ref: pointer to a Slot whose .data is the item
                r = phys(m.u32(d))
                if is_heap(r) and m.u32(r) == expect_item:
                    item, via = r, "ref"
                else:
                    continue
        else:
            continue
        stack = m.u8(item + 12)
        return {"hotbar_off": off, "hotbar": H, "active": bool(active),
                "selected": sel, "item": item, "via": via,
                "item_id": m.u32(item), "stack": stack,
                "stack_addr": item + 12,
                "inv_active_addr": None}
    return None


def find_inventory(m, P, hotbar_off):
    """The OTHER IUI pointer near the hotbar one = Player.inventory;
    ui.active @ Inv+8 detects the START-toggled inventory UI."""
    for off in range(max(0x40, hotbar_off - 0x14), hotbar_off + 0x1C, 4):
        if off == hotbar_off:
            continue
        I = phys(m.u32(P + off))
        if is_heap(I) and m.u8(I + 8) in (0, 1):
            return {"inv_off": off, "inv": I, "active_addr": I + 8,
                    "active": bool(m.u8(I + 8))}
    return None


# ---------------- FIX-1: bit-exact stability gate ---------------------------
class StabilityGate:
    """Require the last N consecutive grabs to be bit-exact (frame hash
    equality) immediately before an attempt; abort+retry otherwise.

    In a world that never settles (mobs/clouds) the gate reports ok=False
    after max_wait; the caller then records the attempt as UNSTABLE and may
    still proceed using the matched no-input drift control.
    """

    def __init__(self, run_fn, grab_fn, n=4, max_wait=240):
        self.run_fn = run_fn            # run_fn(frames) — idle frames
        self.grab_fn = grab_fn          # grab_fn() -> HxWx3 uint8
        self.n = n
        self.max_wait = max_wait

    def check(self, settle=1):
        """Returns (ok, frames_waited, n_stable)."""
        self.run_fn(settle)
        last = sha(self.grab_fn().tobytes())
        waited = settle
        streak = 1
        while waited < self.max_wait:
            if streak >= self.n:
                return True, waited, streak
            self.run_fn(1)
            waited += 1
            h = sha(self.grab_fn().tobytes())
            streak = streak + 1 if h == last else 1
            last = h
        return bool(streak >= self.n), waited, streak


# ---------------- pixel metrics with band split -----------------------------
def diff_bands(a, b):
    """Changed-pixel metrics split into sky / horizon-ground / HUD bands so
    cloud drift (sky) can be separated from world edits (ground)."""
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    mask = d > 2
    h = mask.shape[0]
    hud = np.zeros_like(mask)
    hud[HUD_BAND[1]:HUD_BAND[3], HUD_BAND[0]:HUD_BAND[2]] = True
    sky = np.zeros_like(mask)
    sky[:min(SKY_ROWS, h), :] = True
    world = mask & ~hud
    return {"changed_px": int(mask.sum()),
            "sky_px": int((world & sky).sum()),
            "ground_px": int((world & ~sky).sum()),
            "hud_px": int((mask & hud).sum()),
            "world_px": int(world.sum()),
            "max_d": int(d.max())}


def stack_scan(pre, post, pairs=((26, 25), (25, 24), (24, 23), (23, 22),
                                 (22, 21), (21, 20), (10, 9))):
    """r7/r9 byte-pair scan around a USE tap (ItemID-58 context check)."""
    a = np.frombuffer(pre, np.uint8)
    b = np.frombuffer(post, np.uint8)
    hits = []
    for va, vb in pairs:
        for i in np.nonzero((a == va) & (b == vb))[0]:
            i = int(i)
            if i < 16:
                continue
            ids = [int(np.frombuffer(pre[i - d:i - d + 4], "<u4")[0])
                   for d in range(4, 13) if i - d >= 0]
            rec = {"addr": hex(i), "before": va, "after": vb,
                   "itemid_ctx": ITEMID_CRAFTING_TABLE in ids,
                   "is_stack_addr": i == STACK_ADDR}
            if rec["itemid_ctx"]:
                hits.append(rec)
    return hits

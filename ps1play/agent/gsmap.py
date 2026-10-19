"""GSMap — published GameShark/Pro Action Replay knowledge, READ-ONLY.

Source: gamehacking.org/game/89284 (Metal Slug X, NTSC-U, SLUS-01212).
GameShark PSX addresses are KUSEG virtual (0x80000000+); the physical RAM
offset we read is (addr & 0x1FFFFF) — identical to the raw codes here since
they are all < 0x200000.

WE NEVER WRITE THESE ADDRESSES. The codes tell us *where* game state lives
so the agent can read hp/ammo/lives like a human reads the HUD — with ZERO
LLM tokens. Each entry is validated live by verify_map.py before use.
"""

# role: physical address, dtype, notes
GS_SEEDS = {
    "score":    {"addr": 0x0EE318, "dtype": "u32",
                 "note": "Max Score P1 code (99999999) -> score u32"},
    "score_p2": {"addr": 0x0EE320, "dtype": "u32",
                 "note": "Max Score P2"},
    "hp":       {"addr": 0x032764, "dtype": "u16",
                 "note": "Invincible 00C8=200 -> full P1 HP, scale 0..200"},
    "bombs":    {"addr": 0x0398B4, "dtype": "u16",
                 "note": "Extra Bombs 0001 -> grenade count"},
    "lives":    {"addr": 0x0475A8, "dtype": "u16",
                 "note": "Extra Lives 0001 -> P1 life count"},
    "ammo":     {"addr": 0x02DCD8, "dtype": "u16",
                 "note": "Extra Arms Ammo 0001; infinite-ammo NOP @0x2DCE6"},
    "weapon":   {"addr": 0x02D92C, "dtype": "u16",
                 "note": "Weapon Modifier info -> current weapon id"},
    "timer":    {"addr": 0x0295F8, "dtype": "u16",
                 "note": "Extra/Infinite Time -> mission timer"},
    "pow":      {"addr": 0x087A78, "dtype": "u16",
                 "note": "Tons of Prisoners Saved P1"},
    "mission":  {"addr": 0x0D4213, "dtype": "u8",
                 "note": "Unlock Another Mission 300D4213 00FF -> stage byte"},
    "pad_mirror": {"addr": 0x0D4948, "dtype": "u16",
                   "note": "Rapid-fire joker D00D4948 8000 -> P1 pad bits "
                           "(bit15 = SQUARE = fire) mirrored in RAM"},
}

# 'Hit Anywhere' codes write masks into repeated slots -> entity tables
ENTITY_REGIONS = [
    (0x085200, 0x085A00, "hit-anywhere blocks 0x852D8/0x85700/0x085870"),
    (0x03F000, 0x042000, "0x0401F4/F6 hit fields"),
    (0x0E7000, 0x0E9000, "player_x discovery zone (ps1play v0.1)"),
]

# libretro joypad ids -> PSX pad bit in the 0x0D4948 mirror (active-high):
# bit15=SQUARE(Y) bit13=CIRCLE(A) bit14=CROSS(B) bit12=TRIANGLE(X)
# bit7=LEFT bit5=RIGHT bit6=DOWN bit4=UP bit3=START
PAD_BIT = {"Y": 15, "A": 13, "B": 14, "X": 12,
           "LEFT": 7, "RIGHT": 5, "DOWN": 6, "UP": 4, "START": 3}


def phys(addr):
    """GameShark virtual -> physical RAM offset."""
    return addr & 0x1FFFFF


def seeds_for_profile():
    return {role: {"addr": phys(s["addr"]), "dtype": s["dtype"],
                   "note": s["note"]}
            for role, s in GS_SEEDS.items()}

"""Controller constants + input parsing (PSX digital pad via libretro joypad)."""

JP_B, JP_Y, JP_SELECT, JP_START = 0, 1, 2, 3
JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT = 4, 5, 6, 7
JP_A, JP_X, JP_L, JP_R = 8, 9, 10, 11
JP_L2, JP_R2, JP_L3, JP_R3 = 12, 13, 14, 15

BTN_NAMES = {
    JP_B: "B", JP_Y: "Y", JP_SELECT: "SELECT", JP_START: "START",
    JP_UP: "UP", JP_DOWN: "DOWN", JP_LEFT: "LEFT", JP_RIGHT: "RIGHT",
    JP_A: "A", JP_X: "X", JP_L: "L1", JP_R: "R1",
    JP_L2: "L2", JP_R2: "R2", JP_L3: "L3", JP_R3: "R3",
}
NAME_TO_BTN = {v: k for k, v in BTN_NAMES.items()}
NAME_TO_BTN.update({"X": JP_X, "O": JP_A, "SQ": JP_Y, "TR": JP_X})


def parse_buttons(spec):
    """'START+RIGHT' -> {JP_START, JP_RIGHT}; also accepts a set of ids,
    a set of NAMES ({"START","RIGHT"}), or an int."""
    if isinstance(spec, int):
        return {spec}
    if isinstance(spec, (set, frozenset)):
        out = set()
        for item in spec:
            if isinstance(item, int):
                out.add(item)
            else:
                out |= parse_buttons(item)   # name strings -> ids
        return out
    if not spec:
        return set()
    out = set()
    for token in str(spec).replace(" ", "").split("+"):
        if not token:
            continue
        up = token.upper()
        if up not in NAME_TO_BTN:
            raise ValueError(f"unknown button: {token}")
        out.add(NAME_TO_BTN[up])
    return out

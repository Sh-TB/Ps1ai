"""ThumbNav — screen-state recognition from tiny thumbnails (64x48 gray).

This is the 'learn the menus ONCE' phase of the framework: reference
thumbnails of each menu screen are captured during the first (learning)
run and labeled once. Afterwards the navigator plays the menus with ZERO
tokens: match the current screen to a reference, press the mapped button.

The matching is plain numpy (mean absolute difference) — no LLM, no
pixels ever leave the process. Works for any game given its own refs dir.
"""
import os
import numpy as np
from PIL import Image

THUMB = (64, 48)


def to_thumb(rgb):
    """frame_rgb() HxWx3 -> 48x64 gray float32."""
    im = Image.fromarray(rgb).convert("L").resize(THUMB)
    return np.asarray(im, dtype=np.float32)


def load_refs(refs_dir):
    """refs_dir/<state>__*.png -> {state: [thumb, ...]}"""
    refs = {}
    if not os.path.isdir(refs_dir):
        return refs
    for fn in sorted(os.listdir(refs_dir)):
        if not fn.endswith(".png"):
            continue
        state = fn.split("__")[0]
        arr = np.asarray(Image.open(os.path.join(refs_dir, fn))
                         .convert("L").resize(THUMB), dtype=np.float32)
        refs.setdefault(state, []).append(arr)
    return refs


def save_ref(rgb, refs_dir, state, tag):
    os.makedirs(refs_dir, exist_ok=True)
    im = Image.fromarray(rgb).convert("L").resize(THUMB)
    im.save(os.path.join(refs_dir, f"{state}__{tag}.png"))


class ThumbNav:
    def __init__(self, refs, unknown_thresh=34.0):
        self.refs = refs
        self.unknown_thresh = unknown_thresh

    def classify(self, thumb):
        best, bd = "unknown", None
        for state, thumbs in self.refs.items():
            for ref in thumbs:
                d = float(np.mean(np.abs(ref - thumb)))
                if bd is None or d < bd:
                    best, bd = state, d
        if bd is None or bd > self.unknown_thresh:
            return "unknown", (bd if bd is not None else 999.0)
        return best, bd


# default action table: state -> list of (frames, buttons) moves
# (learned from Metal Slug X; other games override via their plugin)
DEFAULT_ACTIONS = {
    "title": [(15, {"START"})],          # open menu / restart from demo
    "demo": [(15, {"START"})],           # START during attract boots 1P
    "menu": [(15, {"B"})],               # cross selects the highlighted item
    "dialog": [(10, {"UP"}), (40, set()), (15, {"A"})],  # YES + circle
    "loading": [(60, set())],
    "gameplay": [],
    "pause": [(15, {"START"})],
    "unknown": [(15, {"START"})],        # skip radio/intro screens
}


def navigate(core, mem, nav, refs_dir, max_steps=48, settle=40,
             actions=None, log=None):
    """Play the menus until 'gameplay' is detected. Returns state name."""
    actions = actions or DEFAULT_ACTIONS
    state = None
    for step_i in range(max_steps):
        rgb = core.frame_rgb()
        if rgb is None:
            core.run_frame()
            continue
        t = to_thumb(rgb)
        state, dist = nav.classify(t)
        if log:
            log(f"nav[{step_i}] {state} (d={dist:.1f})")
        if state == "gameplay":
            return "gameplay"
        for frames, btns in actions.get(state, actions["unknown"]):
            core.run(frames, btns)
        core.run(settle, set())
    return state or "unknown"

"""brain.py — the P4 deployment entry: the policy runs in ITS OWN
PROCESS that never imports the emulator, ps1play core, or any RAM/debug
capability. The emulator process sends frames over stdin/stdout;
the brain process returns actions. This is the mission's strongest
practical boundary: inside this process there is NOTHING to leak.

Wire protocol (length-prefixed):
  -> b"F" + u32 len + PNG-less raw uint8 RGB bytes (60*80*3)
  <- b"A" + u32 len + utf-8 action name
  -> b"R"            (reset history)
  -> b"Q"            (quit)

Self-audit: `--selfcheck` prints the process's imported module names;
the boundary test asserts `ps1play` is absent.
"""
import argparse
import json
import os
import sys

import numpy as np

# The brain process imports the boundary module DIRECTLY from its file
# (path import) so that `ps1play` — whose package __init__ pulls the
# emulator API chain — is NEVER loaded here. The selfcheck below
# asserts this; tests re-assert it in a fresh subprocess.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from visual_only import Brain  # noqa: E402


def read_exact(stream, n):
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            raise EOFError("frame pipe closed")
        buf += chunk
    return buf


def serve(artifact, inp=None, out=None):
    inp = inp or sys.stdin.buffer
    out = out or sys.stdout.buffer
    brain = Brain(artifact)
    out.write(b"B")                       # ready
    out.flush()
    while True:
        cmd = read_exact(inp, 1)
        if cmd == b"Q":
            break
        if cmd == b"R":
            brain.reset_history()
            out.write(b"K")
            out.flush()
            continue
        if cmd != b"F":
            continue
        n = int(np.frombuffer(read_exact(inp, 4), dtype="<u4")[0])
        raw = read_exact(inp, n)
        fr = np.frombuffer(raw, dtype=np.uint8).reshape(60, 80, 3)
        action = brain.act(fr)
        payload = action.encode()
        out.write(b"A")
        out.write(np.asarray(len(payload), dtype="<u4").tobytes())
        out.write(payload)
        out.flush()


def imported_modules():
    return sorted(m for m in sys.modules if not m.startswith("_"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        print(json.dumps({"modules": imported_modules(),
                          "ps1play_loaded":
                              any(m.startswith("ps1play")
                                  for m in sys.modules)}))
        sys.exit(0)
    serve(args.artifact)

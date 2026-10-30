"""brain_client.py — the subprocess-brain client (the deployment path),
extracted from runner.py so the student pipeline can use it WITHOUT
importing the runner module (which also hosts the assisted DAgger paths
— banned in the R57 teacher-off pipeline by ps1play.learn.student_only).

The child process imports only numpy + visual_only.py (asserted by the
selfcheck + tests) — inside it there is no emulator, no RAM, nothing to
leak.
"""
import os
import subprocess
import sys

import numpy as np

LEARN_DIR = os.path.dirname(os.path.abspath(__file__))


class BrainClient:
    """Subprocess brain: frames in, actions out (length-prefixed)."""

    def __init__(self, artifact_path):
        # Run brain.py by FILE PATH (not -m): importing it as a package
        # module would load the ps1play package __init__ (which pulls
        # the emulator API chain) into the brain process.
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(LEARN_DIR, "brain.py"),
             "--artifact", artifact_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        ready = self.proc.stdout.read(1)
        assert ready == b"B", ready

    @staticmethod
    def _write(buf, b):
        buf.write(b)
        buf.flush()

    def reset_history(self):
        self._write(self.proc.stdin, b"R")
        assert self.proc.stdout.read(1) == b"K"

    def act(self, rgb_small):
        raw = np.ascontiguousarray(rgb_small, dtype=np.uint8).tobytes()
        self._write(self.proc.stdin, b"F")
        self._write(self.proc.stdin,
                    np.asarray(len(raw), dtype="<u4").tobytes())
        self._write(self.proc.stdin, raw)
        hdr = self.proc.stdout.read(5)
        assert hdr[:1] == b"A", hdr
        n = int(np.frombuffer(hdr[1:], dtype="<u4")[0])
        return self.proc.stdout.read(n).decode()

    def close(self):
        try:
            self._write(self.proc.stdin, b"Q")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

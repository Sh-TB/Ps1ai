#!/usr/bin/env python3
"""w2_speedcheck.py — measure real emulation fps + enter_gameplay3 wall
time in THIS sandbox (the reach rerun claimed 3.2 s total, which needs
~4000 fps; previous sessions reported ~400 fps)."""
import sys
import time

sys.path.insert(0, "/home/z/my-project/ps1ai")
sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")

t0 = time.time()
from issue4_controller import boot          # noqa: E402

t_import = time.time() - t0
t0 = time.time()
p, fw = boot()
t_boot = time.time() - t0
frames = p.core.frames_run if hasattr(p.core, "frames_run") else -1
print(f"import: {t_import:.1f}s  boot: {t_boot:.1f}s  "
      f"frames_at_boot_end: {frames}")
print(f"effective fps: {frames / t_boot:.0f}" if t_boot > 0 else "")

t0 = time.time()
p.core.run(3000, {"RIGHT"})
dt = time.time() - t0
f2 = p.core.frames_run
print(f"3000f RIGHT: {dt:.1f}s -> {(f2 - frames) / dt:.0f} fps "
      f"(total frames {f2})")

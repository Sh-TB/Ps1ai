#!/usr/bin/env python3
"""psxmc_ab_device.py — A/B the pad device class against real input
delivery. One MODE per process (H5: second in-process boot is stale).

Mode A: DEVICE_JOYPAD (digital, id 0x41)
Mode B: DEVICE_ANALOG (DualShock, id 0x73)
Each: boot -> world ready -> hold UP 60f -> pos delta; hold SQ 30f ->
yaw delta. Result: which mode actually delivers movement/look.
"""
import json
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa
from ps1play.core.host import DEVICE_JOYPAD, DEVICE_ANALOG        # noqa

CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
ONE_BLOCK = 286720


def run_mode(mode_name, device):
    ws = f"/home/z/my-project/emu/games_psx/ws_ab_{mode_name}"
    p = PS1Play(CUE, workspace=ws)
    info = p.boot()
    if device is not None:
        p.core.set_port_device(device)
    P = None
    for _ in range(240):
        v = p.mem.u32(0x3C608)
        if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000:
            y = p.mem.u32((v & 0x1FFFFF) + 4)
            if 0 < y < 10 * ONE_BLOCK * 4:
                P = v & 0x1FFFFF
                break
        p.wait(30)
    if not P:
        return {"mode": mode_name, "verdict": "NO_WORLD"}
    p.wait(120)
    m = p.mem
    z0 = m.u32(P + 8)
    fwd0 = m.u16(P + 0x20)
    p.core.run(60, {"UP"})
    z1 = m.u32(P + 8)
    fwd1 = m.u16(P + 0x20)
    yaw0 = m.u32(P + 0x1C)
    p.core.run(30, {"SQ"})
    yaw1 = m.u32(P + 0x1C)
    return {"mode": mode_name, "device": device,
            "d_z": z1 - z0, "d_fwd": fwd1 - fwd0,
            "d_yaw": yaw1 - yaw0, "frames": p.core.frames_run}


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    from ps1play.plugins import psxmc_play
    for name, dev in (("digital", DEVICE_JOYPAD), ("analog", DEVICE_ANALOG)):
        # arm-splitting: decide the pad class BEFORE boot (api honours the
        # plugin capability); restore after each arm.
        psxmc_play.PSXMCPlayPlugin.INPUT_DEVICE = (
            "dualshock" if dev == DEVICE_ANALOG else None)
        r = run_mode(name, None)          # boot already chose the device
        r["device_class"] = ("ANALOG/DualShock"
                             if dev == DEVICE_ANALOG else "JOYPAD/digital")
        r["verdict"] = ("INPUT_OK" if (r.get("d_z") or r.get("d_yaw"))
                        else "INPUT_DEAD")
        out[name] = r
        print(name, "->", r)
    psxmc_play.PSXMCPlayPlugin.INPUT_DEVICE = "dualshock"
    with open("/home/z/my-project/emu/games_psx/evidence/"
              "psxmc_ab_device.json", "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

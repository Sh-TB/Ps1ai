#!/usr/bin/env python3
"""r35c_plan.py — offline win-plan simulation from the decoded board.
No emulator. Computes: zero-cell floods, remaining singles, greedy
nearest-neighbor route, tap/click/frame budget, predicted milestones.
"""
import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r35c_lib as L

cells = {}
raw = json.load(open(os.path.join(L.OUT, "board_decode.json")))
for k, v in raw["cells"].items():
    t = tuple(int(a) for a in k.split(","))
    cells[t] = v

TAP_F = 47          # 2 hold + 45 settle
CLICK_F = 130       # 40 cross hold + 90 settle
FLAG_F = 62         # 2 hold + 60 settle


def plan_reveal(cells, start=(0, 0), conn=8):
    NBR = L.NBR8 if conn == 8 else [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def adj(x, y):
        n = 0
        for dx, dy in NBR:
            nx, ny = x + dx, y + dy
            if 0 <= nx < L.GRID_W and 0 <= ny < L.GRID_H and cells[(nx, ny)]["mine"]:
                n += 1
        return n

    def flood(tx, ty, revealed):
        out = set()
        stack = [(tx, ty)]
        while stack:
            x, y = stack.pop()
            if (x, y) in revealed or (x, y) in out or cells[(x, y)]["mine"]:
                continue
            out.add((x, y))
            if adj(x, y) == 0:
                for dx, dy in NBR:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < L.GRID_W and 0 <= ny < L.GRID_H:
                        stack.append((nx, ny))
        return out

    revealed = {k for k, v in cells.items() if v["revealed"]}
    cur = start
    route = []
    taps = 0
    zeros_clicked = 0
    singles = 0
    for _ in range(300):
        cands = [k for k, v in cells.items()
                 if v["active"] and not v["mine"] and k not in revealed]
        if not cands:
            break
        zeros = [k for k in cands if adj(*k) == 0]
        pool = zeros if zeros else cands
        tgt = min(pool, key=lambda k: abs(k[0] - cur[0]) + abs(k[1] - cur[1]))
        d = abs(tgt[0] - cur[0]) + abs(tgt[1] - cur[1])
        taps += d
        fl = flood(*tgt, revealed)
        revealed |= fl
        route.append({"t": list(tgt), "kind": "zero" if zeros else "single",
                      "dist": d, "new": len(fl)})
        if zeros:
            zeros_clicked += 1
        else:
            singles += 1
        cur = tgt
    total_safe = sum(1 for k, v in cells.items()
                     if v["active"] and not v["mine"])
    return {"conn": conn, "revealed_final": len(revealed),
            "safe_total": total_safe, "zero_clicks": zeros_clicked,
            "single_clicks": singles, "clicks": zeros_clicked + singles,
            "nav_taps": taps, "frames": taps * TAP_F +
            (zeros_clicked + singles) * CLICK_F,
            "route": route, "unreached": sorted(
                [list(k) for k, v in cells.items()
                 if v["active"] and not v["mine"] and k not in revealed])}


def plan_flags(cells, route_end):
    mines = sorted([k for k, v in cells.items() if v["mine"]])
    cur = route_end
    order = []
    taps = 0
    while mines:
        tgt = min(mines, key=lambda k: abs(k[0] - cur[0]) + abs(k[1] - cur[1]))
        d = abs(tgt[0] - cur[0]) + abs(tgt[1] - cur[1])
        taps += d
        order.append({"t": list(tgt), "dist": d})
        mines.remove(tgt)
        cur = tgt
    return {"flags": len(order), "nav_taps": taps,
            "frames": taps * TAP_F + len(order) * FLAG_F,
            "order": order, "end": cur}


for conn in (8, 4):
    pr = plan_reveal(cells, conn=conn)
    pf = plan_flags(cells, tuple(pr["route"][-1]["t"]))
    print(f"== conn={conn} == revealed_final={pr['revealed_final']}/{pr['safe_total']} "
          f"zero_clicks={pr['zero_clicks']} single_clicks={pr['single_clicks']} "
          f"reveal_taps={pr['nav_taps']} flag_taps={pf['nav_taps']} "
          f"reveal_frames={pr['frames']} flag_frames={pf['frames']} "
          f"TOTAL_frames={pr['frames'] + pf['frames']}")
    if conn == 8:
        for r in pr["route"][:40]:
            print("  ", r)
        print("   flags first 8:", pf["order"][:8])
        print("    unreached:", pr["unreached"][:10])

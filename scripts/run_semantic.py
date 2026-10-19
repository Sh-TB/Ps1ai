#!/usr/bin/env python3
"""run_semantic.py — THE full agent session:

  boot (proven adaptive nav) -> per-boot calibration ->
  GameShark proofs (published codes + derived freeze codes) ->
  WorldModel entity discovery (enemies/bullets/items, zero tokens) ->
  semantic play of Mission 1 (shoot enemy / eat health / dodge bullet /
  pickup items) with optional GameShark assist (Invincible = HP freeze).

Outputs: report JSON + PNG evidence + telemetry in download/ps1play_v3_semantic/
"""
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")

from ps1play.api import PS1Play                      # noqa: E402
from ps1play.agent.gameshark import GameShark, GSCode  # noqa: E402
from ps1play.agent.worldmodel import WorldModel      # noqa: E402
from ps1play.agent.policy import SemanticPolicy      # noqa: E402
from mission import ensure_mission, recover, idle_churn  # noqa: E402
from calibrate import calibrate                      # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
EVID = "/home/z/my-project/download/ps1play_v3_semantic"
OUT = os.path.join(EVID, "semantic_report.json")
os.makedirs(EVID, exist_ok=True)

CHUNKS = int(os.environ.get("SEM_CHUNKS", "420"))    # 420*60 = 25200f ~7min
ASSIST = os.environ.get("SEM_ASSIST", "1") == "1"    # GS Invincible during play
SKIP_GS = os.environ.get("SEM_SKIP_GS", "0") == "1"

report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
          "mode": "semantic+gs_assist" if ASSIST else "semantic-legit"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(EVID, name))
    except Exception as e:                              # noqa: BLE001
        log("png fail:", e)


# ====================================================================
# 1) BOOT + ENTER MISSION
# ====================================================================
p = PS1Play(GAME, verbose=False)
info = p.boot()
log("boot:", info)
t0 = time.time()
r = p.enter_gameplay3()
log("enter:", {k: v for k, v in r.items() if k != "proof"})
report["boot"] = info
report["enter"] = {k: v for k, v in r.items() if k != "proof"}
if not r.get("in_game"):
    sys.exit("!! boot failed")

# ====================================================================
# 1b) ARE WE ALIVE IN THE MISSION? (recover from continue/pause)
# ====================================================================
mission = ensure_mission(p, log=log)
log("mission gate:", mission)
report["mission_gate"] = mission
if not mission["in_mission"]:
    sys.exit("!! could not reach a live mission state")
p.core.run(150, {"RIGHT", "Y"})        # keep momentum, stay alive
p._advance()

# ====================================================================
# 2) PER-BOOT CALIBRATION (hp/bombs/timer/x/y)
# ====================================================================
cal = calibrate(p)
log("calibration:", json.dumps(cal))
report["calibration"] = cal
gsmap = p.profile.get("gsmap") or {}
HP_A = (gsmap.get("hp") or {}).get("addr")
HP_FULL = (cal.get("hp") or {}).get("full", 200)
BOMB_A = (gsmap.get("bombs") or {}).get("addr")
TMR_A = (gsmap.get("timer") or {}).get("addr")

# ====================================================================
# 3) GAMESHARK PROOFS — "codes must work 100%"
# ====================================================================
gs = GameShark(p.mem)
report["gameshark"] = {}
if not SKIP_GS:
    # published code-patch (gamehacking.org, SLUS-01212): Infinite Bombs
    try:
        res = gs.verify_patch(
            p.core, p.states, "cal_base",
            GSCode("800398BE 2400"), 0x0398B4, "u16", {"A"})
        report["gameshark"]["published_patch_infinite_bombs"] = res
        log("GS published patch (800398BE 2400):", json.dumps(res))
    except Exception as e:                              # noqa: BLE001
        log("GS patch test error:", e)

    # derived freeze code on the calibrated bombs address
    if BOMB_A:
        try:
            res = gs.verify_freeze_event(
                p.core, p.states, "cal_base", BOMB_A, "u16", {"A"})
            report["gameshark"]["derived_freeze_infinite_bombs"] = res
            log("GS derived freeze (bombs):", json.dumps(res))
        except Exception as e:                          # noqa: BLE001
            log("GS freeze test error:", e)

# ====================================================================
# 4) WORLD MODEL — entity discovery (enemies / bullets / items)
# ====================================================================
counters = {}
for role, spec in gsmap.items():
    if spec and spec.get("addr") is not None:
        counters[spec["addr"]] = role
wm = WorldModel(p.mem, counters=counters)
dx = (p.profile.get("discovered") or {})
if dx.get("player_x", {}).get("addr") is not None:
    wm.player_x_addr = dx["player_x"]["addr"]
if dx.get("player_y", {}).get("addr") is not None:
    wm.player_y_addr = dx["player_y"]["addr"]

# assist (Invincible) ON during discovery so probes survive contact
if ASSIST and HP_A:
    frozen = gs.freeze("assist_invincible", HP_A, "u16", value=HP_FULL)
    log(f"ASSIST: Invincible freeze hp@{hex(HP_A)} = {frozen}")
    report["assist"] = {"invincible": {"addr": hex(HP_A), "value": frozen}}

png(p, "00_before_discovery.png")
p.save_state("disc_base")
try:
    disc = wm.discover(p.core, p.states, "disc_base", budget=2600, dbg=True)
except Exception as e:                                  # noqa: BLE001
    log("discovery error:", e)
    disc = {"error": str(e)}
report["worldmodel"] = disc
p.load_state("disc_base")
png(p, "01_after_discovery.png")

# ====================================================================
# 5) SEMANTIC PLAY — Mission 1
# ====================================================================
policy = SemanticPolicy(plugin=p.plugin)
scene_dbg = os.environ.get("SEM_SCENE") == "1"

evc = defaultdict(int)
tel = []
stall, last_x = 0, None
hp_drops = 0
prev_hp = None
t_play = time.time()
timer_last, timer_stall = None, 0
cleared_guess = False

p.save_state("mission_start")
png(p, "02_mission_start.png")

for i in range(CHUNKS):
    obs = p.observer.observe(p.t)
    feat = p.plugin.features(p.mem, obs)
    for e in feat.get("events", ()):
        evc[e] += 1

    # invincibility telemetry: hp must NEVER drop while assist is on
    # (first 3 chunks ignored: pre-freeze residue settles)
    hp = feat.get("hp")
    if ASSIST and i >= 3 and prev_hp is not None and hp is not None \
            and hp < prev_hp:
        hp_drops += 1
        gs.tick()                       # re-assert the freeze immediately
    prev_hp = hp

    # stall detection on player x
    xw = feat.get("x")
    if xw is not None and last_x is not None:
        stall = stall + 60 if xw == last_x else 0
    last_x = xw

    # timer stall -> boss/clear sequence guess
    if TMR_A:
        tv = p.mem.u16(TMR_A)
        if timer_last is not None and tv == timer_last and tv > 0:
            timer_stall += 60
        else:
            timer_stall = 0
        timer_last = tv
        if timer_stall > 900 and not cleared_guess:
            cleared_guess = True
            report["clear_suspect"] = {"chunk": i, "t": p.t,
                                       "note": "mission timer froze >900f "
                                               "(boss fight / clear seq)"}
            png(p, "03_clear_suspect.png")

    # ---- world scene (zero tokens) ------------------------------------
    scene = wm.read_world(p.core)
    scene["threat"] = wm.threat(scene)
    ne = wm.nearest(scene, "enemies")
    scene["nearest_enemy"] = ne
    scene["n_enemies"] = len(scene["enemies"])
    scene["nearest_health"] = wm.nearest(scene, "health")
    scene["nearest_item"] = wm.nearest(scene, "items")

    # ---- policy decision ----------------------------------------------
    ctx_feat = dict(feat)
    ctx_feat["events"] = feat.get("events", [])
    segs = policy.decide(60, scene, ctx_feat, stall=stall)
    done = 0
    for s_ in segs:
        k = min(s_["frames"], 60 - done)
        if k > 0:
            p.core.set_buttons(s_["btns"])
            for _f in range(k):          # GS codes tick EVERY frame
                p.core.run_frame()
                gs.tick()
            done += k
    if done < 60:
        for _f in range(60 - done):
            p.core.run_frame()
            gs.tick()
    p._advance()
    if ctx_feat.get("stall_reset"):
        stall = 0

    if scene_dbg and i % 10 == 0:
        log(f"[scene] i={i} enemies={scene['n_enemies']} "
            f"bullets={len(scene['bullets'])} threat={scene['threat']} "
            f"hp={feat.get('hp')} bombs={feat.get('bombs')} "
            f"act={policy.last_act['act']}")

    # ---- keepalive: quiet screen = dead/paused -> recover -------------
    if i % 15 == 14:
        ch = idle_churn(p, 40)
        if ch < 800:
            log(f"[keepalive] quiet screen churn={ch} at chunk {i}")
            recover(p, log=log)
            report.setdefault("recoveries", []).append({"chunk": i,
                                                        "churn": ch})

    if i % 20 == 19:
        tel.append({"chunk": i, "t": p.t, "feat": {
            k: v for k, v in feat.items() if k != "events"},
            "scene": {"enemies": scene["n_enemies"],
                      "bullets": len(scene["bullets"]),
                      "act": policy.last_act["act"]}})
        png(p, f"play_{(i // 20) + 1:02d}.png")
    if i in (150, 300) or i == CHUNKS - 1:
        name = f"cp_{i}"
        p.save_state(name)
        log("checkpoint:", name, "at t =", p.t)

wall_play = time.time() - t_play
report["play"] = {"chunks": CHUNKS, "frames": CHUNKS * 60,
                  "wall_s": round(wall_play, 1),
                  "fps": round(CHUNKS * 60 / wall_play, 1)}
report["events"] = dict(evc)
report["policy_stats"] = policy.stats
report["hp_drops_while_invincible"] = hp_drops
report["telemetry"] = tel[::2]
report["states"] = [s["name"] for s in p.states.list()]
report["gs_log"] = gs.log
png(p, "99_end.png")

# GS verdict
if not SKIP_GS:
    verdict = {}
    pub = report["gameshark"].get("published_patch_infinite_bombs") or {}
    der = report["gameshark"].get("derived_freeze_infinite_bombs") or {}
    verdict["published_gs_code_works"] = pub.get("works") is True
    verdict["derived_code_works"] = der.get("works") is True
    verdict["invincible_held"] = (hp_drops == 0) if ASSIST else None
    report["gameshark"]["verdict"] = verdict
    log("GAMESHARK VERDICT:", json.dumps(verdict))

json.dump(report, open(OUT, "w"), indent=1)
p.save_profile()
log("report ->", OUT)
print(json.dumps({"enter": report["enter"].get("in_game"),
                  "calibration": cal,
                  "worldmodel": disc,
                  "events": report["events"],
                  "policy_stats": policy.stats,
                  "hp_drops_while_invincible": hp_drops,
                  "gameshark": report.get("gameshark", {}).get("verdict"),
                  "play": report["play"]}, indent=1, default=str))

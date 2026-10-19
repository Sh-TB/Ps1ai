#!/usr/bin/env python3
"""run_semantic2.py — THE full semantic session (v2, perception-guarded).

  boot -> enter -> input-responsive gate -> PerceptionGuard.anchor()
  -> GameShark assist (Invincible = hp freeze, Infinite Bombs freeze)
  -> WorldModel entity discovery -> semantic policy play of Mission 1
  (shoot enemies / dodge / grenade clusters / advance) with live
  telemetry, checkpoints, PNG evidence and GS verdicts.

Modes:
  SEM_ASSIST=1  (default) GameShark assist ON  -> push to clear Mission 1
  SEM_ASSIST=0               legit play (legal inputs only)
"""
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")

from ps1play.api import PS1Play                              # noqa: E402
from ps1play.agent.gameshark import GameShark                # noqa: E402
from ps1play.agent.perception import PerceptionGuard         # noqa: E402
from ps1play.agent.worldmodel import WorldModel              # noqa: E402
from ps1play.agent.policy import SemanticPolicy              # noqa: E402
from mission import ensure_mission, recover, idle_churn, responsive  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
EVID = "/home/z/my-project/download/ps1play_v3_semantic"
OUT = os.path.join(EVID, "semantic_report2.json")
os.makedirs(EVID, exist_ok=True)

CHUNKS = int(os.environ.get("SEM_CHUNKS", "400"))     # 400*60 = 24000f ~6.7min
ASSIST = os.environ.get("SEM_ASSIST", "1") == "1"
SCENE_DBG = os.environ.get("SEM_SCENE") == "1"

report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
          "mode": ("semantic+gs_assist" if ASSIST else "semantic-legit")}


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
# 1) BOOT + ENTER + GATE
# ====================================================================
p = PS1Play(GAME)
info = p.boot()
log("boot:", info)
r = p.enter_gameplay3()
log("enter:", r.get("in_game"))
report["boot"] = info
report["enter"] = r.get("in_game")
if not r.get("in_game"):
    sys.exit("!! boot failed")
m = ensure_mission(p, tries=6, log=log)
log("gate:", {k: v for k, v in m.items() if k != "evidence"})
report["gate"] = {k: v for k, v in m.items() if k != "evidence"}
if not m.get("in_mission"):
    sys.exit("!! gate failed")

# ====================================================================
# 2) PERCEPTION ANCHOR (GameShark layout, translated live)
# ====================================================================
guard = PerceptionGuard(p)
anch = guard.anchor(log=log)
log("anchor:", anch)
report["anchor"] = anch
if not anch.get("ok"):
    sys.exit("!! perception anchor failed")

# ====================================================================
# 3) GAMESHARK ASSIST (the '100% works' demo, opt-in)
#    Only VERIFIED addresses are frozen. hp gets its own freeze-test
#    protocol (freezing the wrong word corrupts the game).
# ====================================================================
gs = GameShark(p.mem)
report["gameshark"] = {"assist": ASSIST}
if ASSIST:
    b0 = guard.read("bombs")
    frozen_b = gs.freeze("assist_bombs", guard.addrs["bombs"], "u16",
                         value=max(b0 or 10, 10))
    log(f"GS assist: bombs@{guard.addrs['bombs']:#x}:={frozen_b} (frozen)")
    report["gameshark"].update({
        "infinite_bombs": {"addr": hex(guard.addrs["bombs"]),
                           "value": frozen_b}})
    hp_addr = guard.find_player_hp(log=log)
    report["gameshark"]["hp_search"] = hex(hp_addr) if hp_addr else None
    if hp_addr:
        hp0 = guard.read("hp")
        full = hp0 or 100
        frozen_hp = gs.freeze("assist_invincible", hp_addr, "u16",
                              value=full)
        log(f"GS assist: hp@{hp_addr:#x}:={frozen_hp} (Invincible ON)")
        report["gameshark"]["invincible"] = {"addr": hex(hp_addr),
                                             "value": frozen_hp}

# ====================================================================
# 4) WORLD MODEL (entity slots, zero tokens)
# ====================================================================
counters = {a: role for role, a in guard.addrs.items()}
wm = WorldModel(p.mem, counters=counters)
if guard.addrs.get("hp"):
    counters[guard.addrs["hp"]] = "hp"
png(p, "00_pre_discovery.png")
p.save_state("disc_base")
try:
    disc = wm.discover(p.core, p.states, "disc_base", budget=2400, dbg=True)
except Exception as e:                                  # noqa: BLE001
    log("discovery error:", e)
    disc = {"error": str(e)}
report["worldmodel"] = disc
p.load_state("disc_base")

# re-anchor if the discovery run moved/reloaded the mission
gs.disable_all()
if not guard.valid():
    ok, _ = responsive(p)
    if not ok:
        recover(p, log=log)
    ra = guard.anchor(log=log)
    log("re-anchor after discovery:", ra)
    report["reanchor_after_discovery"] = ra
    if ASSIST and ra.get("ok"):
        b0 = guard.read("bombs")
        gs.freeze("assist_bombs", guard.addrs["bombs"], "u16",
                  value=max(b0 or 10, 10))
        guard.find_player_hp(log=log)      # ALWAYS re-verify after reload
        if guard.addrs.get("hp"):
            hp0 = guard.read("hp")
            if hp0 and hp0 > 0:
                gs.freeze("assist_invincible", guard.addrs["hp"], "u16",
                          value=hp0)

# ====================================================================
# 5) SEMANTIC PLAY — Mission 1
# ====================================================================
policy = SemanticPolicy()
evc = defaultdict(int)
tel = []
stall_chunks = 0
last_score = guard.score()
hp_drops = 0
prev_hp = guard.read("hp")
grenades_seen = guard.read("bombs")
t_play = time.time()
p.save_state("mission_live")
png(p, "01_mission_live.png")

for i in range(CHUNKS):
    st = guard.state()
    score = guard.score()

    # ---- GS assist integrity + events (zero tokens) ------------------
    events = []
    hp_now = guard.read("hp") if guard.addrs.get("hp") else None
    if prev_hp is not None and hp_now is not None and hp_now < prev_hp:
        hp_drops += 1
        gs.tick()
    if grenades_seen is not None and st.get("bombs") is not None \
            and st["bombs"] < grenades_seen:
        events.append("grenade_used")
    grenades_seen = st.get("bombs")
    if score > last_score:
        events.append("score_up")
        events.append(f"score+{score - last_score}")
    last_score = score
    prev_hp = hp_now
    for e in events:
        evc[e] += 1

    # ---- scene (zero tokens) ------------------------------------------
    scene = wm.read_world(p.core)
    scene["threat"] = wm.threat(scene)
    scene["nearest_enemy"] = wm.nearest(scene, "enemies")
    scene["n_enemies"] = len(scene.get("enemies", []))
    scene["nearest_health"] = wm.nearest(scene, "health")
    scene["nearest_item"] = wm.nearest(scene, "items")

    # ---- policy ---------------------------------------------------------
    feat = {"hp": st.get("hp"), "bombs": st.get("bombs"),
            "events": events}
    segs = policy.decide(60, scene, feat, stall=stall_chunks * 60)
    done = 0
    for s_ in segs:
        k = min(s_["frames"], 60 - done)
        if k > 0:
            p.core.set_buttons(s_["btns"])
            for _f in range(k):              # GS ticks EVERY frame
                p.core.run_frame()
                gs.tick()
            done += k
    p._advance()

    # ---- progress / stall: score frozen + churn low = stuck or dead ----
    if i % 10 == 9:
        ok, (i1, rr) = responsive(p)
        if not ok:
            log(f"[keepalive] chunk {i}: dead screen (idle={i1} run={rr})")
            gs.disable_all()
            recover(p, log=log)
            ra = guard.anchor(log=log)
            report.setdefault("reanchors", []).append({"chunk": i,
                                                       **ra})
            if ASSIST and ra.get("ok"):
                b0 = guard.read("bombs")
                gs.freeze("assist_bombs", guard.addrs["bombs"], "u16",
                          value=max(b0 or 10, 10))
                guard.find_player_hp(log=log)
                if guard.addrs.get("hp"):
                    hp0 = guard.read("hp")
                    if hp0 and hp0 > 0:
                        gs.freeze("assist_invincible",
                                  guard.addrs["hp"], "u16", value=hp0)
        elif score == last_score and rr < 3500:
            stall_chunks += 1
        else:
            stall_chunks = 0

    if SCENE_DBG and i % 10 == 0:
        log(f"[scene] i={i} enemies={scene['n_enemies']} "
            f"threat={scene['threat'] is not None} hp={st.get('hp')} "
            f"bombs={st.get('bombs')} act={policy.last_act['act']}")
    if i % 25 == 24:
        tel.append({"chunk": i, "score": score,
                    "hp": st.get("hp"), "bombs": st.get("bombs"),
                    "timer": st.get("timer"), "lives": st.get("lives"),
                    "act": policy.last_act["act"],
                    "scene": {"enemies": scene["n_enemies"]}})
        png(p, f"play_{(i // 25) + 1:02d}.png")
    if i in (150, 300) or i == CHUNKS - 1:
        p.save_state(f"cp_{i}")
        log("checkpoint cp_", i, "score", score)

wall_play = time.time() - t_play
report["play"] = {"chunks": CHUNKS, "frames": CHUNKS * 60,
                  "wall_s": round(wall_play, 1),
                  "fps": round(CHUNKS * 60 / wall_play, 1),
                  "score_start": None, "score_end": guard.score()}
report["events"] = dict(evc)
report["policy_stats"] = policy.stats
report["hp_drops_while_invincible"] = hp_drops
report["telemetry"] = tel
report["states"] = [s["name"] for s in p.states.list()]
png(p, "99_end.png")

if ASSIST:
    verdict = {
        "invincible_held_whole_session": hp_drops == 0,
        "infinite_bombs_held": evc.get("grenade_used", 0) == 0,
        "note": "freeze codes re-asserted every frame (hardware GS "
                "behaviour); addresses re-anchored after any reload",
    }
    report["gameshark"]["verdict"] = verdict
    log("GS VERDICT:", json.dumps(verdict))

json.dump(report, open(OUT, "w"), indent=1)
p.save_profile()
log("report ->", OUT)
print(json.dumps({"enter": report["enter"], "anchor": report["anchor"],
                  "worldmodel": disc,
                  "policy_stats": policy.stats,
                  "events": report["events"],
                  "hp_drops_while_invincible": hp_drops,
                  "score_end": report["play"]["score_end"],
                  "gameshark": report["gameshark"].get("verdict"),
                  "play": report["play"]}, indent=1, default=str))

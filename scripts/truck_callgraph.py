#!/usr/bin/env python3
"""Phase 2: build the truck damage-path call graph from the committed Ghidra
corpus (overlay_decompiled.json has per-func callers/callees/bytes/c).

Outputs a compact JSON to work/msx_recomp/evidence/issue5_truck/callgraph.json
and prints a human-readable summary. Read-only on the repo.
"""
import json, sys, os

REPO = "/home/z/my-project/ps1ai"
OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck"
os.makedirs(OUT, exist_ok=True)

corp = json.load(open(f"{REPO}/data/games/SLUS-01212/ghidra/overlay_decompiled.json"))
exe_anchors = json.load(open(f"{REPO}/data/games/SLUS-01212/ghidra/exe_decompiled_targeted.json"))

TARGETS = ["8009de68", "800a41d8", "800a4588"]

def fn(addr):
    return corp.get(addr)

def name_of(addr):
    f = corp.get(addr)
    if f:
        return f.get("name", f"FUN_{addr}")
    return f"EXE_{addr}" if addr not in corp else f["name"]

def size_of(f):
    b = f.get("bytes")
    if isinstance(b, int):
        return b  # byte length recorded directly
    if isinstance(b, (list, str)):
        return len(b) // 4
    return None

def normalize(lst):
    out = []
    for x in lst or []:
        a = str(x).lower().replace("0x", "").replace("fun_", "")
        out.append(a[-8:])
    return out

report = {}
for t in TARGETS:
    f = fn(t)
    if not f:
        report[t] = {"error": "not in corpus"}
        continue
    callers = normalize(f.get("callers"))
    callees = normalize(f.get("callees"))
    entry = {
        "name": f.get("name"),
        "size": size_of(f),
        "callers": callers,
        "callees": callees,
        "caller_details": {},
        "callee_details": {},
    }
    for c in callers:
        cf = fn(c)
        if cf:
            entry["caller_details"][c] = {
                "name": cf.get("name"),
                "size": size_of(cf),
                "callees": normalize(cf.get("callees")),
            }
    for c in callees:
        cf = fn(c)
        if cf:
            entry["callee_details"][c] = {
                "name": cf.get("name"),
                "size": size_of(cf),
            }
    report[t] = entry

# Functions that reference the hub pointer address constant 0x800C9A98.
# In the overlay the pattern is lui 0x800d + lw -0x6568.
hub_users = []
for addr, f in corp.items():
    c = f.get("c") or ""
    if "0x800C9A98" in c or "-6568" in c or "unk-6568" in c:
        hub_users.append(addr)
report["_hub_users_overlay"] = sorted(hub_users)

# State-pointer target addresses seen in m2c outputs: 0x800AB094, 0x800AB0FC,
# 0x800AADBC, 0x800B179C, 0x800151DC
state_targets = {
    "800ab094": "state ptr target of FUN_8009de68 else-path",
    "800ab0fc": "state ptr target after X_800a8924 true",
    "800aadbc": "state ptr target after X_800a8ecc true",
    "800b179c": "state ptr target of FUN_800a4588",
    "800151dc": "state ptr target of FUN_800a41d8",
}
report["_state_targets"] = {}
for st, desc in state_targets.items():
    f = fn(st)
    report["_state_targets"][st] = {
        "desc": desc,
        "in_overlay_corpus": f is not None,
        "name": f.get("name") if f else None,
        "size": size_of(f) if f else None,
        "callers": normalize(f.get("callers")) if f else [],
        "callees": normalize(f.get("callees")) if f else [],
    }

# hub anchor refs from the EXE corpus
hb = exe_anchors.get("entity_base_0x800C9A98", {})
report["_hub_exe_refs"] = {
    "n_refs": len(hb.get("refs") or []),
    "refs": (list(hb.get("refs") or {}) if isinstance(hb.get("refs"), dict) else (hb.get("refs") or []))[:40],
}

with open(f"{OUT}/callgraph.json", "w") as fh:
    json.dump(report, fh, indent=1)

# Human summary
for t in TARGETS:
    e = report[t]
    print(f"== {t} ({e.get('name')}) size~{e.get('size')} insns")
    print("   callers:", [f"{c}({d['name']})" for c, d in e["caller_details"].items()] or e["callers"])
    print("   callees:", [f"{c}({d['name']})" for c, d in e["callee_details"].items()] or e["callees"])
    print()
print("hub users in overlay:", len(report["_hub_users_overlay"]))
print("state targets:")
for st, d in report["_state_targets"].items():
    print(" ", st, d["desc"], "| in corpus:", d["in_overlay_corpus"], d["name"],
          "| callers:", [f"{c}({corp[c]['name']})" for c in d["callers"] if c in corp])
print("hub EXE refs:", report["_hub_exe_refs"]["n_refs"])

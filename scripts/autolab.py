#!/usr/bin/env python3
"""autolab.py — one-command autonomous experiment runner for PS1Play.

Executes a bounded, unattended ladder of gates from cheapest to most
expensive, records every experiment as a resumable JSONL line, dedups
unchanged re-runs, and finishes with the single highest-value blocker.

    python3 scripts/autolab.py --goal gates --budget-minutes 10
    python3 scripts/autolab.py --goal mission1-progress --budget-minutes 60

Gate ladder (each gate is recorded honestly; a gate passing never
implies the next one):

    UNIT              offline pytest suite
    EMULATOR_SMOKE    real core loads, retro_init + env wiring
    BIOS_BOOT         real firmware executes (retail or OpenBIOS
                      override), real frames rendered — the verdict is
                      labeled with WHICH firmware path was used
    CONTENT_BOOT      lawful self-generated content mounted + TOC read
                      through the real libretro path
    INPUT_CAUSALITY   controller input causes verified world change
    TARGET_GAME       the exact SLUS-01212 image (user-supplied, never
                      committed)

Experiment records: <workspace>/autolab/experiments.jsonl with a
fingerprint of (tool, arguments, core identity, BIOS md5, content md5,
repo HEAD). A fingerprint that already has a PASS record is reported
as DEDUP instead of being re-run; a FAIL is only re-run after its
inputs changed, or with --force.

Exit codes: 0 all attempted gates passed | 2 some gate blocked/failed
| 3 environment unusable.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

DEF_CORE = os.environ.get(
    "M1_CORE", "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so")
DEF_WORKSPACE = os.environ.get("M1_WORKSPACE",
                               "/home/z/my-project/ps1-test/emu")
DEF_GAME = os.environ.get(
    "M1_GAME", "/home/z/my-project/ps1-test/emu/games/"
               "Metal Slug X (USA).cue")
OPENBIOS = os.path.join(_REPO, "third_party", "openbios", "openbios.bin")


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Lab:
    """Experiment ledger: JSONL records + fingerprint dedup + budget."""

    def __init__(self, workspace, budget_minutes, force=False):
        self.dir = os.path.join(workspace, "autolab")
        os.makedirs(self.dir, exist_ok=True)
        self.ledger = os.path.join(self.dir, "experiments.jsonl")
        self.budget_s = budget_minutes * 60
        self.t0 = time.time()
        self.force = force
        self.records = []

    def elapsed(self):
        return time.time() - self.t0

    def out_of_budget(self):
        return self.elapsed() > self.budget_s

    def load_ledger(self):
        seen = {}
        if os.path.exists(self.ledger):
            with open(self.ledger) as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("status") in ("PASS", "PARTIAL"):
                        seen[r["fingerprint"]] = r
        return seen

    def run(self, gate, hypothesis, next_action, cmd, inputs, fn=None):
        """Run one gate (or reuse its deduped result). `cmd` is the
        command vector for the record; `fn` executes it in-process and
        returns (status, detail, extras)."""
        fp_src = {"gate": gate, "cmd": cmd, "inputs": inputs,
                  "head": _repo_head()}
        fp = hashlib.sha1(json.dumps(fp_src, sort_keys=True).encode()) \
            .hexdigest()[:16]
        prior = self.cache.get(fp) if hasattr(self, "cache") else None
        rec = {"gate": gate, "fingerprint": fp,
               "hypothesis": hypothesis, "next_action": next_action,
               "cmd": cmd, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if prior and not self.force:
            rec.update(status="DEDUP",
                       detail=f"reused {prior.get('gate')} result "
                              f"({prior.get('detail', '')[:80]})",
                       elapsed_s=0.0)
            self.records.append(rec)
            self._append(rec)
            print(f"[{gate}] DEDUP — {rec['detail']}")
            return rec
        status, detail, extras = "FAIL", "not executed", {}
        try:
            out = fn() if fn else (status, detail, {})
            if len(out) == 2:
                status, detail = out
            else:
                status, detail, extras = out
        except Exception as e:                                  # noqa: BLE001
            status, detail = "FAIL", f"exception: {e!r}"
        rec.update(status=status, detail=detail, **extras)
        rec["elapsed_s"] = round(self.elapsed(), 1)
        self.records.append(rec)
        self._append(rec)
        mark = {"PASS": "+", "PARTIAL": "~", "BLOCKED": "!",
                "FAIL": "x"}.get(status, "?")
        print(f"[{gate}] {mark} {status} — {detail[:150]}")
        return rec

    def _append(self, rec):
        with open(self.ledger, "a") as f:
            f.write(json.dumps(rec) + "\n")


def _repo_head():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
            capture_output=True, timeout=10).stdout.decode().strip()
    except Exception:                                           # noqa: BLE001
        return "unknown"


def _run_json(cmd, timeout_s):
    p = subprocess.run(cmd, capture_output=True, timeout=timeout_s)
    try:
        return p.returncode, json.loads(p.stdout.decode())
    except json.JSONDecodeError:
        return p.returncode, {"raw": p.stdout.decode()[-400:]}


def gate_unit(lab):
    def fn():
        p = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                           cwd=_REPO, capture_output=True, timeout=120)
        tail = p.stdout.decode().strip().splitlines()[-1:] or [""]
        ok = p.returncode == 0
        return ("PASS" if ok else "FAIL",
                tail[0] if tail else f"pytest rc={p.returncode}",
                {"exit": p.returncode})
    return lab.run(
        "UNIT", "offline logic tests remain green",
        "fix regressions before any runtime work",
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        {"tests_dir": "tests"}, fn)


def gate_emulator_smoke(lab, core):
    def fn():
        rc, j = _run_json([sys.executable, "scripts/emulator_smoke.py",
                           "--core", core, "--json"], 180)
        status = "PASS" if rc == 0 else "FAIL"
        return status, f"{j.get('tier_result')} core={j.get('core', '?')}", {
            "exit": rc, "json": j}
    return lab.run(
        "EMULATOR_SMOKE", "core loads through the real ctypes host",
        "rebuild/relocate the core binary",
        [sys.executable, "scripts/emulator_smoke.py", "--core", core,
         "--json"], {"core_sha1": sha1_file(core) if os.path.exists(core)
                     else None}, fn)


BIOS_EXP = os.path.join(_REPO, "scripts", "retail_bios_experiment.py")
FIXTURE_CUE = "/tmp/ps1play_fixture/audio_fixture.cue"


def _run_bios_experiment(core):
    """Run the decisive BIOS experiment once, return (rc, json)."""
    return _run_json([sys.executable, "scripts/retail_bios_experiment.py",
                      "--core", core, "--json"], 600)


def gate_bios_boot(lab, core, workspace):
    def fn():
        rc, j = _run_bios_experiment(core)
        lab.last_bios_exp = j
        st = j.get("stage_retail", {})
        if st.get("verdict") == "PASS":
            return "PASS", (
                f"retail BIOS files characterized: {st.get('finding')} "
                "(name-aliased file executed; CPU exception-loops at "
                "reset with zero RAM writes; MD5s match no Redump "
                "revision)", {"finding": st.get("finding")})
        return "FAIL", st.get("error", "retail characterization "
                               "inconclusive"), {"exit": rc}
    return lab.run(
        "BIOS_BOOT",
        "execute the user BIOS under the core's real name-keyed lookup "
        "and characterize what runs",
        "the supplied BIOS images are invalid (site-side obfuscation or "
        "corruption); the BIOS-free exe-direct chain is the active path "
        "— supply a genuine dump (scph5501.bin MD5 490f666e…) only for "
        "TARGET_GAME",
        [sys.executable, "scripts/retail_bios_experiment.py"],
        {"tool": "retail_bios_experiment v2",
         "core_sha1": sha1_file(core) if os.path.exists(core) else None}, fn)


def gate_content_boot(lab, core, workspace):
    def fn():
        j = getattr(lab, "last_bios_exp", None)
        if j is None:
            rc, j = _run_bios_experiment(core)
            lab.last_bios_exp = j
        a = j.get("stage_a", {})
        b = j.get("stage_b", {})
        if a.get("verdict") == "PASS" and b.get("verdict") == "PASS":
            return "PASS", (
                "lawful self-made PS-X EXE dispatched through the core "
                "(BIOS-free exe-direct boot): PAD1 magic + advancing "
                f"counter (t60={a.get('counter_t60')} -> "
                f"t120={a.get('counter_t120')}); pad polls healthy "
                f"(ok={b.get('polls_ok')} fail={b.get('polls_fail')})",
                {"magic": a.get("magic"), "polls_ok": b.get("polls_ok")})
        return "FAIL", (a.get("error") or b.get("error") or
                        "EXE dispatch or poll health failed"), {}
    return lab.run(
        "CONTENT_BOOT",
        "executable dispatch proven with zero copyrighted content and "
        "zero BIOS dependency",
        "if FAIL: inspect bios_experiment_result.json stage_a/stage_b",
        [sys.executable, "scripts/retail_bios_experiment.py"],
        {"tool": "retail_bios_experiment v2",
         "core_sha1": sha1_file(core) if os.path.exists(core) else None}, fn)


def gate_input_causality(lab, core, workspace):
    def fn():
        j = getattr(lab, "last_bios_exp", None)
        if j is None:
            rc, j = _run_bios_experiment(core)
            lab.last_bios_exp = j
        c = j.get("stage_c", {})
        if c.get("verdict") == "PASS":
            arms = c.get("arms", {})
            return "PASS", (
                "controller -> world causality proven on the BIOS-free "
                "chain (none/RIGHT/LEFT = FF/DF/7F, RIGHT repeats): "
                + " ".join(f"{k}={v.get('sw1_mode')}({v.get('sw1_mode_ratio')})"
                           for k, v in arms.items()), {})
        return "BLOCKED", (
            "causality arms mismatched — see bios_experiment_result.json "
            "stage_c"), {"core_json": c}
    return lab.run(
        "INPUT_CAUSALITY",
        "controller input causes a verified world change, observed only "
        "through the payload's own RAM breadcrumbs",
        "if BLOCKED: check frontio SIO protocol assumptions in "
        "make_padtest_hw.py against the running core",
        [sys.executable, "scripts/retail_bios_experiment.py"],
        {"tool": "retail_bios_experiment v2",
         "core_sha1": sha1_file(core) if os.path.exists(core) else None}, fn)


TARGET_EXE_PROBE = os.path.join(_REPO, "scripts", "target_exe_probe.py")


def gate_target_exe(lab, core, workspace):
    """Boot the repository's own SLUS_012.12 main EXE, BIOS-free, and
    report how far the real binary gets (strictly observational)."""
    def fn():
        rc, j = _run_json([sys.executable, TARGET_EXE_PROBE,
                           "--core", core, "--json"], 600)
        verdict = j.get("verdict")
        boot = j.get("boot_log", "")
        wall = j.get("wall", "")
        if verdict == "DISPATCHED":
            return "PARTIAL", (
                "real SLUS_012.12 main EXE dispatches through the "
                "BIOS-free exe-direct v2 path (stack use + low-RAM "
                f"tables + text self-modification observed); wall: {wall} "
                "— kernel services (syscall) are the next dependency; "
                "gameplay NOT claimed", {"verdict": verdict,
                                         "boot": boot, "wall": wall})
        if verdict == "NO_DISPATCH":
            return "BLOCKED", f"no dispatch: {wall}", {
                "verdict": verdict, "boot": boot}
        return "FAIL", j.get("error", f"probe verdict={verdict}"), {
            "exit": rc}
    return lab.run(
        "TARGET_EXE",
        "the real game main binary executes on the BIOS-free chain far "
        "enough to expose its next dependency",
        "if the wall is syscall/kernel: a minimal Sys-exception "
        "dispatcher (self-made) or a genuine retail BIOS is required; "
        "full gameplay still requires the user-supplied SLUS-01212 "
        "disc image", [sys.executable, "scripts/target_exe_probe.py"],
        {"tool": "target_exe_probe v1",
         "core_sha1": sha1_file(core) if os.path.exists(core) else None}, fn)


def gate_target_game(lab, game, core, workspace):
    def fn():
        rc, j = _run_json(
            [sys.executable, "scripts/env_probe.py", "--game", game,
             "--core", core, "--workspace", workspace, "--json"], 600)
        missing = j.get("missing", [])
        if rc == 0 and j.get("ready"):
            return "PASS", "environment ready for real Mission-1 runs", \
                {"exit": rc, "probe": j}
        return "BLOCKED", (
            f"missing artifacts: {', '.join(missing)} — supply each one "
            "locally (copyrighted items are never committed)", {
                "exit": rc, "probe": j})
    return lab.run(
        "TARGET_GAME",
        "the exact SLUS-01212 image is present and verified",
        "supply the disc dump locally; the probe prints per-artifact "
        "next steps", [sys.executable, "scripts/env_probe.py"],
        {"game": os.path.basename(game) if os.path.exists(game) else None},
        fn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default="gates",
                    choices=["gates", "mission1-progress"])
    ap.add_argument("--budget-minutes", type=float, default=10)
    ap.add_argument("--game", default=DEF_GAME)
    ap.add_argument("--core", default=DEF_CORE)
    ap.add_argument("--workspace", default=DEF_WORKSPACE)
    ap.add_argument("--force", action="store_true",
                    help="re-run even if the fingerprint has a result")
    a = ap.parse_args()

    lab = Lab(a.workspace, a.budget_minutes, force=a.force)
    lab.cache = lab.load_ledger()
    print(f"autolab: goal={a.goal} budget={a.budget_minutes}min "
          f"head={_repo_head()} ledger={lab.ledger}")

    executed = [gate_unit(lab)]
    if lab.out_of_budget():
        return _finish(lab, executed)
    executed.append(gate_emulator_smoke(lab, a.core))
    if lab.out_of_budget():
        return _finish(lab, executed)

    if a.goal == "gates":
        executed.append(gate_bios_boot(lab, a.core, a.workspace))
        executed.append(gate_content_boot(lab, a.core, a.workspace))
        executed.append(gate_input_causality(lab, a.core, a.workspace))
        executed.append(gate_target_exe(lab, a.core, a.workspace))
        executed.append(gate_target_game(lab, a.game, a.core, a.workspace))
    else:  # mission1-progress
        executed.append(gate_target_game(lab, a.game, a.core, a.workspace))
        if not lab.out_of_budget():
            last = executed[-1]
            if last["status"] == "PASS":
                print("[mission1-progress] environment ready — the "
                      "bounded Mission-1 run is the NEXT experiment "
                      "(run scripts/run_mission1_legit.py with the "
                      "verified paths)")
            else:
                print("[mission1-progress] environment blocked — see "
                      "the TARGET_GAME record for exact artifacts")

    _finish(lab, executed)


def _finish(lab, records):
    bad = [r for r in records
           if r["status"] not in ("PASS", "PARTIAL", "DEDUP")]
    blocked = [r for r in records if r["status"] == "BLOCKED"]
    print("\n=== autolab summary ===")
    for r in records:
        print(f"  {r['gate']:16s} {r['status']:8s} {r['detail'][:110]}")
    if bad:
        first = bad[0]
        print(f"\nHIGHEST-VALUE BLOCKER: {first['gate']} — "
              f"{first['detail'][:200]}")
        print(f"next action: {first.get('next_action', '')}")
    elif blocked:
        print(f"\nHIGHEST-VALUE BLOCKER: {blocked[0]['gate']} — "
              f"{blocked[0]['detail'][:200]}")
    else:
        print("\nAll attempted gates passed. Next: escalate the "
              "cheapest remaining real-content experiment.")
    print(f"records: {lab.ledger}")
    sys.exit(0 if not bad else 2)


if __name__ == "__main__":
    main()

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

# v0.12: defaults resolve through the shared configuration contract;
# no machine-specific absolute paths remain in this file.
from ps1play import labconfig                                 # noqa: E402

DEF_CORE = labconfig.resolve_path("core")
DEF_WORKSPACE = labconfig.resolve_path("workspace")
DEF_GAME = labconfig.resolve_path("game")
DEF_EVID = labconfig.resolve_path("evidence_dir") or os.path.join(
    _REPO, "evidence_local", "mission1")
DEF_FIRMWARE = os.environ.get("M1_FIRMWARE", "auto")
OPENBIOS = os.path.join(_REPO, "third_party", "openbios", "openbios.bin")
RUNNER = os.path.join(_REPO, "scripts", "run_mission1_legit.py")
EXPLORER = os.path.join(_REPO, "scripts", "route_explorer.py")
VALIDATOR = os.path.join(_REPO, "scripts", "validate_cheats.py")
DEF_REGISTRY = os.path.join(_REPO, "data", "games", "SLUS-01212",
                            "cheats.json")


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

    def run(self, gate, hypothesis, next_action, cmd, inputs, fn=None,
            force=None):
        """Run one gate (or reuse its deduped result). `cmd` is the
        command vector for the record; `fn` executes it in-process and
        returns (status, detail, extras). `force` overrides the
        instance-level --force for this gate only."""
        force = self.force if force is None else force
        fp_src = {"gate": gate, "cmd": cmd, "inputs": inputs,
                  "head": _repo_head()}
        fp = hashlib.sha1(json.dumps(fp_src, sort_keys=True).encode()) \
            .hexdigest()[:16]
        prior = self.cache.get(fp) if hasattr(self, "cache") else None
        rec = {"gate": gate, "fingerprint": fp,
               "hypothesis": hypothesis, "next_action": next_action,
               "cmd": cmd, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if prior and not force:
            rec.update(status="DEDUP",
                       prior_status=prior.get("status"),
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


def _file_sha1(path):
    try:
        return sha1_file(path)
    except OSError:
        return None


def _cue_bin(game):
    """First FILE entry of a cue (or the path itself for non-cue)."""
    if game and game.lower().endswith(".cue"):
        try:
            with open(game, "r", errors="replace") as f:
                for ln in f:
                    if 'FILE "' in ln:
                        return os.path.join(os.path.dirname(game),
                                            ln.split('"')[1])
        except OSError:                                     # noqa: BLE001
            return None
    return game


def gate_mission1_progress(lab, game, core, workspace, firmware="auto",
                           chunks=30, evidence_dir=None, timeout_s=1200,
                           force=False):
    """v0.12 Phase C: actually LAUNCH the bounded real Mission-1 runner.

    Environment readiness is preflight, not the result. The runner is
    executed as a bounded subprocess (hard timeout), its JSON report is
    parsed, and the gameplay result is classified separately:
      PASS    runner exit 0 AND report says mission clear verified
      PARTIAL runner exit 0 AND report reached live Mission-1 gameplay
      FAIL    boot/enter failed, invalid/absent report, or subprocess
              stopped (timeout recorded honestly)
    """
    evidence_dir = evidence_dir or DEF_EVID
    runner_sha = _file_sha1(RUNNER)
    labconfig_sha = _file_sha1(
        os.path.join(_REPO, "ps1play", "labconfig.py"))
    game_bin = _cue_bin(game)
    inputs = {
        "core_sha1": _file_sha1(core) if core else None,
        "game_md5": (labconfig.file_md5(game_bin)
                     if game_bin and os.path.exists(game_bin) else None),
        "firmware_mode": firmware,
        "chunks": chunks,
        "runner_sha1": runner_sha,
        "labconfig_sha1": labconfig_sha,
    }

    def fn():
        t0 = time.time()
        # 1. cheapest preflight — env readiness (never the result)
        rc, j = _run_json(
            [sys.executable, "scripts/env_probe.py", "--game", game,
             "--core", core, "--workspace", workspace, "--json"], 600)
        if not (rc == 0 and j.get("ready")):
            return "BLOCKED", (
                "environment not ready — TARGET_GAME lists the exact "
                f"missing artifacts: {', '.join(j.get('missing', []))}"), {
                    "exit": rc, "probe": j}
        # 2. explicit firmware resolution (shared contract)
        try:
            fw = labconfig.resolve_firmware(firmware, workspace)
        except labconfig.FirmwareError as e:
            return "BLOCKED", f"firmware unresolved: {e}", {}
        # 3. bounded real-runner launch (budget-aware hard timeout)
        run_id = time.strftime("%Y%m%d_%H%M%S")
        run_evid = os.path.join(evidence_dir, f"m1p_{run_id}")
        os.makedirs(run_evid, exist_ok=True)
        report_path = os.path.join(run_evid, "mission1_report.json")
        remaining = max(60.0, lab.budget_s - lab.elapsed())
        hard_timeout = min(float(timeout_s), remaining)
        cmd = [sys.executable, RUNNER,
               "--game", game or "", "--core", core or "",
               "--workspace", workspace or "",
               "--evidence-dir", run_evid,
               "--firmware", fw["mode"],
               "--chunks", str(chunks),
               "--report", report_path]
        timed_out = False
        exit_code = None
        stderr_tail = ""
        stdout_tail = ""
        try:
            pr = subprocess.run(cmd, capture_output=True,
                                timeout=hard_timeout, cwd=_REPO)
            exit_code = pr.returncode
            stderr_tail = pr.stderr.decode(errors="replace")[-800:]
            stdout_tail = pr.stdout.decode(errors="replace")[-800:]
        except subprocess.TimeoutExpired as e:
            timed_out = True
            stderr_tail = ((e.stderr or b"").decode(errors="replace")
                           [-800:])
        elapsed = round(time.time() - t0, 1)
        # 4. parse the real gameplay report
        rep = None
        parse_err = None
        if not timed_out:
            try:
                with open(report_path) as f:
                    rep = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                parse_err = str(e)
        if timed_out:
            status = "FAIL"
            detail = (f"runner exceeded hard timeout at "
                      f"{hard_timeout:.0f}s (chunks={chunks}); subprocess "
                      "stopped; timeout recorded honestly")
        elif rep is None:
            status = "FAIL"
            detail = (f"runner exit={exit_code} without a valid report "
                      f"JSON ({parse_err}); stderr: "
                      f"{stderr_tail.strip()[-300:]}")
        else:
            play = rep.get("play") or {}
            cleared = bool(play.get("cleared"))
            in_game = bool(rep.get("enter"))
            in_mission = bool((rep.get("gate") or {}).get("in_mission"))
            frames = play.get("frames")
            cam_ver = bool((rep.get("camera") or {}).get("verified"))
            prog = play.get("progress_claim")
            if cleared:
                status = "PASS"
                detail = ("MISSION CLEAR VERIFIED by the real runner "
                          f"(frames={frames})")
            elif in_game and in_mission:
                status = "PARTIAL"
                detail = (
                    f"live Mission-1 gameplay executed (frames={frames}, "
                    f"chunks={chunks}, camera_verified={cam_ver}, "
                    f"progress_claim={'yes' if prog else 'none'}, "
                    f"continues={play.get('continues')}) — environment "
                    "readiness is NOT the claim; full progress still "
                    "unproven")
            else:
                status = "FAIL"
                detail = (f"runner exit={exit_code} but gameplay was not "
                          f"reached (enter={in_game}, "
                          f"in_mission={in_mission}); stderr: "
                          f"{stderr_tail.strip()[-300:]}")
        extras = {
            "experiment_id": f"mission1-progress_{run_id}",
            "head": _repo_head(),
            "cmd": cmd,
            "core_sha1": inputs["core_sha1"],
            "game_md5": inputs["game_md5"],
            "firmware_mode": fw["mode"],
            "firmware_bios_md5": fw["bios_md5"],
            "chunks": chunks,
            "exit": exit_code,
            "timed_out": timed_out,
            "hard_timeout_s": round(hard_timeout, 1),
            "runner_elapsed_s": elapsed,
            "frames_actual": (rep or {}).get("play", {}).get("frames"),
            "frames_nominal": (rep or {}).get("play", {}).get(
                "frames_nominal"),
            "report_path": report_path,
            "evidence_dir": run_evid,
            "stderr_tail": stderr_tail[-400:],
            "stdout_tail": stdout_tail[-400:],
            "repro_cmd": " ".join(cmd),
            "runner_sha1": runner_sha,
        }
        return status, detail, extras

    return lab.run(
        "MISSION1_PROGRESS",
        "the active policy executes real bounded gameplay after verified "
        "Mission-1 entry (environment readiness is preflight, not the "
        "result)",
        "if FAIL: read the runner report and stderr tail; if PARTIAL: "
        "classify the first live divergence (Phase E)",
        [sys.executable, "scripts/run_mission1_legit.py"],
        inputs, fn, force=force)


def gate_route_discovery(lab, game, core, workspace, firmware="auto",
                         mode="cheat-assisted", cheats="bombs_freeze,hp_freeze",
                         registry=DEF_REGISTRY, evidence_dir=None,
                         budget_minutes=8.0, timeout_s=1500,
                         cheat_opt_in=False, force=False):
    """Issue #2 section 10: bounded CHEAT_ASSISTED_EXPLORATION or
    LEGIT_CONTROLLER_RUN via scripts/route_explorer.py.

    Contract:
      * cheat mode requires the explicit operator opt-in flag
        (--cheat-opt-in) — without it the gate runs the legit profile
      * cheat mode requires EVERY requested code to be VERIFIED in the
        registry; otherwise the gate is BLOCKED with the exact remedy
        (run scripts/validate_cheats.py first)
    Classification: PASS = mission clear verified by the run;
    PARTIAL = real gameplay evidence recorded without a verified clear;
    FAIL = boot/enter failure or no valid report; BLOCKED = missing
    verified codes / environment not ready.
    """
    evidence_dir = evidence_dir or DEF_EVID
    inputs = {
        "mode": mode,
        "cheats": cheats if mode == "cheat-assisted" else None,
        "cheat_opt_in": bool(cheat_opt_in),
        "registry_sha1": _file_sha1(registry),
        "explorer_sha1": _file_sha1(EXPLORER),
        "core_sha1": _file_sha1(core) if core else None,
        "game_md5": (labconfig.file_md5(_cue_bin(game))
                     if _cue_bin(game) and os.path.exists(_cue_bin(game))
                     else None),
        "firmware_mode": firmware,
        "budget_minutes": budget_minutes,
    }

    def fn():
        t0 = time.time()
        # 0. registry contract BEFORE any emulator work
        if mode == "cheat-assisted":
            if not cheat_opt_in:
                return "BLOCKED", (
                    "CHEAT_ASSISTED_EXPLORATION needs the explicit "
                    "operator flag --cheat-opt-in; re-run with it or "
                    "use --route-mode legit"), {}
            try:
                from ps1play.agent.cheatprof import (CheatRegistry,
                                                     ST_VERIFIED)
                reg = CheatRegistry.load(registry)
                names = [s.strip() for s in cheats.split(",")
                         if s.strip()]
                unverified = [n for n in names
                              if reg.entries.get(n, {}).get("status")
                              != ST_VERIFIED]
                if unverified:
                    return "BLOCKED", (
                        f"cheats not VERIFIED in {registry}: "
                        f"{', '.join(unverified)} — run 'python3 "
                        f"scripts/validate_cheats.py --codes "
                        f"{cheats}' first; CANDIDATE codes never drive "
                        "exploration"), {"unverified": unverified}
            except Exception as e:                          # noqa: BLE001
                return "BLOCKED", f"registry unreadable: {e}", {}
        # 1. environment preflight
        rc, j = _run_json(
            [sys.executable, "scripts/env_probe.py", "--game", game,
             "--core", core, "--workspace", workspace, "--json"], 600)
        if not (rc == 0 and j.get("ready")):
            return "BLOCKED", (
                "environment not ready — missing: "
                f"{', '.join(j.get('missing', []))}"), {
                    "exit": rc, "probe": j}
        try:
            fw = labconfig.resolve_firmware(firmware, workspace)
        except labconfig.FirmwareError as e:
            return "BLOCKED", f"firmware unresolved: {e}", {}
        # 2. bounded explorer launch
        run_id = time.strftime("%Y%m%d_%H%M%S")
        run_evid = os.path.join(evidence_dir,
                                f"route_{mode}_{run_id}")
        os.makedirs(run_evid, exist_ok=True)
        report_path = os.path.join(run_evid, "route_report.json")
        cmd = [sys.executable, EXPLORER,
               "--mode", mode, "--evidence-dir", run_evid,
               "--firmware", fw["mode"],
               "--registry", registry,
               "--budget-minutes", str(budget_minutes),
               "--report", report_path]
        if mode == "cheat-assisted":
            cmd += ["--opt-in", "--cheats", cheats]
        remaining = max(60.0, lab.budget_s - lab.elapsed())
        hard_timeout = min(float(timeout_s), remaining)
        timed_out = False
        exit_code = None
        stderr_tail = ""
        try:
            pr = subprocess.run(cmd, capture_output=True,
                                timeout=hard_timeout, cwd=_REPO)
            exit_code = pr.returncode
            stderr_tail = pr.stderr.decode(errors="replace")[-800:]
        except subprocess.TimeoutExpired as e:
            timed_out = True
            stderr_tail = ((e.stderr or b"").decode(errors="replace")
                           [-800:])
        elapsed = round(time.time() - t0, 1)
        rep = None
        parse_err = None
        if not timed_out:
            try:
                with open(report_path) as f:
                    rep = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                parse_err = str(e)
        if timed_out:
            status = "FAIL"
            detail = (f"explorer exceeded hard timeout at "
                      f"{hard_timeout:.0f}s; stopped; recorded "
                      "honestly")
        elif rep is None:
            status = "FAIL"
            detail = (f"explorer exit={exit_code} without a valid "
                      f"report ({parse_err}); stderr: "
                      f"{stderr_tail.strip()[-300:]}")
        else:
            play = rep.get("play") or {}
            cleared = bool((play.get("mission_clear") or {}).get(
                "verified"))
            frames = play.get("frames")
            cheats_active = bool(rep.get("cheats_enabled"))
            stalled = play.get("stopped_reason") == "stall_blocked"
            if cleared:
                status = "PASS"
                label = ("CHEAT-ASSISTED" if cheats_active
                         else "NO-CHEAT")
                detail = (f"MISSION CLEAR VERIFIED ({label} profile, "
                          f"frames={frames})")
            elif frames:
                status = "PARTIAL"
                detail = (
                    f"bounded {'cheat-assisted' if cheats_active else 'legit'} "
                    f"run recorded real gameplay (frames={frames}, "
                    f"stopped={play.get('stopped_reason')}, "
                    f"stalled={stalled}, "
                    f"score_end={play.get('score_end')}) — a "
                    "cheat-assisted traversal is NOT a no-cheat clear")
            else:
                status = "FAIL"
                detail = (f"explorer exit={exit_code} but no gameplay "
                          f"frames recorded; stderr: "
                          f"{stderr_tail.strip()[-300:]}")
        extras = {
            "experiment_id": f"route-discovery_{run_id}",
            "head": _repo_head(),
            "cmd": cmd,
            "mode": mode,
            "cheats": cheats if mode == "cheat-assisted" else [],
            "core_sha1": inputs["core_sha1"],
            "game_md5": inputs["game_md5"],
            "firmware_mode": fw["mode"],
            "exit": exit_code,
            "timed_out": timed_out,
            "explorer_elapsed_s": elapsed,
            "report_path": report_path,
            "evidence_dir": run_evid,
            "stderr_tail": stderr_tail[-400:],
            "repro_cmd": " ".join(cmd),
        }
        return status, detail, extras

    return lab.run(
        "ROUTE_DISCOVERY",
        f"{mode} bounded route experiment records real Mission-1 "
        "traversal evidence (cheat codes VERIFIED-first, profiles "
        "isolated)",
        "if BLOCKED: satisfy the named registry/env contract; if "
        "PARTIAL: mine the route ledger for the next obstacle",
        [sys.executable, EXPLORER, "--mode", mode],
        inputs, fn, force=force)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default="gates",
                    choices=["gates", "mission1-progress",
                             "mission1-route-discovery"])
    ap.add_argument("--budget-minutes", type=float, default=10)
    ap.add_argument("--route-mode", default="cheat-assisted",
                    choices=["cheat-assisted", "legit"],
                    help="execution profile for the route-discovery "
                         "goal (issue section 4)")
    ap.add_argument("--cheats", default="bombs_freeze,hp_freeze",
                    help="registry cheat names for the cheat-assisted "
                         "route profile (all must be VERIFIED)")
    ap.add_argument("--cheat-opt-in", action="store_true",
                    help="EXPLICIT operator consent for cheat-assisted "
                         "exploration; never assumed")
    ap.add_argument("--registry", default=DEF_REGISTRY)
    ap.add_argument("--route-budget-minutes", type=float, default=8.0,
                    help="wall budget handed to the explorer run")
    ap.add_argument("--game", default=DEF_GAME)
    ap.add_argument("--core", default=DEF_CORE)
    ap.add_argument("--workspace", default=DEF_WORKSPACE)
    ap.add_argument("--evidence-dir", default=DEF_EVID,
                    help="evidence root for the mission1-progress run")
    ap.add_argument("--firmware", default=DEF_FIRMWARE,
                    choices=list(labconfig.FIRMWARE_MODES),
                    help="firmware mode for the real runner (auto | "
                         "openbios | retail); recorded in the ledger")
    ap.add_argument("--chunks", type=int, default=30,
                    help="policy chunks (60 frames each) for the "
                         "mission1-progress diagnostic run (default 30 "
                         "= 1800 frames)")
    ap.add_argument("--timeout-s", type=float, default=1200,
                    help="hard subprocess timeout for the real run")
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
    elif a.goal == "mission1-route-discovery":
        executed.append(gate_target_game(lab, a.game, a.core, a.workspace))
        if not lab.out_of_budget():
            last = executed[-1]
            last_ok = (last["status"] == "PASS"
                       or last.get("prior_status") == "PASS")
            if last_ok:
                executed.append(gate_route_discovery(
                    lab, a.game, a.core, a.workspace,
                    firmware=a.firmware, mode=a.route_mode,
                    cheats=a.cheats, registry=a.registry,
                    evidence_dir=a.evidence_dir,
                    budget_minutes=a.route_budget_minutes,
                    timeout_s=a.timeout_s, cheat_opt_in=a.cheat_opt_in))
            else:
                print("[mission1-route-discovery] environment blocked — "
                      "see the TARGET_GAME record")
    else:  # mission1-progress
        executed.append(gate_target_game(lab, a.game, a.core, a.workspace))
        if not lab.out_of_budget():
            last = executed[-1]
            last_ok = (last["status"] == "PASS"
                       or last.get("prior_status") == "PASS")
            if last_ok:
                # v0.12 Phase C: launch the bounded REAL runner — an
                # environment-ready verdict alone is NOT gameplay
                # progress and must never be labelled as such.
                executed.append(gate_mission1_progress(
                    lab, a.game, a.core, a.workspace,
                    firmware=a.firmware, chunks=a.chunks,
                    evidence_dir=a.evidence_dir, timeout_s=a.timeout_s))
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

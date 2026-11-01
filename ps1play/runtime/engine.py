"""ps1play.runtime.engine — the autonomous play loop (R62).

RuntimeEngine owns the COMPLETE lifecycle the mission requires:

    preflight (assets+hashes) -> boot -> ready -> per episode:
        adapter.reset / policy.reset / controller.reset
        episode start (seed k)
        loop: capture -> observe -> decide -> controller send
              -> advance -> post-advance scoring/terminal
        -> EpisodeResult -> persist -> restart policy
    -> shutdown (release inputs, close emulator, close telemetry)

Guarantees:
  * frame/action association: decision N is made on the frame captured
    after decision N-1's input; the controller rejects re-sends; the
    post-advance scoring frame is captured fresh after the advance.
  * trace hash byte-compatibility with R61: sha256 over
    (values.tobytes() + action.encode()) per step — identical to
    r61e_deploy_loop, so traces can be compared across implementations.
  * every failure is a typed Ps1RuntimeError; cleanup ALWAYS runs
    (controller release, emulator close, telemetry close); the failure
    is persisted (episode record + JSONL event) with the exit code.
  * safety limits per episode: max frames, wall-clock, and the global
    run limits in RestartPolicy; emergency stop via a shared flag or
    SIGINT (the CLI installs the handler).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from .config import RuntimeConfig
from .controller import SafetyController
from .errors import (AssetError, EmulatorError, EmergencyStop,
                     FrameError, Ps1RuntimeError, RuntimePolicyError)
from .lifecycle import (Lifecycle, RestartPolicy, StopWatch,
                        raise_if_stopped)
from .policy_runtime import RuntimePolicy
from .registry import adapter_for_game
from .session import EnvSession, preflight, resolve_iso
from .telemetry import TelemetryLog, build_manifest, manifest_sha


class RuntimeEngine:
    def __init__(self, config: RuntimeConfig, telemetry: TelemetryLog,
                 stop_flag: Optional[Dict[str, Any]] = None):
        self.cfg = config
        self.tel = telemetry
        self.stop_flag = stop_flag if stop_flag is not None else {}
        self.lifecycle = Lifecycle(telemetry)
        self.session: Optional[EnvSession] = None
        self.adapter = None
        self.policy: Optional[RuntimePolicy] = None
        self.controller: Optional[SafetyController] = None
        self.manifest: Dict[str, Any] = {}
        self.manifest_hash: str = ""
        self.results: List[Dict[str, Any]] = []
        self._closed = False

    # ------------------------------------------------------------ --
    # preflight + boot
    # ------------------------------------------------------------ --
    def preflight(self) -> Dict[str, Any]:
        self.lifecycle.transition("BOOTING", reason="preflight")
        iso = resolve_iso(self.cfg)
        try:
            assets = preflight(self.cfg, iso_path=iso,
                               require_model=False)
        except Ps1RuntimeError:
            raise
        self.tel.emit("preflight", **{k: (v[:16] if isinstance(v, str)
                                          and len(v) == 64 else v)
                                      for k, v in assets.items()})
        self.manifest = build_manifest(
            self.cfg, iso_path=assets["iso_path"],
            core_path=assets["core_path"], bios_path=assets["bios_path"])
        self.manifest_hash = manifest_sha(self.manifest)
        man_path = os.path.join(self.cfg.output_dir,
                                "runtime_manifest.json")
        with open(man_path, "w") as f:
            json.dump(self.manifest, f, indent=1, default=str)
        self.tel.emit("manifest", sha256=self.manifest_hash,
                      path=man_path)
        return assets

    def boot(self, assets: Dict[str, Any]) -> None:
        self.session = EnvSession.boot_new(
            self.cfg, deadline_s=self.cfg.boot_timeout_s,
            telemetry=self.tel)
        self.tel.emit("emulator_boot", tag=self.session.tag(),
                      boot_info=str(self.session.boot_info)[:200])
        self.adapter = adapter_for_game(self.cfg.game,
                                        self.session.env,
                                        telemetry=self.tel)
        self.policy = RuntimePolicy(self.cfg, telemetry=self.tel)
        self.controller = SafetyController(self.adapter, self.session,
                                           telemetry=self.tel)
        self.tel.emit("policy_loaded", **self.policy.identity())
        self.adapter.wait_ready(self.cfg.ready_timeout_s)
        self.lifecycle.transition("READY", reason="game ready")
        self.tel.emit("ready", game=self.cfg.game)

    # ------------------------------------------------------------ --
    # the episode loop
    # ------------------------------------------------------------ --
    def run(self) -> List[Dict[str, Any]]:
        """Run all episodes per the restart policy. Returns the result
        list. Raises only on uncontainerable errors (cleanup already
        done by close())."""
        restart = RestartPolicy(
            max_episodes=self.cfg.episodes or 0,
            time_limit_s=self.cfg.max_runtime_s,
            max_consecutive_failures=self.cfg.max_consecutive_failures)
        # defensive: the manifest must exist for every run (preflight
        # writes it; runs assembled programmatically may not have)
        man_path = os.path.join(self.cfg.output_dir,
                                "runtime_manifest.json")
        if self.manifest and not os.path.exists(man_path):
            with open(man_path, "w") as f:
                json.dump(self.manifest, f, indent=1, default=str)
        episode_no = 0
        while True:
            ok, reason = restart.should_continue()
            if not ok:
                self.tel.emit("run_stop", reason=reason)
                break
            raise_if_stopped(self.stop_flag)
            episode_no += 1
            seed_k = self.cfg.seed_for_episode(episode_no)
            try:
                result = self._run_one_episode(episode_no, seed_k,
                                               restart)
                restart.record(failed=(result["result"] == "error"))
                self.results.append(result)
                self._persist_result(result)
            except EmergencyStop as e:
                self._record_interrupted(episode_no, seed_k, str(e))
                self._safe_cleanup(reason=f"emergency stop: {e}")
                self.tel.emit("run_stop", reason="emergency stop")
                break
            except Ps1RuntimeError as e:
                # episode-level failure: persist + decide
                self.tel.emit("episode_error",
                              episode=episode_no, seed_k=seed_k,
                              error=type(e).__name__, detail=str(e))
                rec = self._failure_record(episode_no, seed_k, e)
                restart.record(failed=True)
                self.results.append(rec)
                self._persist_result(rec)
                if self.lifecycle.state == "EPISODE_ACTIVE":
                    self.lifecycle.transition("EPISODE_END",
                                              reason="failure")
                if self.cfg.stop_on_error:
                    self.tel.emit("run_stop",
                                  reason="stop_on_error after failure")
                    break
        self.lifecycle.transition("STOPPING", reason="run complete")
        self._safe_cleanup(reason="run complete")
        if self.lifecycle.state == "STOPPING":
            self.lifecycle.transition("STOPPED")
        return self.results

    def _run_one_episode(self, episode_no: int, seed_k: int,
                         restart: Optional[RestartPolicy] = None) \
            -> Dict[str, Any]:
        lc = self.lifecycle
        if lc.state == "EPISODE_END":          # back for another one
            lc.transition("READY", reason="next episode")
        lc.require("READY")
        lc.transition("EPISODE_ACTIVE", reason=f"episode {episode_no}")
        # -- per-episode resets (no stale state) --
        self.adapter.reset_episode()
        self.policy.reset()
        self.controller.reset_episode()
        t0 = time.time()
        trace = hashlib.sha256()
        errors: List[str] = []
        frames = flaps = 0
        steps = 0
        result, death = "unknown", None
        trace_rows: List[List[Any]] = []
        shot_paths: List[str] = []
        video_path = None
        try:
            self.adapter.start_episode(seed_k)
            src = self.session.frames()
            # per-episode wall limit = the REMAINING run budget (the
            # run limit is global; an episode can never outlive it)
            ep_budget = self.cfg.max_runtime_s
            if restart is not None:
                ep_budget = min(ep_budget,
                                max(0.01, restart.time_left_s()))
            watch = StopWatch(ep_budget)
            budget = self.cfg.max_frames_per_episode
            recorder = self._make_recorder(episode_no, seed_k)
            # The frame the FIRST decision observes: rendered by the
            # start sequence (one capture per emulator advance — the
            # post-advance frame of step t IS the observation frame of
            # step t+1, exactly like the R61 record loop).
            frame = src.latest(require_fresh=False)
            for step in range(budget):
                raise_if_stopped(self.stop_flag)
                if watch.expired():
                    result, death = "stopped", "time_limit"
                    self.tel.emit("episode_stop", episode=episode_no,
                                  reason="time limit")
                    break
                # 1) perceive the current frame
                t = time.perf_counter()
                obs = self.adapter.observe(frame)
                self.tel.latency("perception_ms",
                                 (time.perf_counter() - t) * 1000)
                if not obs.valid:
                    raise AdapterError(
                        f"invalid observation at {obs.frame_id}: "
                        f"{obs.invalid_reason}")
                # 2) decide
                decision = self.policy.predict(obs)
                # 3) update adapter history (exact deployed semantics)
                self.adapter.note_action(decision, obs)
                # 4) act: input for exactly one frame
                self.controller.apply(decision, frame)
                # 5) capture the frame AFTER the action (must be new)
                nf = src.latest(require_fresh=True)
                # 6) score/terminal on the post-action frame
                post = self.adapter.post_advance(nf)
                if decision.action == "FLAP":
                    flaps += 1
                steps += 1
                frames = steps
                # trace hash — byte-compatible with r61e_deploy_loop
                trace.update(obs.values.tobytes())
                trace.update(decision.action.encode())
                if self.cfg.record:
                    trace_rows.append(
                        [int(step),
                         [float(v) for v in obs.values],
                         decision.action])
                if recorder is not None:
                    recorder.maybe(step, frame, nf, obs, decision, post)
                if post.get("terminal"):
                    result, death = "death", post.get("death_reason") \
                        or "game_over"
                    self.tel.emit("terminal", episode=episode_no,
                                  steps=steps, pipes=post.get("pipes"),
                                  reason=death)
                    break
                if self.cfg.verbose and steps % \
                        max(1, self.cfg.status_every_frames) == 0:
                    self._print_status(episode_no, seed_k, steps,
                                       budget, post, decision)
                # the post-action frame is the next decision's input
                frame = nf
            else:
                result = "alive"     # budget exhausted without death
                death = "budget"
            if recorder is not None:
                video_path = recorder.finish(
                    self.adapter, steps, result, shot_paths)
                shot_paths = recorder.shots
        except EmergencyStop:
            self.controller.release_all()
            raise
        except Ps1RuntimeError as e:
            result = "error"
            death = type(e).__name__
            errors.append(f"{type(e).__name__}: {e}")
            self.controller.release_all()   # no button stays latched
            raise
        except Exception as e:
            # ANY unexpected failure becomes a typed runtime error —
            # nothing raw escapes the decision loop
            self.controller.release_all()
            raise EmulatorError(
                f"decision loop failed at step {steps}: "
                f"{type(e).__name__}: {e}")
        ended = time.time()
        stats = self.adapter.episode_stats() \
            if self.adapter is not None else {}
        rec = {
            "episode": episode_no, "game": self.cfg.game,
            "seed_k": seed_k, "rep": 0,
            "result": result, "death_reason": death,
            "pipes": int(stats.get("pipes", 0)),
            "frames": int(frames),
            "flaps": int(stats.get("actions", 0)),
            "actions": int(stats.get("actions", 0)),
            "decisions": int(stats.get("decisions", steps)),
            "errors": errors,
            "wall_s": round(ended - t0, 2),
            "started_ts": round(t0, 3), "ended_ts": round(ended, 3),
            "trace_sha256": trace.hexdigest(),
            "policy_name": self.policy.identity()["name"],
            "policy_sha256": self.policy.identity()["model_sha256"],
            "manifest_sha256": self.manifest_hash,
            "emulator_tag": self.session.tag(),
            "screenshots": shot_paths, "video": video_path,
            "trace_file": None,
        }
        if self.cfg.record and trace_rows:
            rec["trace_file"] = self._write_trace(episode_no, seed_k,
                                                  trace_rows)
        lc.transition("EPISODE_END", reason=f"{result} at {steps}f")
        self.tel.emit("episode_end", **{k: rec[k] for k in
                                        ("episode", "seed_k", "result",
                                         "death_reason", "pipes",
                                         "frames", "flaps", "actions",
                                         "decisions",
                                         "trace_sha256", "wall_s")})
        self.tel.flush()
        return rec

    def _record_interrupted(self, episode_no: int, seed_k: int,
                            reason: str) -> None:
        """Persist a record for an episode interrupted by an emergency
        stop, so the evidence trail shows the interruption."""
        rec = self._failure_record(episode_no, seed_k,
                                   EmergencyStop(reason))
        rec["result"] = "stopped"
        rec["death_reason"] = "emergency_stop"
        self.results.append(rec)
        self._persist_result(rec)
        if self.lifecycle.state == "EPISODE_ACTIVE":
            self.lifecycle.transition("EPISODE_END",
                                      reason="emergency stop")

    def _failure_record(self, episode_no: int, seed_k: int,
                        err: Ps1RuntimeError) -> Dict[str, Any]:
        stats = self.adapter.episode_stats() \
            if self.adapter is not None else {}
        return {
            "episode": episode_no, "game": self.cfg.game,
            "seed_k": seed_k, "rep": 0,
            "result": "error", "death_reason": type(err).__name__,
            "pipes": int(stats.get("pipes", 0)),
            "frames": int(stats.get("decisions", 0)),
            "flaps": int(stats.get("actions", 0)),
            "actions": int(stats.get("actions", 0)),
            "decisions": int(stats.get("decisions", 0)),
            "errors": [f"{type(err).__name__}: {err}"],
            "wall_s": 0.0,
            "started_ts": round(time.time(), 3),
            "ended_ts": round(time.time(), 3),
            "trace_sha256": "", "policy_name": "?", "policy_sha256": "",
            "manifest_sha256": self.manifest_hash,
            "emulator_tag": self.session.tag() if self.session else "?",
            "screenshots": [], "video": None, "trace_file": None,
        }

    def _persist_result(self, rec: Dict[str, Any]) -> None:
        path = os.path.join(self.cfg.output_dir, "episodes.jsonl")
        try:
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            summary = os.path.join(self.cfg.output_dir,
                                   f"episode_{rec['episode']:03d}.json")
            with open(summary, "w") as f:
                json.dump(rec, f, indent=1)
        except OSError as e:
            self.tel.emit("persist_error", error=str(e))

    def _write_trace(self, episode_no: int, seed_k: int,
                     rows: List[List[Any]]) -> str:
        path = os.path.join(self.cfg.output_dir,
                            f"trace_ep{episode_no:03d}_k{seed_k}.jsonl")
        with open(path, "w") as f:
            for s, v, a in rows:
                f.write(json.dumps({"step": s, "x": v, "a": a}) + "\n")
        return path

    # ------------------------------------------------------------ --
    # observability helpers
    # ------------------------------------------------------------ --
    def _make_recorder(self, episode_no: int, seed_k: int):
        if not (self.cfg.record or self.cfg.screenshot):
            return None
        from .recorder import Recorder  # noqa: PLC0415
        return Recorder(self.cfg, self.session, episode_no, seed_k,
                        self.tel)

    def _print_status(self, ep, k, steps, budget, post, decision) \
            -> None:
        snap = self.adapter.snapshot()
        print(f"[ep{ep} k={k}] {steps}/{budget}f "
              f"pipes={post.get('pipes')} bird_y="
              f"{snap.get('bird_y')} gap={snap.get('gap_center')} "
              f"act={decision.action} "
              f"cap={self.session.frames().capture_latency_ms():.1f}ms",
              flush=True)

    # ------------------------------------------------------------ --
    # cleanup
    # ------------------------------------------------------------ --
    def _safe_cleanup(self, reason: str = "") -> None:
        if self.controller is not None:
            try:
                self.controller.release_all()
            except Exception:
                pass
        if self.policy is not None:
            self.policy.close()
            self.policy = None
        if self.session is not None:
            self.tel.emit("emulator_close", reason=reason,
                          tag=self.session.tag())
            self.session.close()
            self.session = None
        self.tel.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self.lifecycle.in_terminal():
            if self.lifecycle.state != "STOPPING":
                self.lifecycle.transition("STOPPING",
                                          reason="engine.close")
            self._safe_cleanup(reason="engine.close")
            self.lifecycle.transition("STOPPED")
        self.tel.emit("engine_close", results=len(self.results))
        self.tel.close()

"""dataset.py — episode-structured experience with provenance.

Storage layout (LOCAL, gitignored under scratch/learn_datasets/):

  <root>/manifest.json                 dataset-level metadata + file index
  <root>/ep_<id>.npz                   one episode: frames + labels + actions
  <root>/ep_<id>.json                  per-episode metadata (provenance)

Each episode record stores:
  * frames: uint8 gray, downsampled (game-specific geometry), one row per
    CAPTURED frame (references, not duplicates)
  * actions: the legal action actually sent (agent or teacher)
  * teacher_action: what the teacher would do on this state (DAgger relabel)
  * labels: dict name -> value, each carrying a ROLE (observations.py);
    roles live in the episode json (field table), values in the npz
  * outcome: score/progress/failure_type/result
  * scenario: seed / perturbation id (split key — NEVER split frames of
    one episode across train/test)
"""
import hashlib
import json
import os
import time

import numpy as np

from ps1play.learn.observations import (DIAGNOSTIC_ONLY, EVALUATION_ONLY,
                                        TEACHER_LABEL, VISUAL_INPUT)

FRAME_DTYPE = np.uint8


class EpisodeRecord:
    """In-memory episode builder; freeze() writes the npz + json pair."""

    def __init__(self, game, mode, episode_id, scenario, field_table,
                 frame_shape, note=""):
        assert mode in ("explore_assisted", "collect_teacher_data",
                        "train_student", "evaluate_visual_only",
                        "play_visual_only")
        self.game = game
        self.mode = mode
        self.episode_id = episode_id
        self.scenario = str(scenario)
        self.field_table = list(field_table)          # list[dict]
        self.frame_shape = tuple(frame_shape)
        self.note = note
        self.t0 = time.time()
        self.frames = []            # uint8 gray downsampled
        self.actions = []           # str per control step
        self.teacher_actions = []   # str or "" per control step
        self.step_labels = []       # dict name -> value per control step
        self.events = []            # json events (serves, points, deaths)
        self.outcome = {}

    # ---- collection API ----
    def add_frame(self, gray):
        assert gray.dtype == FRAME_DTYPE and gray.shape == self.frame_shape
        self.frames.append(gray)

    def add_step(self, action, teacher_action="", labels=None):
        self.actions.append(str(action))
        self.teacher_actions.append(str(teacher_action or ""))
        self.step_labels.append(dict(labels or {}))

    def add_event(self, **ev):
        ev["t_rel"] = round(time.time() - self.t0, 3)
        self.events.append(ev)

    def set_outcome(self, **kw):
        self.outcome.update(kw)

    # ---- persistence ----
    def freeze(self, root, extra_meta=None):
        os.makedirs(root, exist_ok=True)
        n = len(self.frames)
        meta = {
            "game": self.game, "mode": self.mode,
            "episode_id": self.episode_id, "scenario": self.scenario,
            "field_table": self.field_table,
            "frame_shape": list(self.frame_shape),
            "n_steps": n, "note": self.note,
            "duration_s": round(time.time() - self.t0, 2),
            "outcome": self.outcome,
            "events": self.events,
            "extra_meta": extra_meta or {},
        }
        npz_path = os.path.join(root, f"ep_{self.episode_id}.npz")
        np.savez_compressed(
            npz_path,
            frames=np.asarray(self.frames, dtype=FRAME_DTYPE),
            actions=np.asarray(self.actions, dtype="<U8"),
            teacher_actions=np.asarray(self.teacher_actions, dtype="<U8"),
            labels_json=json.dumps(self.step_labels),
        )
        meta["npz_sha256"] = _sha256(npz_path)
        js_path = os.path.join(root, f"ep_{self.episode_id}.json")
        with open(js_path, "w") as f:
            json.dump(meta, f, indent=2)
        return js_path

    # ---- loading ----
    @classmethod
    def load(cls, root, episode_id):
        js_path = os.path.join(root, f"ep_{episode_id}.json")
        with open(js_path) as f:
            meta = json.load(f)
        npz = np.load(os.path.join(root, f"ep_{episode_id}.npz"))
        return meta, npz


class LearningDataset:
    """Episode-level index with splits BY EPISODE (never by frame)."""

    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.manifest_path = os.path.join(root, "manifest.json")
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {"created": time.time(), "episodes": [],
                             "config": {}}

    def register(self, episode_id, meta):
        entry = {"episode_id": episode_id, "game": meta["game"],
                 "mode": meta["mode"], "scenario": meta["scenario"],
                 "n_steps": meta["n_steps"], "outcome": meta["outcome"],
                 "split": meta.get("split", "unassigned"),
                 "npz_sha256": meta["npz_sha256"]}
        self.manifest["episodes"] = [
            e for e in self.manifest["episodes"]
            if e["episode_id"] != episode_id]
        self.manifest["episodes"].append(entry)
        self.save()

    def save(self):
        self.manifest["updated"] = time.time()
        with open(self.manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=2)

    def episodes(self, split=None, mode=None, game=None):
        out = []
        for e in self.manifest["episodes"]:
            if split and e["split"] != split:
                continue
            if mode and e["mode"] != mode:
                continue
            if game and e["game"] != game:
                continue
            out.append(e)
        return out

    def assign_splits(self, train_ids, val_ids, test_ids):
        for e in self.manifest["episodes"]:
            eid = e["episode_id"]
            e["split"] = ("train" if eid in train_ids
                          else "val" if eid in val_ids
                          else "test" if eid in test_ids
                          else e.get("split", "unassigned"))
        self.save()

    def concat_features(self, episodes, feature_fn, label_names,
                        role_map):
        """Build (X, Y, meta) matrices from loaded episodes.

        feature_fn(meta, npz, step_idx) -> 1-D float vector built ONLY
        from policy-legal fields.  label_names maps matrix columns to
        label keys; role_map[label_key] must be TEACHER_LABEL (or
        EVALUATION_ONLY for regression targets used in training only).

        Raises if any requested label is not a legal training target.
        """
        for k in label_names:
            role = role_map.get(k)
            if role not in (TEACHER_LABEL, EVALUATION_ONLY,
                            DIAGNOSTIC_ONLY, VISUAL_INPUT):
                raise ValueError(f"label {k!r} has illegal role {role!r}")
        X, Y, metas = [], [], []
        for eid in episodes:
            meta, npz = EpisodeRecord.load(self.root, eid)
            labels = json.loads(str(npz["labels_json"]))
            for i in range(meta["n_steps"]):
                X.append(feature_fn(meta, npz, i, labels[i]))
                Y.append([labels[i].get(k) for k in label_names])
                metas.append({"episode_id": eid, "step": i})
        return (np.asarray(X, dtype=np.float32),
                np.asarray(Y, dtype=np.float32), metas)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dataset_digest(root):
    """Stable digest over episode json+npz hashes (train-set freezing)."""
    h = hashlib.sha256()
    for name in sorted(os.listdir(root)):
        if name.endswith((".json", ".npz")) and name != "manifest.json":
            h.update(name.encode())
            h.update(_sha256(os.path.join(root, name)).encode())
    return h.hexdigest()

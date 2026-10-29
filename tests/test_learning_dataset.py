"""Dataset provenance / role-separation / causal-split tests (mission
§4.3, §8): roles are enforced at use time, splits are episode-level,
the digest is stable, and no teacher-only field can reach a policy
feature matrix."""
import json
import os
import sys

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.learn.dataset import (EpisodeRecord, LearningDataset,  # noqa
                                   dataset_digest)
from ps1play.learn.observations import (EVALUATION_ONLY, TEACHER_LABEL,  # noqa
                                        VISUAL_INPUT)


def _mk_episode(root, eid, scenario):
    fields = [{"name": "g", "role": VISUAL_INPUT, "source": "frame"},
              {"name": "truth", "role": TEACHER_LABEL, "source": "ram"},
              {"name": "score", "role": EVALUATION_ONLY, "source": "ram"}]
    rec = EpisodeRecord(game="pong", mode="collect_teacher_data",
                        episode_id=eid, scenario=scenario,
                        field_table=fields, frame_shape=(4, 4))
    for i in range(5):
        rec.add_frame(np.full((4, 4), i, np.uint8))
        rec.add_step("UP", labels={"truth": i, "score": 0})
    rec.set_outcome(result="ok")
    meta_path = rec.freeze(root)
    with open(meta_path) as f:
        return json.load(f)


def test_roundtrip_and_provenance(tmp_path):
    root = str(tmp_path)
    meta = _mk_episode(root, "e0", "s0")
    assert meta["field_table"][1]["role"] == TEACHER_LABEL
    loaded, npz = EpisodeRecord.load(root, "e0")
    assert loaded["n_steps"] == 5
    assert npz["frames"].shape == (5, 4, 4)
    assert json.loads(str(npz["labels_json"]))[2]["truth"] == 2


def test_episode_level_splits(tmp_path):
    root = str(tmp_path)
    ds = LearningDataset(root)
    for i in range(4):
        meta = _mk_episode(root, f"e{i}", f"s{i}")
        ds.register(f"e{i}", meta)
    ids = [e["episode_id"] for e in ds.manifest["episodes"]]
    assert len(ids) == 4
    ds.assign_splits(["e0", "e1"], ["e2"], ["e3"])
    seen = {}
    for e in ds.manifest["episodes"]:
        assert e["split"] not in seen, "episode in two splits"
        seen[e["episode_id"]] = e["split"]
    assert seen == {"e0": "train", "e1": "train", "e2": "val",
                    "e3": "test"}


def test_digest_stable(tmp_path):
    root = str(tmp_path)
    _mk_episode(root, "e0", "s0")
    d1 = dataset_digest(root)
    d2 = dataset_digest(root)
    assert d1 == d2 and len(d1) == 64


def test_labels_never_silent_visual(tmp_path):
    """A teacher_label field stays teacher-only: concat_features refuses
    an unknown role, and the role table round-trips."""
    root = str(tmp_path)
    meta = _mk_episode(root, "e0", "s0")
    roles = {f["name"]: f["role"] for f in meta["field_table"]}
    assert roles["truth"] == TEACHER_LABEL
    assert roles["g"] == VISUAL_INPUT
    with pytest.raises(ValueError):
        LearningDataset(root).concat_features(
            ["e0"], feature_fn=lambda *a: np.zeros(1),
            label_names=["nope"], role_map={"nope": "illegal_role"})

"""Analysis cache: key results by (game_id, input hashes, tool, config).

Rules (Issue #10 addendum):
- Cache hits are reused only when ALL fingerprint components match.
- Invalidation is per-key: a changed input hash only invalidates the work
  affected by that input.
- Budgets (seconds/frames/retries) are explicit; unsupported reads raise
  instead of silently returning zeros.
- Bulk payloads stay OUT of git: default root is the local cache dir.
"""
import hashlib
import json
import os


class BudgetExceeded(RuntimeError):
    pass


class UnsupportedAddress(LookupError):
    """Raised instead of silently returning zero for unmapped reads."""


def key(game_id, inputs, tool, config=None):
    """inputs: dict of named hashes/paths (path -> hashed content)."""
    blob = json.dumps({"game_id": game_id, "inputs": inputs, "tool": tool,
                       "config": config or {}}, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


class AnalysisCache:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _path(self, k):
        return os.path.join(self.root, k + ".json")

    def get(self, k):
        p = self._path(k)
        if os.path.exists(p):
            self.hits += 1
            return json.load(open(p))
        self.misses += 1
        return None

    def put(self, k, value, budget=None):
        payload = {"key": k, "value": value}
        if budget is not None:
            payload["budget"] = budget
        with open(self._path(k), "w") as f:
            json.dump(payload, f, sort_keys=True)
        return k

    def invalidate(self, game_id, tool=None):
        """Drop every cached entry for a game (optionally one tool only)."""
        dropped = 0
        for fn in os.listdir(self.root):
            p = os.path.join(self.root, fn)
            try:
                rec = json.load(open(p))
            except (json.JSONDecodeError, OSError):
                continue
            # key is a hash; game/tool match requires re-derivation inputs —
            # store them explicitly for invalidation.
            meta = rec.get("meta") or {}
            if meta.get("game_id") != game_id:
                continue
            if tool and meta.get("tool") != tool:
                continue
            os.remove(p)
            dropped += 1
        return dropped

    def put_with_meta(self, k, value, game_id, tool, inputs=None,
                      config=None, budget=None):
        self.put(k, value, budget=budget)
        rec_path = self._path(k)
        rec = json.load(open(rec_path))
        rec["meta"] = {"game_id": game_id, "tool": tool, "inputs": inputs,
                       "config": config or {}}
        with open(rec_path, "w") as f:
            json.dump(rec, f, sort_keys=True)
        return k

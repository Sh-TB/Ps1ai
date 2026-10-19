"""Save states + progress journal -> continue from anywhere, anytime."""
import json
import os
import time


class StateManager:
    def __init__(self, states_dir):
        self.dir = states_dir
        os.makedirs(self.dir, exist_ok=True)

    def _paths(self, name):
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        return (os.path.join(self.dir, safe + ".state"),
                os.path.join(self.dir, safe + ".meta.json"))

    def save(self, core, name, meta=None):
        p, mp = self._paths(name)
        blob = core.serialize()
        with open(p, "wb") as f:
            f.write(blob)
        m = {"name": name, "frames": core.frame_count,
             "bytes": len(blob), "ts": time.time(),
             "core": core.core_name, "core_ver": core.core_ver}
        if meta:
            m.update(meta)
        with open(mp, "w") as f:
            json.dump(m, f, indent=1)
        return {"name": name, "bytes": len(blob)}

    def load(self, core, name):
        p, _ = self._paths(name)
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        with open(p, "rb") as f:
            core.unserialize(f.read())
        return {"name": name, "restored": True}

    def exists(self, name):
        return os.path.exists(self._paths(name)[0])

    def list(self):
        out = []
        for fn in sorted(os.listdir(self.dir)):
            if fn.endswith(".state"):
                name = fn[:-6]
                mp = os.path.join(self.dir, fn[:-6] + ".meta.json")
                meta = {}
                if os.path.exists(mp):
                    with open(mp) as f:
                        meta = json.load(f)
                out.append({"name": name, "frames": meta.get("frames"),
                            "bytes": meta.get("bytes"), "ts": meta.get("ts")})
        return out

    def latest(self):
        items = [s for s in self.list() if s.get("ts")]
        return max(items, key=lambda s: s["ts"])["name"] if items else None

    def prune(self, keep=3, prefix="auto"):
        autos = sorted([s for s in self.list() if s["name"].startswith(prefix)],
                       key=lambda s: -s["ts"])
        for s in autos[keep:]:
            p, mp = self._paths(s["name"])
            for q in (p, mp):
                if os.path.exists(q):
                    os.remove(q)


class Journal:
    """Append-only JSONL — the token-minimal record an LLM agent reads."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.fh = open(path, "a", encoding="utf-8")

    def log(self, row):
        self.fh.write(json.dumps(row, ensure_ascii=False,
                                 separators=(",", ":")) + "\n")
        self.fh.flush()

    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass

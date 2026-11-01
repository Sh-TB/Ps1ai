"""ps1play.runtime.session — emulator lifecycle + frame source (R62).

`EnvSession` wraps a game "env object" (the proven `ps1play.learn.games`
wrappers — beetle PSX via ctypes, in-process, headless) behind the
runtime's `Emulator`/`FrameSource` contracts:

  * preflight: ISO + hash, core binary, BIOS — fail-early AssetError
  * boot with a wall-clock deadline and firmware trust check
  * ordered frame capture: every `latest()` returns a `Frame` with a
    monotonic seq, the core's own rendered-frame counter, a timestamp,
    and a staleness flag (frames_run unchanged since the last capture
    == nothing new was rendered)
  * `advance()` forwards to the core's run(frames, buttons)
  * crash detection: any core exception marks the session dead and is
    re-raised as EmulatorError
  * `close()` is idempotent; the core is in-process so there are no
    child processes to leak — `close()` unloads the game and deinit's
    the libretro core (verified by the reuse test that a second boot
    works in the same process afterwards)
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import numpy as np

from .errors import AssetError, EmulatorError, FrameError
from .interfaces import Emulator, Frame, FrameSource, check_frame_shape
from .telemetry import sha256_file

# The committed OpenBIOS used by every learning boot.
BIOS_SRC = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "third_party",
    "openbios", "openbios.bin")


# Per-game default disc (cue preferred). Registered games add their
# entry here (R64: tetrade) — the map IS the registry's disc column.
GAME_DEFAULT_ISO = {
    "flappybird": os.path.join("/home/z/my-project/emu/games_homebrew",
                               "flappybird.cue"),
    "tetrade": os.path.join("/home/z/my-project/emu/games_homebrew",
                            "patched", "tetrade_lic.cue"),
    "buzzybee": os.path.join("/home/z/my-project/emu/games_homebrew",
                             "patched", "buzzybee_ntsc_lic.cue"),
    # R66: the owner's lawful local retail copy (NEVER committed to
    # the repository); the pin is the exact bytes every MSX record
    # was made with.
    "metal_slug_x": os.path.join("/home/z/my-project/emu", "game",
                                 "Metal Slug X (USA).cue"),
}

# The exact disc bytes every record was made with (R64: the
# license-patched Tetrade image, sha256 over TETRADE_lic.bin; R65: the
# wrapped BuzzyBee NTSC disc, sha256 over buzzybee_ntsc_lic.bin —
# rebuilt byte-identical by scripts/r30t0_buzzybee_asset.py).
EXPECTED_ISO_SHA = {
    "flappybird": "b45871d32c7910784b26128c3f4ed48d181e31dfd693f4e5efa"
                  "187cf2296f0ed",
    "tetrade": "7eb38eda1274b6c2dba81dc490598d5b8a9e683025a0afd604ec"
               "130d063c3cc1",
    "buzzybee": "042b94bb29907e75b4eadd0699619eb770089bf8880adf31f26bc"
                "c591a1bb093",
    "metal_slug_x": "45cde149878fe945d0219fd0f61ca09856aee66bdcc9119d"
                    "e21c0583f1d0667d",
}


def resolve_iso(config) -> str:
    """The disc path for the configured game (cue preferred)."""
    if config.iso_path:
        return config.iso_path
    default = GAME_DEFAULT_ISO.get(config.game)
    if default is None:
        raise AssetError(
            f"no default ISO registered for game {config.game!r}")
    return default


def disc_image_path(disc_path: str) -> str:
    """Resolve a .cue to the actual binary image it references (hashes
    must be computed over the IMAGE, not the cue text)."""
    if not disc_path.lower().endswith(".cue"):
        return disc_path
    import re
    with open(disc_path) as f:
        m = re.search(r'FILE\s+"([^"]+)"\s+BINARY', f.read(),
                      flags=re.IGNORECASE)
    if not m:
        raise AssetError(f"cue has no FILE entry: {disc_path}")
    img = os.path.normpath(os.path.join(os.path.dirname(disc_path),
                                        m.group(1)))
    if not os.path.exists(img):
        raise AssetError(f"cue references a missing image: {img}")
    return img


def preflight(config, *, iso_path: str,
              require_model: bool = True) -> Dict[str, Any]:
    """Fail-early asset validation. Returns the resolved asset table."""
    assets: Dict[str, Any] = {}
    if not os.path.exists(iso_path):
        raise AssetError(f"game disc not found: {iso_path}")
    image = disc_image_path(iso_path)
    if not os.path.exists(image):
        raise AssetError(f"game ISO not found: {image}")
    assets["disc_path"] = iso_path
    assets["iso_path"] = image
    assets["iso_sha256"] = sha256_file(image)
    assets["iso_bytes"] = os.path.getsize(image)
    expected = EXPECTED_ISO_SHA.get(config.game)
    if expected and config.verify_hashes and \
            assets["iso_sha256"] != expected:
        raise AssetError(
            f"ISO hash mismatch: {iso_path}: got "
            f"{assets['iso_sha256'][:16]}..., expected "
            f"{expected[:16]}... (the exact disc the published "
            f"records for {config.game} were made with)")
    if not os.path.exists(BIOS_SRC):
        raise AssetError(f"OpenBIOS not found: {BIOS_SRC}")
    assets["bios_path"] = BIOS_SRC
    assets["bios_sha256"] = sha256_file(BIOS_SRC)
    if require_model:
        for label, path in (("model", config.model_path),
                            ("model_manifest", config.manifest_path)):
            if not os.path.exists(path):
                raise AssetError(f"{label} not found: {path}")
            assets[f"{label}_sha256"] = sha256_file(path)
    core = _resolve_core()
    if not os.path.exists(core):
        raise AssetError(f"libretro core not found: {core}")
    assets["core_path"] = core
    assets["core_sha256"] = sha256_file(core)
    return assets


def _resolve_core() -> str:
    from ps1play.api import DEFAULT_CORE  # noqa: PLC0415
    return DEFAULT_CORE


class EnvFrameSource(FrameSource):
    """Ordered capture over a game env object's frame() with staleness
    detection via the core's rendered-frame counter."""

    def __init__(self, env, session: "EnvSession"):
        self._env = env
        self._session = session
        self._seq = 0
        self._last_frames_run = -1
        self._ema_ms: Optional[float] = None

    def latest(self, require_fresh: bool = True) -> Frame:
        t0 = time.perf_counter()
        fr = self._env.frame()
        ms = (time.perf_counter() - t0) * 1000.0
        self._ema_ms = (ms if self._ema_ms is None
                        else 0.7 * self._ema_ms + 0.3 * ms)
        check_frame_shape(fr)
        self._seq += 1
        frames_run = int(getattr(self._env.p.core, "frames_run", -1))
        stale = (frames_run == self._last_frames_run
                 and self._last_frames_run >= 0)
        self._last_frames_run = frames_run
        if stale and require_fresh:
            raise FrameError(
                f"stale frame: emulator rendered no new frame since "
                f"the previous capture (frames_run={frames_run})")
        return Frame(seq=self._seq, emulator_frame_count=frames_run,
                     rgb=fr, timestamp=time.time(), stale=stale)

    def capture_latency_ms(self) -> float:
        return self._ema_ms or 0.0

    def close(self) -> None:
        self._env = None


class EnvSession(Emulator):
    """The emulator lifecycle over a game env object."""

    def __init__(self, env, config, *, boot_info: Optional[dict] = None):
        self.env = env
        self.config = config
        self.boot_info = boot_info or {}
        self._src: Optional[EnvFrameSource] = None
        self._alive = True

    @classmethod
    def boot_new(cls, config, *, deadline_s: float = 120.0,
                 telemetry=None) -> "EnvSession":
        """Build the game env (imports only the proven game wrappers),
        boot the core, and enforce the deadline."""
        from ps1play.runtime.registry import make_env
        t0 = time.time()
        try:
            env = make_env(config)
        except AssetError:
            raise
        except Exception as e:
            raise EmulatorError(f"emulator construction failed: "
                                f"{type(e).__name__}: {e}")
        if time.time() - t0 > deadline_s:
            try:
                env.close()
            except Exception:
                pass
            raise EmulatorError(
                f"emulator boot exceeded deadline ({deadline_s}s)")
        if telemetry is not None:
            telemetry.latency("emulator_boot_s",
                              (time.time() - t0) * 1000.0)
        sess = cls(env, config)
        try:
            bi = getattr(env, "boot_info", None)
            if isinstance(bi, dict):
                sess.boot_info = bi
        except Exception:
            pass
        return sess

    # ---- Emulator surface ----
    def frames(self) -> FrameSource:
        if self._src is None:
            self._src = EnvFrameSource(self.env, self)
        return self._src

    def advance(self, frames: int, buttons: frozenset) -> None:
        if not self._alive:
            raise EmulatorError("advance on a dead emulator session")
        try:
            self.env.run(int(frames), set(buttons))
        except Exception as e:
            self._alive = False
            raise EmulatorError(
                f"emulator died during advance: {type(e).__name__}: {e}")

    def alive(self) -> bool:
        return self._alive

    def serialize(self) -> bytes:
        try:
            return self.env.p.core.serialize()
        except Exception as e:
            self._alive = False
            raise EmulatorError(f"serialize failed: "
                                f"{type(e).__name__}: {e}")

    def unserialize(self, blob: bytes) -> None:
        try:
            self.env.p.core.unserialize(blob)
            self.env.run(1, set())   # force a render before frame reads
        except Exception as e:
            self._alive = False
            raise EmulatorError(f"unserialize failed: "
                                f"{type(e).__name__}: {e}")

    def tag(self) -> str:
        core = os.path.basename(getattr(getattr(self.env, "p", None),
                                        "core_path", "") or "?")
        return f"beetle={core}; boot={str(self.boot_info)[:110]}"

    def close(self) -> None:
        if self._src is not None:
            try:
                self._src.close()
            except Exception:
                pass
            self._src = None
        self._alive = False
        try:
            self.env.close()
        except Exception:
            pass

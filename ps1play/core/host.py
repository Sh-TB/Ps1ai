"""Libretro host (ctypes) — headless PS1 execution engine.

Proven callback setup (borrowed from scripts/psx_headless.py which booted
Metal Slug X to real gameplay at ~287 fps, software rendering, no GPU).
Extensions over the original: live RAM/VRAM numpy views, save-state API.
"""
import ctypes, os, sys, time
from ctypes import (CFUNCTYPE, POINTER, byref, cast, c_bool, c_char_p, c_double,
                    c_float, c_int, c_int16, c_size_t, c_uint, c_void_p, Structure)
import numpy as np

from .inputmap import parse_buttons

# --- libretro environment cmds (subset, proven values) ---
E_CAN_DUPE, E_OVERSCAN, E_SET_MESSAGE = 3, 2, 6
E_SET_PERF_LEVEL, E_SYSTEM_DIR, E_PIXEL_FMT = 8, 9, 10
E_SET_INPUT_DESC, E_SET_KB_CB, E_SET_DISK_CB, E_SET_HW_RENDER = 11, 12, 13, 14
E_GET_VARIABLE, E_SET_VARIABLES, E_GET_VARIABLE_UPDATE = 15, 16, 17
E_SET_SUPPORT_NO_GAME, E_LIBRETRO_PATH = 18, 19
E_SET_FRAME_TIME_CB, E_SET_AUDIO_CB, E_RUMBLE = 21, 22, 23
E_LOG_IFACE, E_PERF_IFACE = 27, 28
E_SAVE_DIR, E_SET_AV_INFO = 31, 32
E_SET_PROC_ADDR, E_SET_SUBSYSTEM, E_SET_CONTROLLER_INFO = 33, 34, 35
E_SET_MEMORY_MAPS, E_SET_GEOMETRY, E_USERNAME, E_LANGUAGE = 36, 37, 38, 39
E_SET_SUPPORT_ACHIEVEMENTS = 42
E_GET_CURRENT_SW_FB, E_INPUT_BITMASKS, E_CORE_OPTS_VER = 43, 51, 52
E_SET_CORE_OPTS, E_SET_CORE_OPTS_INTL, E_SET_MESSAGE_EXT = 57, 58, 59
E_VFS_IFACE, E_DISK_EXT_VER = 61, 72

PIXEL_0RGB1555, PIXEL_XRGB8888, PIXEL_RGB565 = 0, 1, 2
DEVICE_JOYPAD = 1
MEM_SAVE_RAM, MEM_SYSTEM_RAM, MEM_VIDEO_RAM = 1, 2, 0


class retro_system_info(Structure):
    _fields_ = [("library_name", c_char_p), ("library_version", c_char_p),
                ("valid_extensions", c_char_p), ("need_fullpath", c_bool),
                ("block_extract", c_bool)]


class retro_variable(Structure):
    _fields_ = [("key", c_char_p), ("value", c_char_p)]


LOG_PRINTF = CFUNCTYPE(None, c_uint, c_char_p)


class retro_log_callback(Structure):
    _fields_ = [("log", LOG_PRINTF)]


class retro_game_info(Structure):
    _fields_ = [("path", c_char_p), ("data", c_void_p),
                ("size", c_size_t), ("meta", c_char_p)]


VIDEO_REFRESH = CFUNCTYPE(None, c_void_p, c_uint, c_uint, c_size_t)
AUDIO_SAMPLE = CFUNCTYPE(None, c_int16, c_int16)
AUDIO_BATCH = CFUNCTYPE(c_size_t, POINTER(c_int16), c_size_t)
INPUT_POLL = CFUNCTYPE(None)
INPUT_STATE = CFUNCTYPE(c_int16, c_uint, c_uint, c_uint, c_uint)
ENVIRONMENT = CFUNCTYPE(c_bool, c_uint, c_void_p)

DEFAULT_OVERRIDES = {b"beetle_psx_renderer": b"software",
                     b"beetle_psx_frame_duping": b"disabled"}


class LibretroCore:
    """Headless libretro frontend with live memory views and save states."""

    def __init__(self, core_path, system_dir, save_dir,
                 var_overrides=None, verbose=False):
        self.verbose = verbose
        self.system_dir_buf = ctypes.create_string_buffer(
            os.fsencode(os.path.abspath(system_dir)))
        self.save_dir_buf = ctypes.create_string_buffer(
            os.fsencode(os.path.abspath(save_dir)))
        self.pixel_fmt = PIXEL_0RGB1555
        self.frame_count = 0
        self.frame = None
        self.core_vars = {}
        self.var_overrides = dict(DEFAULT_OVERRIDES)
        if var_overrides:
            self.var_overrides.update(var_overrides)
        self.log_history = []
        self._keepalive = []
        self._buttons = set()
        self.frames_run = 0
        self._ram = self._vram = self._sram = None
        self._ram_buf = self._vram_buf = self._sram_buf = None

        lib = ctypes.CDLL(os.path.abspath(core_path))
        self.lib = lib
        lib.retro_set_environment.argtypes = [ENVIRONMENT]
        lib.retro_set_video_refresh.argtypes = [VIDEO_REFRESH]
        lib.retro_set_audio_sample.argtypes = [AUDIO_SAMPLE]
        lib.retro_set_audio_sample_batch.argtypes = [AUDIO_BATCH]
        lib.retro_set_input_poll.argtypes = [INPUT_POLL]
        lib.retro_set_input_state.argtypes = [INPUT_STATE]
        lib.retro_get_system_info.argtypes = [POINTER(retro_system_info)]
        lib.retro_get_system_av_info.argtypes = [POINTER(_av_info)]
        lib.retro_load_game.argtypes = [POINTER(retro_game_info)]
        lib.retro_load_game.restype = c_bool
        lib.retro_get_memory_data.argtypes = [c_uint]
        lib.retro_get_memory_data.restype = c_void_p
        lib.retro_get_memory_size.argtypes = [c_uint]
        lib.retro_get_memory_size.restype = c_size_t
        lib.retro_serialize_size.restype = c_size_t
        lib.retro_serialize.argtypes = [c_void_p, c_size_t]
        lib.retro_serialize.restype = c_bool
        lib.retro_unserialize.argtypes = [c_void_p, c_size_t]
        lib.retro_unserialize.restype = c_bool

        @VIDEO_REFRESH
        def video_refresh(data, width, height, pitch):
            if not data or width == 0 or height == 0:
                return
            self.frame = (data, width, height, pitch, self.pixel_fmt)
            self.frame_count += 1

        @AUDIO_SAMPLE
        def audio_sample(l, r):
            return None

        @AUDIO_BATCH
        def audio_batch(data, frames):
            return frames

        @INPUT_POLL
        def input_poll():
            return None

        @INPUT_STATE
        def input_state(port, device, index, device_id):
            if port != 0 or device != DEVICE_JOYPAD:
                return 0
            return 1 if device_id in self._buttons else 0

        @ENVIRONMENT
        def environment(cmd, data):
            return self._environment(cmd, data)

        @LOG_PRINTF
        def core_log(level, text):
            s = text.decode("utf-8", "replace").rstrip()
            self.log_history.append(s)
            if self.verbose and len(self.log_history) < 400:
                sys.stderr.write(f"[core] {s}\n")

        # variadic-log shim (compiled once: scripts/logshim.c -> logshim.so)
        self._log_fn = None
        here = os.path.dirname(os.path.abspath(__file__))
        for cand in (os.path.join(here, "logshim.so"),
                     "/home/z/my-project/scripts/logshim.so"):
            if os.path.exists(cand):
                try:
                    shim = ctypes.CDLL(cand)
                    SINK = CFUNCTYPE(None, c_char_p)
                    shim_sink = SINK(lambda s: core_log(0, s))
                    shim.set_sink.argtypes = [c_void_p]
                    shim.set_sink(cast(shim_sink, c_void_p))
                    self._keepalive.append(shim_sink)
                    self._log_fn = getattr(shim, "core_log_shim")
                    self._log_fn.restype = None
                    break
                except OSError:
                    continue

        self.cb_video, self.cb_audio = video_refresh, audio_sample
        self.cb_batch, self.cb_poll = audio_batch, input_poll
        self.cb_input, self.cb_env = input_state, environment
        self.cb_log = core_log
        self._keepalive += [video_refresh, audio_sample, audio_batch,
                            input_poll, input_state, environment, core_log]

        lib.retro_set_video_refresh(video_refresh)
        lib.retro_set_audio_sample(audio_sample)
        lib.retro_set_audio_sample_batch(audio_batch)
        lib.retro_set_input_poll(input_poll)
        lib.retro_set_input_state(input_state)
        lib.retro_set_environment(environment)

        si = retro_system_info()
        lib.retro_get_system_info(byref(si))
        self.core_name = si.library_name.decode() if si.library_name else "?"
        self.core_ver = si.library_version.decode() if si.library_version else "?"
        if self.verbose:
            print(f"[ps1play] core: {self.core_name} {self.core_ver}")
        lib.retro_init()

    # ---------------- environment (proven logic) ----------------
    def _environment(self, cmd, data):
        if cmd == E_CAN_DUPE:
            cast(data, POINTER(c_bool))[0] = True
            return True
        if cmd == E_OVERSCAN:
            cast(data, POINTER(c_bool))[0] = False
            return True
        if cmd == E_SYSTEM_DIR:
            cast(data, POINTER(c_char_p))[0] = cast(self.system_dir_buf, c_char_p)
            return True
        if cmd == E_SAVE_DIR:
            cast(data, POINTER(c_char_p))[0] = cast(self.save_dir_buf, c_char_p)
            return True
        if cmd == E_LOG_IFACE:
            lcb = cast(data, POINTER(retro_log_callback))[0]
            if self._log_fn is not None:
                lcb.log = cast(self._log_fn, LOG_PRINTF)
            else:
                lcb.log = self.cb_log
            cast(data, POINTER(retro_log_callback))[0] = lcb
            return True
        if cmd == E_PIXEL_FMT:
            self.pixel_fmt = cast(data, POINTER(c_int))[0]
            return True
        if cmd == E_GET_VARIABLE:
            p = cast(data, POINTER(retro_variable))
            key = p[0].key
            val = None
            if key in self.var_overrides:
                val = self.var_overrides[key]
            elif key in self.core_vars:
                val = self.core_vars[key]
            else:
                return False
            buf = ctypes.create_string_buffer(val)
            self._keepalive.append(buf)
            p[0].value = cast(buf, c_char_p)
            return True
        if cmd == E_SET_VARIABLES:
            arr = cast(data, POINTER(retro_variable))
            i = 0
            while True:
                rv = arr[i]
                if not rv.key:
                    break
                raw = rv.value.decode() if rv.value else ""
                if ";" in raw:
                    default = raw.split(";", 1)[-1].strip().split("|")[0].strip()
                else:
                    default = raw
                self.core_vars[rv.key] = default.encode()
                i += 1
            return True
        if cmd == E_GET_VARIABLE_UPDATE:
            cast(data, POINTER(c_bool))[0] = False
            return True
        if cmd == E_USERNAME:
            cast(data, POINTER(c_char_p))[0] = b"ps1play"
            return True
        if cmd == E_LANGUAGE:
            cast(data, POINTER(c_uint))[0] = 0
            return True
        if cmd == E_CORE_OPTS_VER:
            cast(data, POINTER(c_uint))[0] = 0
            return True
        if cmd in (E_SET_INPUT_DESC, E_SET_CONTROLLER_INFO, E_SET_DISK_CB,
                   E_SET_GEOMETRY, E_SET_AV_INFO, E_SET_MESSAGE,
                   E_SET_PROC_ADDR, E_SET_SUBSYSTEM, E_SET_MEMORY_MAPS,
                   E_SET_SUPPORT_ACHIEVEMENTS, E_SET_MESSAGE_EXT,
                   E_SET_CORE_OPTS, E_SET_CORE_OPTS_INTL, E_SET_KB_CB,
                   E_SET_AUDIO_CB, E_SET_FRAME_TIME_CB, E_SET_PERF_LEVEL,
                   E_SET_SUPPORT_NO_GAME):
            return True
        # force software path / unsupported
        return False

    # ---------------- lifecycle ----------------
    def load_game(self, path):
        info = retro_game_info()
        info.path = os.fsencode(os.path.abspath(path))
        ok = self.lib.retro_load_game(byref(info))
        if not ok:
            raise RuntimeError(f"retro_load_game failed: {path}")
        av = _av_info()
        self.lib.retro_get_system_av_info(byref(av))
        self.av_info = {"w": av.geometry.base_width, "h": av.geometry.base_height,
                        "fps": av.timing.fps, "audio": av.timing.sample_rate}
        self.lib.retro_set_controller_port_device(0, DEVICE_JOYPAD)
        self._map_memories()
        return self.av_info

    def _map_memories(self):
        for attr, mem_id in (("_sram", MEM_SAVE_RAM), ("_ram", MEM_SYSTEM_RAM),
                             ("_vram", MEM_VIDEO_RAM)):
            ptr = self.lib.retro_get_memory_data(mem_id)
            size = self.lib.retro_get_memory_size(mem_id)
            if not ptr or not size:
                setattr(self, attr, None)
                continue
            buf = (ctypes.c_uint8 * size).from_address(ptr)
            setattr(self, attr + "_buf", buf)
            setattr(self, attr, np.frombuffer(buf, dtype=np.uint8))

    @property
    def ram(self):
        """Live numpy view of 2MB PS1 main RAM (u8). READ-ONLY usage by agents."""
        return self._ram

    @property
    def vram(self):
        return self._vram

    @property
    def sram(self):
        return self._sram

    # ---------------- input / run ----------------
    def set_buttons(self, spec):
        self._buttons = parse_buttons(spec)

    def reset(self):
        self.lib.retro_reset()

    def run_frame(self):
        self.frames_run += 1
        self.lib.retro_run()

    def run(self, frames, buttons=None):
        if buttons is not None:
            self.set_buttons(buttons)
        for _ in range(frames):
            self.run_frame()

    # ---------------- save states ----------------
    def serialize(self):
        n = self.lib.retro_serialize_size()
        buf = (ctypes.c_ubyte * n)()
        ok = self.lib.retro_serialize(cast(buf, c_void_p), n)
        if not ok:
            raise RuntimeError("retro_serialize failed")
        return bytes(buf)

    def unserialize(self, blob):
        n = len(blob)
        buf = (ctypes.c_ubyte * n).from_buffer_copy(blob)
        ok = self.lib.retro_unserialize(cast(buf, c_void_p), n)
        if not ok:
            raise RuntimeError("retro_unserialize failed")

    def frame_rgb(self):
        """Latest rendered frame as (H,W,3) uint8 (rare, human-only use)."""
        if not self.frame:
            return None
        data, w, h, pitch, fmt = self.frame
        buf = ctypes.string_at(data, pitch * h)
        if fmt == PIXEL_XRGB8888:
            per = pitch // 4
            arr = np.frombuffer(buf, dtype=np.uint32, count=per * h)
            arr = arr.reshape(h, per)[:, :w]
            return np.dstack([(arr >> 16) & 0xFF, (arr >> 8) & 0xFF, arr & 0xFF]
                             ).astype(np.uint8)
        if fmt == PIXEL_RGB565:
            per = pitch // 2
            arr = np.frombuffer(buf, dtype=np.uint16, count=per * h)
            arr = arr.reshape(h, per)[:, :w].astype(np.uint32)
            r = (((arr >> 11) & 31) * 255 // 31).astype(np.uint8)
            g = (((arr >> 5) & 63) * 255 // 63).astype(np.uint8)
            b = ((arr & 31) * 255 // 31).astype(np.uint8)
            return np.dstack([r, g, b])
        per = pitch // 2
        arr = np.frombuffer(buf, dtype=np.uint16, count=per * h)
        arr = arr.reshape(h, per)[:, :w].astype(np.uint32)
        r = (((arr >> 10) & 31) * 255 // 31).astype(np.uint8)
        g = (((arr >> 5) & 31) * 255 // 31).astype(np.uint8)
        b = ((arr & 31) * 255 // 31).astype(np.uint8)
        return np.dstack([r, g, b])

    def shutdown(self):
        try:
            self.lib.retro_unload_game()
            self.lib.retro_deinit()
        except Exception:
            pass


class _geo(ctypes.Structure):
    _fields_ = [("base_width", c_uint), ("base_height", c_uint),
                ("max_width", c_uint), ("max_height", c_uint),
                ("aspect_ratio", c_float)]


class _tim(ctypes.Structure):
    _fields_ = [("fps", c_double), ("sample_rate", c_double)]


class _av_info(ctypes.Structure):
    _fields_ = [("geometry", _geo), ("timing", _tim)]

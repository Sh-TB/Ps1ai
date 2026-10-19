#!/usr/bin/env python3.13
"""
PSX Headless libretro frontend - runs a PS1 game with ZERO graphics.
No GPU, no X11, no window. Software rendering in RAM, frames analyzed
in numpy, inputs injected by script. Built for CLI proof-of-run.
"""
import ctypes, os, sys, time, hashlib, json, argparse
from ctypes import (CFUNCTYPE, POINTER, byref, c_void_p, c_char_p, c_bool,
                    c_int, c_uint, c_int16, c_size_t, c_float, c_double,
                    Structure, cast)
import numpy as np

# ================= libretro constants =================
ENV_GET_OVERSCAN, ENV_GET_CAN_DUPE = 2, 3
ENV_SET_MESSAGE = 6
ENV_SET_PERFORMANCE_LEVEL, ENV_GET_SYSTEM_DIRECTORY = 8, 9
ENV_SET_PIXEL_FORMAT, ENV_SET_INPUT_DESCRIPTORS = 10, 11
ENV_SET_KEYBOARD_CALLBACK, ENV_SET_DISK_CONTROL_INTERFACE, ENV_SET_HW_RENDER = 12, 13, 14
ENV_GET_VARIABLE, ENV_SET_VARIABLES, ENV_GET_VARIABLE_UPDATE = 15, 16, 17
ENV_SET_SUPPORT_NO_GAME, ENV_GET_LIBRETRO_PATH = 18, 19
ENV_SET_FRAME_TIME_CALLBACK, ENV_SET_AUDIO_CALLBACK, ENV_GET_RUMBLE_INTERFACE = 21, 22, 23
ENV_GET_LOG_INTERFACE, ENV_GET_PERFORMANCE_INTERFACE = 27, 28
ENV_GET_SAVE_DIRECTORY, ENV_SET_SYSTEM_AV_INFO = 31, 32
ENV_SET_PROC_ADDRESS_CALLBACK, ENV_SET_SUBSYSTEM_INFO, ENV_SET_CONTROLLER_INFO = 33, 34, 35
ENV_SET_MEMORY_MAPS, ENV_SET_GEOMETRY, ENV_GET_USERNAME, ENV_GET_LANGUAGE = 36, 37, 38, 39
ENV_SET_SUPPORT_ACHIEVEMENTS = 42
ENV_GET_CURRENT_SOFTWARE_FRAMEBUFFER = 43
ENV_GET_INPUT_BITMASKS, ENV_GET_CORE_OPTIONS_VERSION = 51, 52
ENV_SET_CORE_OPTIONS, ENV_SET_CORE_OPTIONS_INTL, ENV_SET_MESSAGE_EXT = 57, 58, 59
ENV_GET_VFS_INTERFACE, ENV_GET_DISK_CONTROL_EXT_VERSION = 61, 72

PIXEL_0RGB1555, PIXEL_XRGB8888, PIXEL_RGB565 = 0, 1, 2
DEVICE_JOYPAD = 1
JP_B, JP_Y, JP_SELECT, JP_START = 0, 1, 2, 3
JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT = 4, 5, 6, 7
JP_A, JP_X, JP_L, JP_R = 8, 9, 10, 11

BTN_NAMES = {JP_B: "B(x)", JP_Y: "Y(sq)", JP_SELECT: "SELECT", JP_START: "START",
             JP_UP: "UP", JP_DOWN: "DOWN", JP_LEFT: "LEFT", JP_RIGHT: "RIGHT",
             JP_A: "A(o)", JP_X: "X(tr)", JP_L: "L1", JP_R: "R1"}

# ================= structs =================
class retro_system_info(Structure):
    _fields_ = [("library_name", c_char_p), ("library_version", c_char_p),
                ("valid_extensions", c_char_p), ("need_fullpath", c_bool),
                ("block_extract", c_bool)]

class retro_game_geometry(Structure):
    _fields_ = [("base_width", c_uint), ("base_height", c_uint),
                ("max_width", c_uint), ("max_height", c_uint),
                ("aspect_ratio", c_float)]

class retro_system_timing(Structure):
    _fields_ = [("fps", c_double), ("sample_rate", c_double)]

class retro_system_av_info(Structure):
    _fields_ = [("geometry", retro_game_geometry), ("timing", retro_system_timing)]

class retro_variable(Structure):
    _fields_ = [("key", c_char_p), ("value", c_char_p)]

LOG_PRINTF = CFUNCTYPE(None, c_uint, c_char_p)

class retro_log_callback(Structure):
    _fields_ = [("log", LOG_PRINTF)]

class retro_game_info(Structure):
    _fields_ = [("path", c_char_p), ("data", c_void_p),
                ("size", c_size_t), ("meta", c_char_p)]

# ================= callbacks =================
VIDEO_REFRESH = CFUNCTYPE(None, c_void_p, c_uint, c_uint, c_size_t)
AUDIO_SAMPLE = CFUNCTYPE(None, c_int16, c_int16)
AUDIO_BATCH = CFUNCTYPE(c_size_t, POINTER(c_int16), c_size_t)
INPUT_POLL = CFUNCTYPE(None)
INPUT_STATE = CFUNCTYPE(c_int16, c_uint, c_uint, c_uint, c_uint)
ENVIRONMENT = CFUNCTYPE(c_bool, c_uint, c_void_p)


def to_rgb(frame, fmt, width, pitch_bytes, height):
    """Convert raw libretro frame buffer to (H,W,3) uint8 RGB numpy array."""
    if fmt == PIXEL_XRGB8888:
        px_per_row = pitch_bytes // 4
        arr = np.frombuffer(frame, dtype=np.uint32, count=px_per_row * height)
        arr = arr.reshape(height, px_per_row)[:, :width]
        r = ((arr >> 16) & 0xFF).astype(np.uint8)
        g = ((arr >> 8) & 0xFF).astype(np.uint8)
        b = (arr & 0xFF).astype(np.uint8)
        return np.dstack([r, g, b])
    elif fmt == PIXEL_RGB565:
        px_per_row = pitch_bytes // 2
        arr = np.frombuffer(frame, dtype=np.uint16, count=px_per_row * height)
        arr = arr.reshape(height, px_per_row)[:, :width].astype(np.uint32)
        r = (((arr >> 11) & 31) * 255 // 31).astype(np.uint8)
        g = (((arr >> 5) & 63) * 255 // 63).astype(np.uint8)
        b = ((arr & 31) * 255 // 31).astype(np.uint8)
        return np.dstack([r, g, b])
    else:  # 0RGB1555
        px_per_row = pitch_bytes // 2
        arr = np.frombuffer(frame, dtype=np.uint16, count=px_per_row * height)
        arr = arr.reshape(height, px_per_row)[:, :width].astype(np.uint32)
        r = (((arr >> 10) & 31) * 255 // 31).astype(np.uint8)
        g = (((arr >> 5) & 31) * 255 // 31).astype(np.uint8)
        b = ((arr & 31) * 255 // 31).astype(np.uint8)
        return np.dstack([r, g, b])


def ascii_art(rgb, cols=96):
    h, w, _ = rgb.shape
    rows = max(1, round(cols * h / w / 2.1))
    ys = (np.linspace(0, h, rows + 1)).astype(int)
    xs = (np.linspace(0, w, cols + 1)).astype(int)
    lum = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    blocks = [lum[ys[i]:ys[i+1], xs[j]:xs[j+1]].mean()
              for i in range(rows) for j in range(cols)]
    chars = " .:-=+*#%@"
    out = []
    for i in range(rows):
        line = "".join(chars[min(9, int(blocks[i * cols + j] / 25.6))]
                       for j in range(cols))
        out.append(line)
    return "\n".join(out)


class PSXHeadless:
    def __init__(self, core_path, system_dir, save_dir, verbose=True):
        self.verbose = verbose
        # persistent NUL-terminated buffers (must outlive callbacks)
        self.system_dir_buf = ctypes.create_string_buffer(os.fsencode(os.path.abspath(system_dir)))
        self.save_dir_buf = ctypes.create_string_buffer(os.fsencode(os.path.abspath(save_dir)))
        self.pixel_fmt = PIXEL_0RGB1555
        self.frame = None
        self.frame_count = 0
        self.unique_hashes = set()
        self.core_vars = {}          # defaults parsed from SET_VARIABLES
        self.var_overrides = {
            b"beetle_psx_renderer": b"software",
            b"beetle_psx_frame_duping": b"disabled",
        }
        self.log_history = []
        self.env_trace = {}   # cmd -> [asked, answered_true]
        # keep python refs alive (GC!)
        self._keepalive = []

        lib = ctypes.CDLL(os.path.abspath(core_path))
        self.lib = lib

        # bind core API
        lib.retro_set_environment.argtypes = [ENVIRONMENT]
        lib.retro_set_video_refresh.argtypes = [VIDEO_REFRESH]
        lib.retro_set_audio_sample.argtypes = [AUDIO_SAMPLE]
        lib.retro_set_audio_sample_batch.argtypes = [AUDIO_BATCH]
        lib.retro_set_input_poll.argtypes = [INPUT_POLL]
        lib.retro_set_input_state.argtypes = [INPUT_STATE]
        lib.retro_init.restype = None
        lib.retro_api_version.restype = c_uint
        lib.retro_get_system_info.argtypes = [POINTER(retro_system_info)]
        lib.retro_get_system_av_info.argtypes = [POINTER(retro_system_av_info)]
        lib.retro_load_game.argtypes = [POINTER(retro_game_info)]
        lib.retro_load_game.restype = c_bool
        lib.retro_run.restype = None
        lib.retro_unload_game.restype = None
        lib.retro_deinit.restype = None

        # button state per frame (set by run loop)
        self._buttons = set()

        # ---- callbacks ----
        @VIDEO_REFRESH
        def video_refresh(data, width, height, pitch):
            if not data or width == 0 or height == 0:
                return
            buf = ctypes.string_at(data, pitch * height)
            self.frame = to_rgb(buf, self.pixel_fmt, width, pitch, height)
            h = hashlib.md5(self.frame.tobytes()).digest()[:6]
            self.unique_hashes.add(h)
            self.frame_count += 1

        @AUDIO_SAMPLE
        def audio_sample(l, r): return None

        @AUDIO_BATCH
        def audio_batch(data, frames): return frames

        @INPUT_POLL
        def input_poll(): return None

        @INPUT_STATE
        def input_state(port, device, index, device_id):
            if port != 0 or device != DEVICE_JOYPAD:
                return 0
            return 1 if device_id in self._buttons else 0

        @ENVIRONMENT
        def environment(cmd, data):
            res = self._environment(cmd, data)
            t = self.env_trace.setdefault(cmd, [0, 0])
            t[0] += 1
            if res:
                t[1] += 1
            return res

        @LOG_PRINTF
        def core_log(level, text):
            try:
                s = text.decode("utf-8", "replace").rstrip()
            except Exception:
                return
            self.log_history.append(s)
            if self.verbose and len(self.log_history) < 400:
                sys.stderr.write(f"[core] {s}\n")

        # --- varargs-aware log shim (real formatted core messages) ---
        try:
            shim = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logshim.so"))
            SINK = CFUNCTYPE(None, c_char_p)
            shim_sink = SINK(lambda s: core_log(0, s))
            shim.set_sink.argtypes = [c_void_p]
            shim.set_sink(ctypes.cast(shim_sink, c_void_p))
            self._keepalive.append(shim_sink)
            self._log_fn = getattr(shim, "core_log_shim")
            self._log_fn.restype = None
        except OSError as e:
            self._log_fn = None

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

        # core info
        si = retro_system_info()
        lib.retro_get_system_info(byref(si))
        self.core_name = si.library_name.decode() if si.library_name else "?"
        self.core_ver = si.library_version.decode() if si.library_version else "?"
        print(f"[front] core: {self.core_name} {self.core_ver} | "
              f"ext: {si.valid_extensions.decode() if si.valid_extensions else '?'} | "
              f"need_fullpath={si.need_fullpath}")
        lib.retro_init()

    # ---------- environment ----------
    def _environment(self, cmd, data):
        if cmd == ENV_GET_CAN_DUPE:
            cast(data, POINTER(c_bool))[0] = True
            return True
        if cmd == ENV_GET_OVERSCAN:
            cast(data, POINTER(c_bool))[0] = False
            return True
        if cmd == ENV_GET_SYSTEM_DIRECTORY:
            cast(data, POINTER(c_char_p))[0] = cast(self.system_dir_buf, c_char_p)
            return True
        if cmd == ENV_GET_SAVE_DIRECTORY:
            cast(data, POINTER(c_char_p))[0] = cast(self.save_dir_buf, c_char_p)
            return True
        if cmd == ENV_GET_LOG_INTERFACE:
            lcb = cast(data, POINTER(retro_log_callback))[0]
            if self._log_fn is not None:
                lcb.log = ctypes.cast(self._log_fn, LOG_PRINTF)
            else:
                lcb.log = self.cb_log
            cast(data, POINTER(retro_log_callback))[0] = lcb
            return True
        if cmd == ENV_SET_PIXEL_FORMAT:
            self.pixel_fmt = cast(data, POINTER(c_int))[0]
            names = {0: "0RGB1555", 1: "XRGB8888", 2: "RGB565"}
            if self.verbose:
                print(f"[front] pixel format -> {names.get(self.pixel_fmt, self.pixel_fmt)}")
            return True
        if cmd == ENV_GET_VARIABLE:
            p = cast(data, POINTER(retro_variable))
            key = p[0].key
            if key in self.var_overrides:
                val = self.var_overrides[key]
            elif key in self.core_vars:
                val = self.core_vars[key]
            else:
                return False
            buf = ctypes.create_string_buffer(val)   # keepalive!
            self._keepalive.append(buf)
            p[0].value = ctypes.cast(buf, c_char_p)
            return True
        if cmd == ENV_SET_VARIABLES:
            arr = cast(data, POINTER(retro_variable))
            i = 0
            while True:
                rv = arr[i]
                if not rv.key:
                    break
                # value format: "Description; opt1|opt2|default-ish"
                raw = rv.value.decode() if rv.value else ""
                if ";" in raw:
                    default = raw.split(";", 1)[-1].strip().split("|")[0].strip()
                else:
                    default = raw
                self.core_vars[rv.key] = default.encode()
                i += 1
            if self.verbose:
                print(f"[front] core exposed {len(self.core_vars)} variables")
            return True
        if cmd == ENV_GET_VARIABLE_UPDATE:
            cast(data, POINTER(c_bool))[0] = False
            return True
        if cmd == ENV_SET_SUPPORT_NO_GAME:
            return True
        if cmd in (ENV_SET_INPUT_DESCRIPTORS, ENV_SET_CONTROLLER_INFO,
                   ENV_SET_DISK_CONTROL_INTERFACE, ENV_SET_GEOMETRY,
                   ENV_SET_SYSTEM_AV_INFO, ENV_SET_MESSAGE,
                   ENV_SET_PROC_ADDRESS_CALLBACK, ENV_SET_SUBSYSTEM_INFO,
                   ENV_SET_MEMORY_MAPS, ENV_SET_SUPPORT_ACHIEVEMENTS,
                   ENV_SET_MESSAGE_EXT, ENV_SET_CORE_OPTIONS,
                   ENV_SET_CORE_OPTIONS_INTL, ENV_SET_KEYBOARD_CALLBACK,
                   ENV_SET_AUDIO_CALLBACK, ENV_SET_FRAME_TIME_CALLBACK,
                   ENV_SET_PERFORMANCE_LEVEL):
            return True
        if cmd == ENV_GET_CORE_OPTIONS_VERSION:
            cast(data, POINTER(c_uint))[0] = 0   # force legacy SET_VARIABLES
            return True
        if cmd == ENV_GET_USERNAME:
            cast(data, POINTER(c_char_p))[0] = b"zai"
            return True
        if cmd == ENV_GET_LANGUAGE:
            cast(data, POINTER(c_uint))[0] = 0
            return True
        if cmd in (ENV_SET_HW_RENDER, ENV_GET_PERFORMANCE_INTERFACE,
                   ENV_GET_RUMBLE_INTERFACE, ENV_GET_LIBRETRO_PATH,
                   ENV_GET_CURRENT_SOFTWARE_FRAMEBUFFER,
                   ENV_GET_INPUT_BITMASKS, ENV_GET_VFS_INTERFACE,
                   ENV_GET_DISK_CONTROL_EXT_VERSION):
            return False   # force software path / unsupported
        return False

    # ---------- run ----------
    def load_game(self, path):
        info = retro_game_info()
        info.path = os.fsencode(os.path.abspath(path))
        ok = self.lib.retro_load_game(byref(info))
        if not ok:
            raise RuntimeError("retro_load_game returned false")
        av = retro_system_av_info()
        self.lib.retro_get_system_av_info(byref(av))
        g, t = av.geometry, av.timing
        print(f"[front] game loaded. geometry {g.base_width}x{g.base_height} "
              f"(max {g.max_width}x{g.max_height}) fps={t.fps:.4f} audio={t.sample_rate:.0f}Hz")
        return av

    def run_frames(self, n, button_schedule=None, snapshot_frames=(),
                   out_dir=None, gif_every=0, gif_dir=None):
        """button_schedule: list of (start_frame, end_frame, {btns})"""
        schedule = sorted(button_schedule or [], key=lambda x: x[0])
        gif_frames = []
        t0 = time.time()
        for f in range(n):
            self._buttons = set()
            for s, e, btns in schedule:
                if s <= f < e:
                    self._buttons |= btns
            self.lib.retro_run()
            if f in snapshot_frames and self.frame is not None and out_dir:
                from PIL import Image
                p = os.path.join(out_dir, f"frame_{f:05d}.png")
                Image.fromarray(self.frame).save(p)
                print(f"[front] saved {p}")
            if gif_every and f % gif_every == 0 and self.frame is not None:
                from PIL import Image
                im = Image.fromarray(self.frame).resize((160, 120))
                gif_frames.append(im)
        dt = time.time() - t0
        fps = n / dt if dt > 0 else 0
        print(f"[front] ran {n} frames in {dt:.1f}s ({fps:.1f} fps, unthrottled) | "
              f"distinct frames so far: {len(self.unique_hashes)}")
        if gif_frames:
            from PIL import Image
            p = os.path.join(gif_dir, "boot_sequence.gif")
            gif_frames[0].save(p, save_all=True, append_images=gif_frames[1:],
                               duration=250, loop=0)
            print(f"[front] gif -> {p} ({len(gif_frames)} frames)")
        return fps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default="/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so")
    ap.add_argument("--system", default="/home/z/my-project/ps1-test/emu/system")
    ap.add_argument("--saves", default="/home/z/my-project/ps1-test/emu/saves")
    ap.add_argument("--game", default="/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue")
    ap.add_argument("--frames", type=int, default=2400)
    ap.add_argument("--outdir", default="/home/z/my-project/ps1-test/output/frames")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    fe = PSXHeadless(args.core, args.system, args.saves, verbose=not args.quiet)

    snaps = {30, 150, 400, 700, 1000, 1600, 2200, 2800, 3400, 4000, 4900,
             5300, 5600, 5900, 6200, 6500, 6800, 7100, 7400, 7700, 8000,
             8300, args.frames - 1}
    av = fe.load_game(args.game)

    # button choreography (frame ranges): skip BIOS/intros, navigate menus, play
    JP = dict(B=JP_B, Y=JP_Y, START=JP_START, UP=JP_UP, DOWN=JP_DOWN,
              LEFT=JP_LEFT, RIGHT=JP_RIGHT, A=JP_A, X=JP_X)
    sched = []
    # periodic START taps to skip logos / FMVs / confirm menus (1000..5200)
    for start in range(1000, 5300, 300):
        sched.append((start, start + 15, {JP_START}))
    sched.append((5150, 5165, {JP_START}))   # confirm OK?->YES
    # from 5600: run right and shoot (gameplay demo)
    sched += [
        (5600, args.frames, {JP_RIGHT}),
    ]
    for s in range(5650, args.frames - 20, 60):
        sched.append((s, s + 12, {JP_Y}))          # fire bursts
        if (s // 60) % 3 == 0:
            sched.append((s + 20, s + 32, {JP_B}))  # jumps

    fps = fe.run_frames(args.frames, button_schedule=sched,
                        snapshot_frames=snaps, out_dir=args.outdir,
                        gif_every=15, gif_dir=args.outdir)

    # ASCII proof at key moments: capture happens inside run; we saved
    # snapshots; now print the last frame as ASCII art
    if fe.frame is not None:
        print("\n=== FINAL FRAME (ASCII view) ===")
        print(ascii_art(fe.frame))
        from PIL import Image
        Image.fromarray(fe.frame).save(os.path.join(args.outdir, "final.png"))

    summary = {
        "core": fe.core_name, "version": fe.core_ver,
        "frames_requested": args.frames, "frames_rendered": fe.frame_count,
        "distinct_frames": len(fe.unique_hashes), "fps_achieved": round(fps, 1),
        "pixel_format": fe.pixel_fmt,
    }
    print("\n[env trace] cmd:[asked, answeredTrue]")
    names = {2: "OVERSCAN", 3: "CAN_DUPE", 9: "SYSTEM_DIR", 10: "PIXEL_FMT",
             15: "GET_VAR", 16: "SET_VARS", 17: "VAR_UPDATE", 27: "LOG",
             31: "SAVE_DIR", 51: "INPUT_BITMASK", 52: "OPT_VERSION"}
    for cmd in sorted(fe.env_trace):
        a, t = fe.env_trace[cmd]
        print(f"  {cmd:>3} {names.get(cmd, '?'):<13} asked={a:<3} ok={t}")
    with open(os.path.join(args.outdir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\n[summary]", json.dumps(summary, indent=2))

    fe.lib.retro_unload_game()
    fe.lib.retro_deinit()


if __name__ == "__main__":
    main()

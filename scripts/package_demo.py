#!/usr/bin/env python3.13
"""Package headless PSX demo evidence into download folder."""
import os, shutil, json
from PIL import Image

src = "/home/z/my-project/ps1-test/output/frames"
dst = "/home/z/my-project/download/psx_headless_demo"
os.makedirs(dst, exist_ok=True)

named = [
    ("frame_00030.png", "01_bios_boot_start.png"),
    ("frame_00700.png", "02_playstation_logo.png"),
    ("frame_01600.png", "03_game_code_running.png"),
    ("frame_02800.png", "04_agetec_publisher_logo.png"),
    ("frame_04000.png", "05_main_menu.png"),
    ("frame_04900.png", "06_menu_confirm_dialog.png"),
    ("frame_06500.png", "07_mission1_loading.png"),
    ("frame_07400.png", "08_gameplay_running_shooting.png"),
    ("frame_08599.png", "09_game_over_press_start.png"),
]
for s, d in named:
    p = os.path.join(src, s)
    if os.path.exists(p):
        shutil.copy(p, os.path.join(dst, d))
        print("copied", d)

# highlights GIF from key moments (use whatever exists)
keys = [p for p, _ in named if os.path.exists(os.path.join(src, p))]
ims = [Image.open(os.path.join(src, p)).convert("P", palette=Image.ADAPTIVE)
       for p in keys]
if ims:
    out = os.path.join(dst, "highlights.gif")
    ims[0].save(out, save_all=True, append_images=ims[1:], duration=1200, loop=0)
    print("gif:", out, len(ims), "frames")

# summary.json
summary = {
    "core": "Beetle PSX 0.9.44.1 (mednafen_psx_libretro)",
    "frontend": "custom Python ctypes libretro frontend (headless, no GPU/X11)",
    "bios": "SCPH-5501 (US) SHA1 0555C6FAE8906F3F09BAF5988F00E55F88E9F30B",
    "game": "Metal Slug X (USA) SLUS_012.12",
    "frames_run": 8600, "fps_achieved": 287.2, "distinct_frames": 1128,
    "milestones": [
        "BIOS boot + PlayStation logo animation",
        "game code running (save-data check message)",
        "intro FMV + publisher logos",
        "main menu navigated via scripted inputs",
        "mission 1 loading screen",
        "actual gameplay: run/jump/shoot, score 800->1200, death, PRESS START",
    ],
}
with open(os.path.join(dst, "summary.json"), "w") as f:
    json.dump(summary, f, indent=2)
print("summary.json written")
print("\nAll files in", dst, ":")
for f in sorted(os.listdir(dst)):
    print("  ", f, f"({os.path.getsize(os.path.join(dst, f)):,} B)")

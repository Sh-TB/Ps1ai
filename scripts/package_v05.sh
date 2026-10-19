#!/usr/bin/env bash
# package_v05.sh — build the source zip for delivery
set -e
cd /home/z/my-project
OUT=download/ps1play_v0.5_src.zip
rm -f "$OUT"
zip -qr "$OUT" ps1play \
    -x "ps1play/re/X09.BIN" -x "ps1play/re/X801.BIN" \
    -x "ps1play/re/RANKING.BIN" -x "ps1play/re/ENDING.BIN" \
    -x "ps1play/re/MCARD.BIN" -x "ps1play/re/TITLE.BIN" \
    -x "ps1play/re/BONUS.BIN" -x "ps1play/re/LOADING.BIN" \
    -x "*__pycache__*"
zip -qr "$OUT" scripts -x "*__pycache__*"
zip -qr "$OUT" download/ps1play_v4_mission1 \
    -x "download/ps1play_v4_mission1/diag/*.png" \
    -x "download/ps1play_v4_mission1/lab/end_*.png"
zip -q "$OUT" worklog.md
ls -la "$OUT"
python3 - "$OUT" <<'PYEOF'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
print(f"{len(names)} files, total {sum(i.file_size for i in z.infolist())//1024} KB uncompressed")
PYEOF

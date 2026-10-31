#!/usr/bin/env bash
# r61_run_validation.sh — drive the R61 fresh-validation grid to
# completion: 30 seeds x 2 reps x 3 policies, chunked (one emulator
# boot per chunk), resumable via the rows jsonl.
set -u
cd /home/z/my-project/ps1ai
ROWS=scratch/r61/r61_validation_rows.jsonl
for i in $(seq 1 40); do
  OUT=$(timeout 590 python3 scripts/r61e_deploy_loop.py --mode fresh \
        --policies deploy,base,c1 --reps 2 --out "$ROWS" \
        --seconds 540 2>&1 | tail -3)
  echo "=== chunk $i ==="
  echo "$OUT"
  if echo "$OUT" | grep -q ALL_DONE; then
    echo "GRID COMPLETE"
    break
  fi
done
echo "rows: $(wc -l < "$ROWS" 2>/dev/null || echo 0)"

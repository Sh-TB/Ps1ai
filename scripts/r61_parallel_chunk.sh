#!/usr/bin/env bash
# r61_parallel_chunk.sh — one parallel chunk: two emulator workers on
# the two cores, deterministic shard split over the full grid, DISTINCT
# emulator workspaces (savestate files are per-workspace; a shared
# workspace raced and killed a worker with an IndexError — fixed by
# isolation, disclosed in the R61 report).
set -u
cd /home/z/my-project/ps1ai
MAIN=scratch/r61/r61_validation_rows.jsonl
S0=scratch/r61/r61_val_shard0.jsonl
S1=scratch/r61/r61_val_shard1.jsonl
WS=/home/z/my-project/emu/games_homebrew
timeout 545 bash -c "
python3 scripts/r61e_deploy_loop.py --mode fresh \
  --policies base:1,c1:1 --shard 0 --shards 2 \
  --also-done '$MAIN' --out '$S0' --seconds 540 \
  --workspace '$WS/ws_r61_w0' > /tmp/r61_w0.log 2>&1 &
python3 scripts/r61e_deploy_loop.py --mode fresh \
  --policies base:1,c1:1 --shard 1 --shards 2 \
  --also-done '$MAIN' --out '$S1' --seconds 540 \
  --workspace '$WS/ws_r61_w1' > /tmp/r61_w1.log 2>&1 &
wait"
echo "--- shard0 tail:"; tail -n 1 "$S0" 2>/dev/null | cut -c1-110
echo "--- shard1 tail:"; tail -n 1 "$S1" 2>/dev/null | cut -c1-110
grep -h ALL_DONE /tmp/r61_w0.log /tmp/r61_w1.log 2>/dev/null | wc -l
grep -h LoopError /tmp/r61_w0.log /tmp/r61_w1.log 2>/dev/null | head -n 2

#!/usr/bin/env bash
# All Lab 6 JMeter runs, one after another (about 11 minutes, CPU only, mock mode).
#   perf/run_all.sh <out_root>
#
# Load test (manual Exp 8: one server vs a load-balanced group), 50 users for 75 s:
#   L0-direct-1   JMeter -> 1 backend directly          (cost of the proxy itself)
#   L1-proxy-1    JMeter -> proxy -> 1 backend
#   L3-proxy-3    JMeter -> proxy -> 3 backends (round robin)
# Stress test (manual Exp 9: find the limits), 45 s per step, 10 s ramp-up:
#   S1-<users>    proxy -> 1 backend at 25, 100, 200, 400, 800 users (50 = L1-proxy-1)
#   S3-800        proxy -> 3 backends at 800 users
set -euo pipefail
out=${1:?usage: run_all.sh <out_root>}
here=$(cd "$(dirname "$0")" && pwd)
run() { echo "== $1"; "$here/run_scenario.sh" "$@" "$out"; }

run L0-direct-1 1 0 50 15 75
run L1-proxy-1 1 1 50 15 75
run L3-proxy-3 3 1 50 15 75
for users in 25 100 200 400 800; do
  run "S1-$users" 1 1 "$users" 10 45
done
run S3-800 3 1 800 10 45
"$here/../.venv/bin/python" "$here/summarize.py" "$out"

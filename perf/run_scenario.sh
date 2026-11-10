#!/usr/bin/env bash
# Run one JMeter scenario against the Field Service (Software Testing Lab 6).
#
#   perf/run_scenario.sh <name> <backends> <via_proxy> <users> <rampup_s> <duration_s> <out_root>
#
#   backends   number of Field Service processes (ports 8001, 8002, ...), sharing one SQLite file
#   via_proxy  1 = JMeter -> round-robin proxy :8000 -> backends; 0 = JMeter -> :8001 directly
#
# Writes <out_root>/<name>/: results.jtl, dashboard/ (JMeter HTML report), jmeter.log,
# backend-N.log, proxy.log, meta.txt. Only processes started here are stopped at the end.
set -euo pipefail

name=$1 backends=$2 via_proxy=$3 users=$4 rampup=$5 duration=$6 out_root=$7
repo=$(cd "$(dirname "$0")/.." && pwd)
py="$repo/.venv/bin/python"
jmeter_bin=${JMETER_BIN:-$HOME/.local/opt/apache-jmeter-5.6.3/bin/jmeter}
export JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/default}

out="$out_root/$name"
rm -rf "$out"
mkdir -p "$out"
db="$out/field_service.db"
pids=()

cleanup() {
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT

wait_up() {  # wait until $1/api/health answers (max 30 s)
  for _ in $(seq 1 60); do
    curl -sf -m 1 "$1/api/health" >/dev/null && return 0
    sleep 0.5
  done
  echo "server at $1 did not come up" >&2
  return 1
}

cd "$repo"
backend_urls=()
for i in $(seq 1 "$backends"); do
  port=$((8000 + i))
  AGRIAGENT_DB="$db" "$py" -m uvicorn --factory service.main:create_app \
    --host 127.0.0.1 --port "$port" --log-level warning --no-access-log \
    >"$out/backend-$i.log" 2>&1 &
  pids+=($!)
  backend_urls+=("http://127.0.0.1:$port")
done
for url in "${backend_urls[@]}"; do wait_up "$url"; done

if [[ "$via_proxy" == 1 ]]; then
  BACKENDS=$(IFS=,; echo "${backend_urls[*]}") "$py" -m uvicorn perf.round_robin_proxy:app \
    --host 127.0.0.1 --port 8000 --log-level warning --no-access-log >"$out/proxy.log" 2>&1 &
  pids+=($!)
  wait_up "http://127.0.0.1:8000"
  target_port=8000
else
  target_port=8001
fi

{
  echo "scenario=$name backends=$backends via_proxy=$via_proxy users=$users rampup=$rampup duration=$duration"
  echo "target=http://127.0.0.1:$target_port started=$(date -Iseconds)"
  echo "git=$(git -C "$repo" rev-parse --short HEAD) cpus=$(nproc)"
} >"$out/meta.txt"

"$jmeter_bin" -n -t "$repo/perf/field_service_load.jmx" \
  -Jhost=127.0.0.1 -Jport="$target_port" -Jusers="$users" -Jrampup="$rampup" \
  -Jduration="$duration" -Jimage="$repo/perf/data/field_320.jpg" \
  -l "$out/results.jtl" -j "$out/jmeter.log" -e -o "$out/dashboard" >"$out/jmeter-console.txt" 2>&1

echo "finished=$(date -Iseconds)" >>"$out/meta.txt"
echo "runs_stored=$(curl -s "http://127.0.0.1:8001/api/runs?limit=1" | "$py" -c 'import json,sys; print(json.load(sys.stdin)["total"])')" >>"$out/meta.txt"
rm -f "$db" "$db-wal" "$db-shm"  # results are in the JTL; the database is only scratch
tail -n 3 "$out/jmeter-console.txt"

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

docker compose up -d --build
echo "waiting for agentgateway readiness..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:3900/flat -H 'Accept: application/json, text/event-stream' \
      -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","id":0,"method":"tools/list"}' >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

python3 measure.py

echo
echo "Tearing down..."
docker compose down

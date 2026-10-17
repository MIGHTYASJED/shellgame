#!/usr/bin/env bash
# Restart the API in the background. Usage: scripts/dev.sh [db-file]
cd "$(dirname "$0")/.."
[ -f /tmp/shellgame-api.pid ] && kill "$(cat /tmp/shellgame-api.pid)" 2>/dev/null && sleep 1
FALKORDB_LITE_PATH="${1:-.data/real.db}" setsid nohup uvicorn shellgame.api:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
echo $! > /tmp/shellgame-api.pid

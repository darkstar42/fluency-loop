#!/usr/bin/env bash
# Stop the lesson server (scripts/serve.py) if it's running. Invoked by the
# SessionEnd hook in .claude/settings.json so the server dies with Claude Code.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
PIDFILE="$ROOT/.server.pid"

[ -f "$PIDFILE" ] || exit 0
PID="$(cat "$PIDFILE" 2>/dev/null || true)"
if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID" 2>/dev/null || true
fi
rm -f "$PIDFILE"

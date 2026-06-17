#!/usr/bin/env bash
# Run the FULL local analysis suite on Handy takes — fluency + disfluency/prosody
# + pronunciation alignment. All offline. Pass-through args: --since N | --ids a,b | --last N | --json
#
#   scripts/analyze.sh --since 801
#   scripts/analyze.sh --ids 805,806,807,808
#
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
NOISE='Warning|warn|UserWarning|torch|deprecat|FutureWarning|tqdm'

echo "════════════════ FLUENCY (speed · pauses · runs) ════════════════"
"$PY" "$DIR/fluency.py" "$@" 2>&1 | grep -vE "$NOISE" || true
echo
echo "═══════════ DISFLUENCY · PROSODY · RAW PHONES ═══════════"
"$PY" "$DIR/probe.py" "$@" 2>&1 | grep -vE "$NOISE" || true
echo
echo "════════════ PRONUNCIATION ALIGNMENT (German tells) ════════════"
"$PY" "$DIR/pron_align.py" "$@" 2>&1 | grep -vE "$NOISE" || true

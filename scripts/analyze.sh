#!/usr/bin/env bash
# Run the analysis suite on Handy takes. Fluency works for every language and
# always runs; the experimental prosody/pronunciation probes are the English
# (German→English) reference modules and run only when the workspace language is
# English. All offline. Pass-through args: --since N | --ids a,b | --last N | --json
#
#   scripts/analyze.sh --since 801
#   scripts/analyze.sh --ids 805,806,807,808
#
# Language comes from config.json (set during onboarding); override per-run with
# LANG_CODE=ja scripts/analyze.sh ...
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
PY="$DIR/.venv/bin/python"
NOISE='Warning|warn|UserWarning|torch|deprecat|FutureWarning|tqdm'

# Resolve the target language: LANG_CODE env > config.json > generic
TARGET="${LANG_CODE:-}"
if [ -z "$TARGET" ] && [ -f "$ROOT/config.json" ]; then
  TARGET="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("target_language") or "")' "$ROOT/config.json" 2>/dev/null || true)"
fi
LANGARG=(); [ -n "$TARGET" ] && LANGARG=(--lang "$TARGET")

echo "════════════════ FLUENCY (speed · pauses · runs) ════════════════"
"$PY" "$DIR/fluency.py" "${LANGARG[@]}" "$@" 2>&1 | grep -vE "$NOISE" || true

if [ "$TARGET" = "ja" ]; then
  echo
  echo "════════ PRONUNCIATION — Japanese (長音 · ら行 · ふ · 促音 · prosody) ════════"
  "$PY" "$DIR/pron_align_ja.py" "$@" 2>&1 | grep -vE "$NOISE" || true
elif [ -z "$TARGET" ] || [ "$TARGET" = "en" ]; then
  echo
  echo "═══════════ DISFLUENCY · PROSODY · RAW PHONES (English) ═══════════"
  "$PY" "$DIR/probe.py" "$@" 2>&1 | grep -vE "$NOISE" || true
  echo
  echo "════════════ PRONUNCIATION ALIGNMENT (English ← German tells) ════════════"
  "$PY" "$DIR/pron_align.py" "$@" 2>&1 | grep -vE "$NOISE" || true
else
  echo
  echo "(no pronunciation module for '$TARGET' yet — fluency above is language-neutral)"
fi

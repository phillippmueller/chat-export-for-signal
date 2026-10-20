#!/usr/bin/env bash
#
# Try the tool without touching real messages: builds a small, fake Signal
# Desktop database with invented people and messages, then exports it with the
# real script, exactly as a real export would run.
#
# Usage: tests/demo.sh [OUTPUT_FOLDER]     (default: ~/chat-export-demo)
#
# Needs uv; the first run downloads Python and signal-export (pinned version).
# Nothing reads your own Signal data, and nothing asks for keychain access.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SCRIPT="$REPO_ROOT/plugins/chat-export-for-signal/skills/signal-export/scripts/signal-export.sh"
OUT="${1:-$HOME/chat-export-demo}"

# shellcheck disable=SC2016  # the $ is literal text in the pattern
SIGEXPORT_VERSION="$(sed -n 's/^readonly SIGEXPORT_VERSION="\${SIGEXPORT_VERSION:-\(.*\)}"$/\1/p' "$SCRIPT")"

command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Install it with: brew install uv" >&2; exit 1; }
[[ ! -e "$OUT" ]] || { echo "$OUT already exists. Remove it or pass another folder." >&2; exit 1; }

mkdir -p "$OUT"
echo "Creating fake Signal data in $OUT/fake-signal-data"
uv tool run --quiet --python 3.12 --from "signal-export==$SIGEXPORT_VERSION" \
  python "$REPO_ROOT/tests/make_fake_signal.py" "$OUT/fake-signal-data"

bash "$SCRIPT" export --source "$OUT/fake-signal-data" --out "$OUT/export" --single-page

echo ""
echo "Demo export ready: $OUT/export"
echo "  Readable:          open $OUT/export/AnnaMuster/index.html"
echo "  Machine-readable:  $OUT/export/messages.jsonl and manifest.json"

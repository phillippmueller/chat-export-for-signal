#!/usr/bin/env bash
#
# Tests for signal-export.sh. They never touch real Signal data: a fake "uv"
# records the arguments the script would pass to sigexport, and a temporary
# HOME holds a fake Signal data folder.
#
# Run: tests/test_cli.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SCRIPT="$REPO_ROOT/skills/signal-export/scripts/signal-export.sh"

# Resolve symlinks (macOS temp folders live behind /var -> /private/var), so
# paths printed by the script compare equal to the ones built here.
TMP="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT

# Isolate the tests from the caller's environment; CI runners, for example,
# set XDG_CONFIG_HOME, which would move the expected Signal data folder.
unset XDG_CONFIG_HOME SIGNAL_EXPORT_DIR SIGEXPORT_VERSION SIGEXPORT_PYTHON

FAKE_BIN="$TMP/bin"
export HOME="$TMP/home"
export UV_LOG="$TMP/uv.log"
mkdir -p "$FAKE_BIN" "$HOME"

# Fake uv. For the sigexport step it logs its arguments one per line to
# $UV_LOG, prints a chat list for --list-chats and creates the destination
# folder. For the data step (signal_jsonl.py) it logs to $UV_LOG.data, and
# fails when FAKE_DATA_FAIL is set.
cat >"$FAKE_BIN/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then echo "uv 0.0.0-fake"; exit 0; fi
for arg in "$@"; do
  if [[ "$arg" == */signal_jsonl.py ]]; then
    printf '%s\n' "$@" >"$UV_LOG.data"
    [[ -n "${FAKE_DATA_FAIL:-}" ]] && exit 3
    exit 0
  fi
done
printf '%s\n' "$@" >"$UV_LOG"
for arg in "$@"; do
  if [[ "$arg" == "--list-chats" ]]; then echo "Anna | Family Group | Note to Self"; exit 0; fi
done
last="${*: -1}"
[[ "$last" == /* ]] && mkdir -p "$last"
exit 0
EOF
# Fake pgrep: Signal is never running in tests.
printf '#!/usr/bin/env bash\nexit 1\n' >"$FAKE_BIN/pgrep"
chmod +x "$FAKE_BIN/uv" "$FAKE_BIN/pgrep"

case "$(uname -s)" in
  Darwin) SIGNAL_DIR="$HOME/Library/Application Support/Signal" ;;
  *) SIGNAL_DIR="$HOME/.config/Signal" ;;
esac
mkdir -p "$SIGNAL_DIR"
echo '{}' >"$SIGNAL_DIR/config.json"

PATH="$FAKE_BIN:/usr/bin:/bin"
export PATH

passed=0
failed=0

pass() { passed=$((passed + 1)); printf '  ok    %s\n' "$1"; }
fail() {
  failed=$((failed + 1))
  printf '  FAIL  %s\n' "$1"
  [[ -n "${2:-}" ]] && printf '%s\n' "$2" | sed 's/^/        /'
  # On GitHub Actions, also raise an annotation so failures are visible on
  # the run page without opening the log.
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    local detail="${2:-}"
    detail="${detail//$'\n'/%0A}"
    printf '::error title=Test failed: %s::%s\n' "$1" "$detail"
  fi
  return 0
}

# expect <name> <expected exit: 0|nonzero> <text that output must contain> -- cmd...
expect() {
  local name="$1" want="$2" needle="$3"
  shift 4
  local out code=0
  rm -f "$UV_LOG" "$UV_LOG.data"
  out="$("$@" 2>&1)" || code=$?
  if [[ "$want" == "0" && $code -ne 0 ]] || [[ "$want" == "nonzero" && $code -eq 0 ]]; then
    fail "$name (exit $code)" "$out"
  elif [[ -n "$needle" && "$out" != *"$needle"* ]]; then
    fail "$name (missing: $needle)" "$out"
  else
    pass "$name"
  fi
}

# log_has <name> <argument the fake uv must have received> [log file]
log_has() {
  local log="${3:-$UV_LOG}"
  if [[ -f "$log" ]] && grep -qxF -- "$2" "$log"; then
    pass "$1"
  else
    fail "$1" "$(cat "$log" 2>/dev/null || echo "(no call logged)")"
  fi
}

# log_lacks <name> <log file>: the step must not have run
log_lacks() {
  if [[ ! -f "$2" ]]; then pass "$1"; else fail "$1" "$(cat "$2")"; fi
}

echo "signal-export.sh tests"

expect "help prints usage" 0 "Usage:" -- "$SCRIPT" help
expect "no command prints usage" 0 "Commands:" -- "$SCRIPT"
expect "version" 0 "signal-export.sh" -- "$SCRIPT" version
expect "unknown command fails" nonzero "Unknown command" -- "$SCRIPT" frobnicate
expect "doctor ready" 0 "Ready to export" -- "$SCRIPT" doctor

expect "list prints one chat per line" 0 "Family Group" -- "$SCRIPT" list
log_has "list passes --list-chats" "--list-chats"
log_has "list pins signal-export version" "signal-export==3.9.3"
if [[ "$("$SCRIPT" list 2>/dev/null | wc -l | tr -d ' ')" == "3" ]]; then
  pass "list output has 3 lines"
else
  fail "list output has 3 lines" "$("$SCRIPT" list 2>&1)"
fi

expect "export with options" 0 "Done." -- \
  "$SCRIPT" export --chats "Anna,Family Group" --single-page --since 2026-01-01 --no-attachments
log_has "export passes chats" "Anna,Family Group"
log_has "export passes --paginate" "--paginate"
log_has "export passes since as --start" "2026-01-01"
log_has "export passes --no-attachments" "--no-attachments"
if [[ "$(tail -n 1 "$UV_LOG")" == "$HOME/signal-chats/export-"* ]]; then
  pass "export defaults to a dated folder in ~/signal-chats"
else
  fail "export defaults to a dated folder in ~/signal-chats" "$(tail -n 1 "$UV_LOG")"
fi

log_has "data step runs after export" "--out" "$UV_LOG.data"
log_has "data step gets the same chats" "Anna,Family Group" "$UV_LOG.data"
log_has "data step gets the same start date" "2026-01-01" "$UV_LOG.data"
log_has "data step knows attachments were skipped" "--no-attachments" "$UV_LOG.data"
log_has "data step pins signal-export version" "signal-export==3.9.3" "$UV_LOG.data"

expect "export passthrough after --" 0 "Done." -- \
  "$SCRIPT" export --out "$HOME/out-pass" -- --include-empty
log_has "passthrough reaches sigexport" "--include-empty"
log_has "passthrough filter reaches data step" "--include-empty" "$UV_LOG.data"

expect "export --no-data" 0 "Done." -- "$SCRIPT" export --out "$HOME/out-nodata" --no-data
log_lacks "--no-data skips the data step" "$UV_LOG.data"

expect "failed data step is reported" nonzero "machine-readable files failed" -- \
  env FAKE_DATA_FAIL=1 "$SCRIPT" export --out "$HOME/out-datafail"
if [[ -d "$HOME/out-datafail" ]]; then
  pass "readable export is kept when the data step fails"
else
  fail "readable export is kept when the data step fails"
fi

expect "export refuses existing folder" nonzero "already exists" -- \
  "$SCRIPT" export --out "$HOME/out-pass"
expect "export refuses repository folder" nonzero "Refusing to export" -- \
  "$SCRIPT" export --out "$REPO_ROOT/exports"
expect "export rejects unknown option" nonzero "Unknown option" -- \
  "$SCRIPT" export --bogus
expect "export rejects --from" nonzero "only works with update" -- \
  "$SCRIPT" export --from "$HOME"

expect "update needs --from" nonzero "update needs --from" -- "$SCRIPT" update
expect "update rejects missing earlier export" nonzero "not found" -- \
  "$SCRIPT" update --from "$HOME/nope"
expect "update merges earlier export" 0 "Merging in earlier export" -- \
  "$SCRIPT" update --from "$HOME/out-pass" --out "$HOME/out-update"
log_has "update passes --old" "--old"

mv "$SIGNAL_DIR/config.json" "$TMP/config.json.bak"
expect "missing Signal data is reported" nonzero "No Signal Desktop data" -- "$SCRIPT" list
mv "$TMP/config.json.bak" "$SIGNAL_DIR/config.json"

printf '#!/usr/bin/env bash\nexit 0\n' >"$FAKE_BIN/pgrep"
expect "running Signal blocks export" nonzero "Signal is still running" -- "$SCRIPT" list
printf '#!/usr/bin/env bash\nexit 1\n' >"$FAKE_BIN/pgrep"

rm "$FAKE_BIN/uv"
expect "missing uv is reported" nonzero "uv is not installed" -- "$SCRIPT" list

echo
echo "$passed passed, $failed failed"
((failed == 0))

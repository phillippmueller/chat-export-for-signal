#!/usr/bin/env bash
#
# signal-export.sh - export Signal Desktop chats to HTML, Markdown and JSON.
#
# Besides the readable export, it writes machine-readable files with stable
# IDs (people.jsonl, chats.jsonl, messages.jsonl, manifest.json) using the
# companion script signal_jsonl.py.
#
# A thin, safe wrapper around signal-export by Chris Arderne
# (https://github.com/carderne/signal-export, MIT). It runs that tool through
# uv, which builds and caches an isolated Python environment on first use, so
# there is nothing to install by hand apart from uv itself.
#
# Usage: signal-export.sh <command> [options]    (run with "help" for details)

set -euo pipefail

readonly VERSION="0.2.0"

# Pinned so a new upstream release cannot silently change behaviour.
# Override per run, e.g. SIGEXPORT_VERSION=3.9.4 signal-export.sh list
readonly SIGEXPORT_VERSION="${SIGEXPORT_VERSION:-3.9.3}"
readonly SIGEXPORT_PYTHON="${SIGEXPORT_PYTHON:-3.12}"
readonly OUT_ROOT="${SIGNAL_EXPORT_DIR:-$HOME/signal-chats}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR

# ---------------------------------------------------------------- helpers ---

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*" >&2
}

usage() {
  cat <<EOF
signal-export.sh $VERSION - export Signal Desktop chats (HTML, Markdown, JSON)

Usage:
  signal-export.sh <command> [options]

Commands:
  doctor              Check that everything is ready (changes nothing)
  list                Show the exact names of all chats
  export              Export chats to a new folder
  update              Export again and merge in an earlier export
  version             Show version information
  help                Show this help

Options for export and update:
  --chats "A,B"       Only these chats, comma-separated, names as shown by
                      "list" (default: all chats)
  --out DIR           Output folder; must not exist yet
                      (default: $OUT_ROOT/export-<date-time>)
  --single-page       Put each chat on one HTML page instead of pages of 100
  --since DATE        Only messages from DATE on (ISO-8601, e.g. 2026-01-31
                      or 2026-01-31T09:00:00+01:00)
  --until DATE        Only messages up to DATE (same format)
  --no-attachments    Skip copying images, voice notes and files
  --no-data           Skip the machine-readable files (people.jsonl,
                      chats.jsonl, messages.jsonl, manifest.json)
  --source DIR        Signal data folder, if not in the standard place
  --from DIR          (update only, required) the earlier export to merge
  -- ARGS             Pass any further options straight to sigexport

Options for list:
  --source DIR        As above

Environment variables:
  SIGNAL_EXPORT_DIR   Default output root (now: $OUT_ROOT)
  SIGEXPORT_VERSION   signal-export version to use (now: $SIGEXPORT_VERSION)
  SIGEXPORT_PYTHON    Python version uv should use (now: $SIGEXPORT_PYTHON)

Before list, export or update, quit Signal completely (Cmd+Q on a Mac).
The first run on macOS asks for keychain access to "Signal Safe Storage";
click Allow, or the database cannot be decrypted.

Exports contain your private messages unencrypted. Keep them somewhere safe.
EOF
}

os_name() {
  uname -s
}

default_signal_dir() {
  case "$(os_name)" in
    Darwin) printf '%s\n' "$HOME/Library/Application Support/Signal" ;;
    Linux) printf '%s\n' "${XDG_CONFIG_HOME:-$HOME/.config}/Signal" ;;
    *) die "Unsupported operating system: $(os_name). Only macOS and Linux are supported." ;;
  esac
}

signal_is_running() {
  case "$(os_name)" in
    Darwin) pgrep -f '/Signal.app/Contents/MacOS/Signal' >/dev/null 2>&1 ;;
    Linux) pgrep -x signal-desktop >/dev/null 2>&1 || pgrep -f '/signal-desktop' >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}

require_uv() {
  command -v uv >/dev/null 2>&1 && return 0
  die "uv is not installed. Install it with:  brew install uv
       (or see https://docs.astral.sh/uv/getting-started/installation/)"
}

require_signal_quit() {
  if signal_is_running; then
    die "Signal is still running, so its database is locked.
       Quit it completely (Cmd+Q on a Mac; closing the window is not enough) and run this again."
  fi
}

require_signal_data() {
  local dir="$1"
  [[ -f "$dir/config.json" ]] && return 0
  die "No Signal Desktop data found in: $dir
       Install Signal Desktop, link it to your phone and open it once,
       or point to the right folder with --source DIR."
}

# Prints the absolute, symlink-free path of DIR even if DIR does not exist
# yet, by resolving its nearest existing parent.
absolute_path() {
  local path="$1" suffix=""
  path="${path/#\~/$HOME}"
  [[ "$path" == /* ]] || path="$PWD/$path"
  while [[ ! -d "$path" ]]; do
    suffix="/$(basename "$path")$suffix"
    path="$(dirname "$path")"
  done
  printf '%s%s\n' "$(cd "$path" && pwd -P)" "$suffix"
}

# Refuses output folders inside this tool's own repository, so private
# messages can never end up in a git commit.
require_out_outside_repo() {
  local out="$1" repo_root
  repo_root="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
  [[ -n "$repo_root" ]] || return 0
  repo_root="$(cd "$repo_root" && pwd -P)"
  case "$out/" in
    "$repo_root"/*) die "Refusing to export into this tool's repository ($repo_root).
       Choose an output folder outside it, e.g. --out ~/signal-chats/my-export" ;;
  esac
}

# Writes people.jsonl, chats.jsonl, messages.jsonl and manifest.json, using
# the same pinned signal-export package as a library.
run_data_step() {
  uv run --quiet --no-project \
    --python "$SIGEXPORT_PYTHON" \
    --with "signal-export==$SIGEXPORT_VERSION" \
    python "$SCRIPT_DIR/signal_jsonl.py" --exporter-version "$SIGEXPORT_VERSION" "$@"
}

run_sigexport() {
  uv tool run --quiet \
    --python "$SIGEXPORT_PYTHON" \
    --from "signal-export==$SIGEXPORT_VERSION" \
    sigexport "$@"
}

# --------------------------------------------------------------- commands ---

cmd_doctor() {
  local ok=1 signal_dir
  signal_dir="$(default_signal_dir)"

  info "signal-export.sh $VERSION (signal-export $SIGEXPORT_VERSION, Python $SIGEXPORT_PYTHON)"
  info "System:        $(os_name)"

  if command -v uv >/dev/null 2>&1; then
    info "uv:            ok ($(uv --version 2>/dev/null))"
  else
    info "uv:            MISSING - install with: brew install uv"
    ok=0
  fi

  if [[ -f "$signal_dir/config.json" ]]; then
    info "Signal data:   ok ($signal_dir)"
  else
    info "Signal data:   NOT FOUND at $signal_dir (use --source DIR if it lives elsewhere)"
    ok=0
  fi

  if signal_is_running; then
    info "Signal app:    RUNNING - quit it (Cmd+Q) before exporting"
    ok=0
  else
    info "Signal app:    not running, good"
  fi

  info "Output root:   $OUT_ROOT"

  if ((ok)); then
    info "Ready to export."
  else
    info "Fix the items above, then run doctor again."
    return 1
  fi
}

cmd_list() {
  local source=""
  while (($#)); do
    case "$1" in
      --source)
        [[ $# -ge 2 ]] || die "--source needs a folder"
        source="$2"
        shift 2
        ;;
      *) die "Unknown option for list: $1 (see: signal-export.sh help)" ;;
    esac
  done

  require_uv
  require_signal_data "${source:-$(default_signal_dir)}"
  require_signal_quit

  local args=(--list-chats) names
  [[ -n "$source" ]] && args+=(--source "$source")
  names="$(run_sigexport "${args[@]}")"
  # sigexport prints names separated by " | "; print one per line instead.
  printf '%s\n' "${names// | /$'\n'}"
}

# Shared by export and update. $1 is the mode ("export" or "update").
cmd_export() {
  local mode="$1"
  shift

  local chats="" out="" since="" until="" source="" from=""
  local single_page=0 attachments=1 data=1
  local passthrough=()

  while (($#)); do
    case "$1" in
      --chats | --out | --since | --until | --source | --from)
        [[ $# -ge 2 ]] || die "$1 needs a value"
        case "$1" in
          --chats) chats="$2" ;;
          --out) out="$2" ;;
          --since) since="$2" ;;
          --until) until="$2" ;;
          --source) source="$2" ;;
          --from) from="$2" ;;
        esac
        shift 2
        ;;
      --single-page) single_page=1; shift ;;
      --no-attachments) attachments=0; shift ;;
      --no-data) data=0; shift ;;
      --) shift; passthrough=("$@"); break ;;
      *) die "Unknown option for $mode: $1 (see: signal-export.sh help)" ;;
    esac
  done

  if [[ "$mode" == "update" ]]; then
    [[ -n "$from" ]] || die "update needs --from DIR, the earlier export to merge"
    from="$(absolute_path "$from")"
    [[ -d "$from" ]] || die "Earlier export not found: $from"
  elif [[ -n "$from" ]]; then
    die "--from only works with update"
  fi

  [[ -n "$out" ]] || out="$OUT_ROOT/export-$(date +%Y-%m-%d_%H%M%S)"
  out="$(absolute_path "$out")"
  [[ ! -e "$out" ]] || die "Output folder already exists: $out
       Choose a new folder with --out, or delete the old one first."
  require_out_outside_repo "$out"

  require_uv
  require_signal_data "${source:-$(default_signal_dir)}"
  require_signal_quit

  local args=()
  [[ -n "$chats" ]] && args+=(--chats "$chats")
  [[ -n "$since" ]] && args+=(--start "$since")
  [[ -n "$until" ]] && args+=(--end "$until")
  [[ -n "$source" ]] && args+=(--source "$source")
  [[ -n "$from" ]] && args+=(--old "$from")
  ((single_page)) && args+=(--paginate 0)
  ((attachments)) || args+=(--no-attachments)
  # The ${arr[@]+...} form keeps empty arrays safe under "set -u" in the
  # bash 3.2 that macOS ships.
  args+=(${passthrough[@]+"${passthrough[@]}"})

  info "Exporting ${chats:-all chats} to: $out"
  [[ -n "$from" ]] && info "Merging in earlier export: $from (it stays unchanged)"
  run_sigexport ${args[@]+"${args[@]}"} "$out"

  if [[ ! -d "$out" ]]; then
    info "Nothing was exported (no matching chats or messages)."
    return 0
  fi

  local data_failed=0
  if ((data)); then
    local data_args=(--out "$out")
    [[ -n "$chats" ]] && data_args+=(--chats "$chats")
    [[ -n "$since" ]] && data_args+=(--since "$since")
    [[ -n "$until" ]] && data_args+=(--until "$until")
    [[ -n "$source" ]] && data_args+=(--source "$source")
    ((attachments)) || data_args+=(--no-attachments)
    # Keep the data files in step with the export's upstream filters.
    local arg
    for arg in ${passthrough[@]+"${passthrough[@]}"}; do
      case "$arg" in
        --include-empty | --include-disappearing) data_args+=("$arg") ;;
      esac
    done
    info "Writing machine-readable data (messages.jsonl, manifest.json, ...)"
    run_data_step "${data_args[@]}" || data_failed=1
  fi

  info ""
  info "Done. Your export is in: $out"
  info "Open the .html file of a chat in your browser to read it."
  info "Reminder: these files are unencrypted private messages."
  if ((data_failed)); then
    die "The readable export is complete, but writing the machine-readable files failed (see above)."
  fi
}

cmd_version() {
  printf 'signal-export.sh %s\n' "$VERSION"
  printf 'signal-export    %s (pinned)\n' "$SIGEXPORT_VERSION"
  printf 'Python           %s (via uv)\n' "$SIGEXPORT_PYTHON"
}

# ------------------------------------------------------------------- main ---

main() {
  local cmd="${1:-help}"
  (($#)) && shift
  case "$cmd" in
    doctor) cmd_doctor "$@" ;;
    list) cmd_list "$@" ;;
    export) cmd_export export "$@" ;;
    update) cmd_export update "$@" ;;
    version | --version) cmd_version ;;
    help | -h | --help) usage ;;
    *) usage >&2; die "Unknown command: $cmd" ;;
  esac
}

main "$@"

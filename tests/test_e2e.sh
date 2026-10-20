#!/usr/bin/env bash
#
# End-to-end test: runs the real script, the real signal-export tool and the
# real data step through uv against a fake, encrypted Signal database
# (tests/make_fake_signal.py). Needs uv and internet access on the first run.
#
# Run: tests/test_e2e.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SCRIPT="$REPO_ROOT/skills/signal-export/scripts/signal-export.sh"
# The pinned version, read from the script so the fixture uses the same one.
# shellcheck disable=SC2016  # the $ is literal text in the pattern
SIGEXPORT_VERSION="$(sed -n 's/^readonly SIGEXPORT_VERSION="\${SIGEXPORT_VERSION:-\(.*\)}"$/\1/p' "$SCRIPT")"
[[ -n "$SIGEXPORT_VERSION" ]] || { echo "Could not read the pinned signal-export version" >&2; exit 1; }

TMP="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT
unset XDG_CONFIG_HOME SIGNAL_EXPORT_DIR SIGEXPORT_PYTHON

echo "Building fake Signal data (signal-export $SIGEXPORT_VERSION)"
uv run --quiet --no-project --python 3.12 --with "signal-export==$SIGEXPORT_VERSION" \
  python "$REPO_ROOT/tests/make_fake_signal.py" "$TMP/Signal"

echo "Exporting"
"$SCRIPT" export --source "$TMP/Signal" --out "$TMP/first" --chats "Anna Muster,Family Group" --single-page
echo "Updating"
"$SCRIPT" update --source "$TMP/Signal" --from "$TMP/first" --out "$TMP/second"

echo "Checking results"
python3 - "$TMP/first" "$TMP/second" <<'EOF'
import hashlib, json, sys
from pathlib import Path

def check(out: Path, chats: int, messages: int) -> None:
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["chats"] == chats, manifest["counts"]
    assert manifest["counts"]["messages"] == messages, manifest["counts"]
    for name, info in manifest["files"].items():
        data = (out / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == info["sha256"], f"checksum mismatch: {name}"
        assert len(data.decode("utf-8").splitlines()) == info["records"], name
    for line in (out / "chats.jsonl").read_text(encoding="utf-8").splitlines():
        chat = json.loads(line)
        folder = out / chat["folder"]
        assert (folder / "index.html").is_file(), f"no HTML for chat folder {folder}"
    ids = set()
    for line in (out / "messages.jsonl").read_text(encoding="utf-8").splitlines():
        msg = json.loads(line)
        assert msg["message_id"] not in ids, "duplicate message_id"
        ids.add(msg["message_id"])
        assert msg["sender_id"], f"message without sender: {msg['message_id']}"
        assert msg["sent_at"].endswith("Z")
        for att in msg["attachments"]:
            assert att["path"] and (out / att["path"]).is_file(), f"attachment missing: {att}"
    print(f"  ok    {out.name}: {chats} chats, {messages} messages, checksums and files verified")

check(Path(sys.argv[1]), chats=2, messages=4)
check(Path(sys.argv[2]), chats=3, messages=5)
EOF

echo "End-to-end test passed"

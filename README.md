# signal-skill

Export your Signal Desktop chats to readable files, either yourself from the
Terminal or by asking Claude.

- **HTML** you open in a browser, formatted like the chat, with images inline
- **Markdown** for notes and archives
- **Machine-readable data**: `messages.jsonl`, `chats.jsonl` and
  `people.jsonl` with stable IDs, plus a `manifest.json` with counts and
  checksums, ready for a database, pandas or an AI pipeline
- **Attachments** (images, voice notes, files) copied alongside
- **Updates**: merge newer messages into an earlier export without touching it

Runs on **macOS and Linux**, locally, on the computer where Signal Desktop is
installed. Nothing is uploaded anywhere.

## Quick start

You need [Signal Desktop](https://signal.org/download/) (linked to your phone)
and [uv](https://docs.astral.sh/uv/):

```bash
brew install uv          # macOS; other systems: see the uv docs
git clone https://github.com/phillippmueller/signal-skill.git
cd signal-skill
```

Quit Signal completely (Cmd+Q on a Mac), then:

```bash
./skills/signal-export/scripts/signal-export.sh doctor   # checks everything, changes nothing
./skills/signal-export/scripts/signal-export.sh list     # exact chat names
./skills/signal-export/scripts/signal-export.sh export --chats "Anna" --single-page
```

On the first run macOS asks for access to **"Signal Safe Storage"** in your
keychain. Click **Allow**; the tool needs this key to decrypt your local
database. The first run also takes a bit longer while uv sets up Python and the
export tool; later runs reuse them.

Your export lands in a new dated folder under `~/signal-chats/`:

```
export-2026-10-20_141500/
├── manifest.json        what's inside: versions, filters, counts, checksums
├── messages.jsonl       one message per line, with stable IDs
├── chats.jsonl          one chat per line
├── people.jsonl         one person per line
└── AnnaMuster/
    ├── index.html       open this in your browser
    ├── chat.md
    └── media/           attachments
```

Tip: add an alias to your `~/.zshrc` to run it from anywhere:

```bash
alias sigx="$HOME/path/to/signal-skill/skills/signal-export/scripts/signal-export.sh"
```

## Commands

| Command | What it does |
| :- | :- |
| `doctor` | Checks uv, Signal's data folder and whether Signal is running |
| `list` | Lists all chat names |
| `export` | Exports chats to a new folder |
| `update --from DIR` | Exports again and merges in an earlier export (kept unchanged) |
| `help` | Shows all options |

Useful options for `export` and `update`:

```bash
--chats "Anna,Family Group"   # only these chats (default: all)
--single-page                 # one HTML page per chat instead of pages of 100
--since 2026-01-01            # only messages from this date
--until 2026-03-31            # only messages up to this date
--out ~/signal-chats/anna     # your own output folder (must not exist yet)
--no-attachments              # skip images and files
--no-data                     # skip the .jsonl files and manifest.json
-- --include-empty            # anything after -- goes straight to sigexport
```

## Machine-readable data

The `.jsonl` files hold one JSON object per line and map one-to-one onto
database tables, linked by IDs:

```json
{"message_id": "…", "signal_key": "<sender>:<ms>", "chat_id": "…", "sender_id": "<uuid>",
 "sender_name": "Anna Muster", "direction": "incoming", "sent_at": "2026-01-01T00:01:00.000Z",
 "text": "Hi! Are we still on for Friday?", "reply_to": null, "reactions": [], "attachments": [], …}
```

People are identified by their Signal service ID, which stays the same across
devices and name changes, and messages carry both a local ID for upserting
repeated exports and a cross-device key. Query them directly, for example with
DuckDB:

```sql
SELECT sender_name, count(*) FROM 'messages.jsonl' GROUP BY 1 ORDER BY 2 DESC;
```

Full field reference and loading examples:
[data format](skills/signal-export/reference/data-format.md).

## Use it with Claude

The repository is also a Claude plugin with a skill, so Claude can run the
export for you when you say something like *"export my Signal chat with
Anna"*. Claude needs a shell on the computer where Signal runs: Claude Code
there, or the Claude desktop app with that computer linked.

**In the Claude app** (paid plans): open **Customize → Plugins**, click
**Add → Add marketplace → Add from a repository**, enter
`phillippmueller/signal-skill`, and install **signal-export**.

**As a single skill** (any plan with code execution on): download
`signal-export-skill.zip` from the
[latest release](https://github.com/phillippmueller/signal-skill/releases/latest),
then open **Customize → Skills → + → Create skill → Upload a skill** and
choose the ZIP.

**In Claude Code:**

```bash
claude plugin marketplace add phillippmueller/signal-skill
claude plugin install signal-export@signal-skill
```

When the skill's files aren't on the computer with Signal (for example when
you use it from the Claude app), Claude asks before cloning this repository to
`~/signal-skill` on that computer and runs the scripts from there. Either way,
Claude asks you to quit Signal and to click Allow on the keychain prompt;
those steps stay with you on purpose.

## Privacy

Exports contain **your and other people's private messages, unencrypted**.

- Store them somewhere safe, and delete them when you no longer need them.
- The people in a chat didn't agree to their messages being stored elsewhere.
  Think before uploading exports to cloud drives, databases or AI tools.
- The script refuses to write exports inside this repository, and
  `.gitignore` blocks common export folders, so they can't be committed by
  accident.

## Limits

- Only messages held by Signal Desktop are exported: what was transferred when
  you linked it to your phone, plus everything received since.
- Windows is not supported.
- A new Signal Desktop release can occasionally break the export until the
  underlying tool is updated. See
  [troubleshooting](skills/signal-export/reference/troubleshooting.md).

## How it works

[`signal-export.sh`](skills/signal-export/scripts/signal-export.sh) is a small,
defensive wrapper around
[signal-export](https://github.com/carderne/signal-export) by Chris Arderne,
which does the decryption and the HTML and Markdown export. The wrapper pins a
tested version, runs it through uv in an isolated environment, checks that
Signal is closed, and keeps exports out of the repository.
[`signal_jsonl.py`](skills/signal-export/scripts/signal_jsonl.py) then reads
the same database through signal-export's library to write the
machine-readable files.

```
.claude-plugin/          plugin and marketplace manifests
skills/signal-export/
  SKILL.md               instructions Claude follows
  scripts/               the executable scripts
  reference/             data format and troubleshooting
tests/                   tests (no real Signal data needed)
```

## Development

```bash
tests/test_cli.sh                                    # script tests (no network)
python3 -m unittest discover -s tests -p "test_*.py" # converter tests (no network)
tests/test_e2e.sh                                    # full run on a fake Signal database (uv, network)
shellcheck skills/signal-export/scripts/*.sh tests/*.sh
claude plugin validate .                             # check the plugin manifests
```

Every push runs these checks on macOS and Linux via GitHub Actions.

## License

[MIT](LICENSE) © Philip Mueller. signal-export is a separate project under its
own MIT license; this repository installs it at runtime and doesn't include its
code.

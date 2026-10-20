# Chat Export for Signal (unofficial)

Export your Signal Desktop chats to files on your own computer, either by
asking Claude or yourself from the Terminal.

- **HTML** you open in a browser, formatted like the chat, with images inline
- **Markdown** for notes and archives
- **Machine-readable data**: `messages.jsonl`, `chats.jsonl` and
  `people.jsonl` with stable IDs, plus a `manifest.json` with counts and
  checksums, ready for a database, pandas or an AI pipeline
- **Attachments** (images, voice notes, files) copied alongside
- **Updates**: merge newer messages into an earlier export without touching it

Runs on **macOS and Linux**, locally, on the computer where Signal Desktop is
installed. Nothing is uploaded anywhere.

> This is an independent, unofficial tool. It is not made by, endorsed by or
> affiliated with Signal or the Signal Technology Foundation.

## Examples

Once installed as a Claude plugin or skill, ask Claude:

- *"Export my Signal chat with Anna."*
- *"Back up the Family Group chat from this year as one page per chat, without the photos."*
- *"Update last month's Signal export with the new messages, then load messages.jsonl into DuckDB and show me who wrote the most."*

Claude checks that everything is ready, finds the exact chat name, runs the
export and tells you where the files are. It asks you to quit Signal and to
click Allow on the macOS keychain prompt; those two steps stay with you on
purpose.

## Install

You need [Signal Desktop](https://signal.org/download/), linked to your phone,
and [uv](https://docs.astral.sh/uv/) (`brew install uv` on a Mac). Claude needs
a shell on the computer where Signal runs: the Claude desktop app with that
computer linked, or Claude Code on it.

**Claude app** (paid plans): open **Customize → Plugins**, click **Add → Add
marketplace → Add from a repository**, enter
`phillippmueller/chat-export-for-signal`, and install **Chat Export for
Signal**.

**Single skill upload** (any plan with code execution on): download
`chat-export-for-signal-skill.zip` from the
[latest release](https://github.com/phillippmueller/chat-export-for-signal/releases/latest),
then open **Customize → Skills → + → Create skill → Upload a skill**.

**Claude Code:**

```bash
claude plugin marketplace add phillippmueller/chat-export-for-signal
claude plugin install chat-export-for-signal@chat-export-for-signal
```

When Claude works from the app, the plugin's files live with Claude rather
than on your computer. Claude then asks before copying its two scripts to
`~/.chat-export-for-signal/` on your computer and runs them from there.

## Use it without Claude

```bash
git clone https://github.com/phillippmueller/chat-export-for-signal.git
cd chat-export-for-signal
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

### Commands

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

## Try it with sample data

`tests/demo.sh` builds a small fake Signal database with invented people and
messages and exports it with the real script. It never reads your own Signal
data and doesn't ask for keychain access:

```bash
tests/demo.sh                 # writes to ~/chat-export-demo
open ~/chat-export-demo/export/AnnaMuster/index.html
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

## What this plugin runs and accesses

Everything happens on your computer. In detail:

- **Downloads, through uv, on first use:** a Python 3.12 runtime and the
  [signal-export](https://pypi.org/project/signal-export/) package, pinned to
  version 3.9.3, with its dependencies, from the official Python Package
  Index. Nothing else is downloaded.
- **Reads:** Signal Desktop's data folder
  (`~/Library/Application Support/Signal` on macOS, `~/.config/Signal` on
  Linux), including its encrypted database and attachments. On macOS it reads
  the database key from your keychain entry "Signal Safe Storage", which macOS
  only allows after you click Allow.
- **Writes:** only the new export folder you choose (by default a new folder
  under `~/signal-chats/`). It never changes Signal's own data, and it refuses
  to write into this repository.
- **Runs:** the two scripts in
  [`skills/signal-export/scripts/`](skills/signal-export/scripts/), and
  `pgrep` to check whether Signal is running.
- **Sends:** nothing. There is no telemetry, no analytics and no network
  connection apart from the uv downloads above.

When you use it through Claude, Claude reads the script's output (chat names,
counts, folder paths) to report back. The skill tells Claude not to read or
quote message content unless you ask for it.

## Privacy

Exports contain **your and other people's private messages and phone numbers,
unencrypted**.

- Store them somewhere safe, and delete them when you no longer need them.
- The people in a chat didn't agree to their messages being stored elsewhere.
  Think before uploading exports to cloud drives, databases or AI tools.
- The script refuses to write exports inside this repository, and
  `.gitignore` blocks common export folders, so they can't be committed by
  accident.

See [PRIVACY.md](PRIVACY.md) for the privacy statement.

## Limits

- Only messages held by Signal Desktop are exported: what was transferred when
  you linked it to your phone, plus everything received since.
- Windows is not supported.
- A new Signal Desktop release can occasionally break the export until the
  underlying tool is updated. See
  [troubleshooting](skills/signal-export/reference/troubleshooting.md).

## Support

- **Questions and bugs:** [open an issue](https://github.com/phillippmueller/chat-export-for-signal/issues)
- **Email:** [philip.mueller.bueckeburg@gmail.com](mailto:philip.mueller.bueckeburg@gmail.com)
- **Security problems:** please report them privately, see [SECURITY.md](SECURITY.md)

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
  scripts/               the two scripts
  reference/             data format and troubleshooting
tests/                   tests and the sample-data demo (no real Signal data)
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
code. "Signal" is a trademark of its owner and is used here only to describe
what the tool works with.

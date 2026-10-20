# Chat Export for Signal (unofficial)

Export your Signal Desktop chats to files on your own computer, just by asking
Claude. You get readable HTML and Markdown for each chat, the attachments, and
machine-readable JSON Lines files with stable IDs and a manifest, ready for a
database, a spreadsheet or further analysis. Earlier exports can be updated
with newer messages.

> This is an independent, unofficial tool. It is not made by, endorsed by or
> affiliated with Signal or the Signal Technology Foundation.

## Examples

- *"Export my Signal chat with Anna."*
- *"Back up the Family Group chat from this year as one page per chat, without the photos."*
- *"Update last month's Signal export with the new messages, then load messages.jsonl into DuckDB and show me who wrote the most."*

Claude checks that everything is ready, finds the exact chat name, runs the
export and tells you where the files are. It asks you to quit Signal and to
click Allow on the macOS keychain prompt; those two steps stay with you on
purpose.

## Install

In the Claude app, add it from the plugin directory, or under **Customize →
Plugins → Add → Add marketplace → Add from a repository** with
`phillippmueller/chat-export-for-signal`. In Claude Code:

```
/plugin install chat-export-for-signal --marketplace phillippmueller/chat-export-for-signal
```

## Requirements

- Signal Desktop on macOS or Linux, linked to your phone
- [uv](https://docs.astral.sh/uv/) (`brew install uv` on a Mac)
- Claude with a shell on that computer: Claude Code there, or the Claude
  desktop app with that computer linked

When Claude works from the app, the plugin's files live with Claude rather
than on your computer. Claude then asks before copying the plugin's two
scripts to `~/.chat-export-for-signal/` on your computer and runs them from
there.

## What this plugin runs and accesses

Everything happens on your computer.

- **Downloads, through uv, on first use:** a Python 3.12 runtime and the
  [signal-export](https://pypi.org/project/signal-export/) package, pinned to
  version 3.9.3, with its dependencies, from the official Python Package
  Index. Nothing else is downloaded.
- **Reads:** Signal Desktop's data folder (`~/Library/Application
  Support/Signal` on macOS, `~/.config/Signal` on Linux), including its
  encrypted database and attachments. On macOS it reads the database key from
  the keychain entry "Signal Safe Storage", which macOS only allows after you
  click Allow.
- **Writes:** only the new export folder you choose, by default a new folder
  under `~/signal-chats/`. It never changes Signal's own data.
- **Runs:** the two scripts in `skills/signal-export/scripts/`, and `pgrep`
  to check whether Signal is running.
- **Sends:** nothing. There is no telemetry, no analytics and no network
  connection apart from the uv downloads above.

Claude reads the script's output (chat names, counts, folder paths) to report
back. The skill tells Claude not to read or quote message content unless you
ask for it.

## Privacy

Exports contain your and other people's private messages and phone numbers,
unencrypted. Store them safely, and think before uploading them anywhere: the
people in your chats didn't agree to their messages being stored elsewhere.
Full statement:
[PRIVACY.md](https://github.com/phillippmueller/chat-export-for-signal/blob/main/PRIVACY.md).

## Limits

Only messages held by Signal Desktop are exported: what was transferred when
you linked it to your phone, plus everything received since. Windows is not
supported.

## Support

- Documentation, data format and source:
  https://github.com/phillippmueller/chat-export-for-signal
- Questions and bugs:
  [open an issue](https://github.com/phillippmueller/chat-export-for-signal/issues)
- Email: [philip.mueller.bueckeburg@gmail.com](mailto:philip.mueller.bueckeburg@gmail.com)
- Security problems: report privately, see
  [SECURITY.md](https://github.com/phillippmueller/chat-export-for-signal/blob/main/SECURITY.md)

## License

MIT © Philip Mueller. Built on
[signal-export](https://github.com/carderne/signal-export) by Chris Arderne
(MIT), which is installed at runtime and not included here. "Signal" is a
trademark of its owner and is used only to describe what the tool works with.

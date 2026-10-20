# Troubleshooting

## "Signal is still running"

Signal locks its database while open. Quit it completely: Cmd+Q on a Mac, or
right-click the Dock icon and choose Quit. If the message persists, open
Activity Monitor, search for "Signal" and quit any leftover processes.

## "uv is not installed"

Install uv once:

- macOS: `brew install uv`
- Any system: see https://docs.astral.sh/uv/getting-started/installation/

The first export then takes a little longer while uv downloads Python and the
export tool. Later runs reuse that environment.

## Keychain or decryption errors (macOS)

You probably clicked Deny on the "Signal Safe Storage" prompt. Run the command
again and click Allow. Alternatively, open Keychain Access, find "Signal Safe
Storage", and allow your terminal app under Access Control.

## "No Signal Desktop data found"

Signal Desktop must be installed, linked to your phone and opened at least
once. If its data lives in a non-standard place, pass it with
`--source DIR`. The folder must contain `config.json` and a `sql` folder.

Standard locations:

- macOS: `~/Library/Application Support/Signal`
- Linux: `~/.config/Signal`

Linux installs via Flatpak or Snap keep their data elsewhere, so use
`--source` for those.

## "Output folder already exists"

Each export goes into a new folder so nothing gets overwritten. Pick another
name with `--out`, or delete the old folder first.

## "Refusing to export into this tool's repository"

A safety check: exports are private messages and must never be committed to
git. Choose an output folder outside the repository.

## A chat is missing from the list

Empty chats and disappearing messages are skipped by default. To include
them, pass the upstream options after `--`:

```bash
scripts/signal-export.sh export --chats "Name" -- --include-empty --include-disappearing
```

Also check that the messages appear in Signal Desktop itself; anything that
exists only on your phone can't be exported.

## The export tool broke after a Signal update

Signal sometimes changes its database format. Check for a new release of this
plugin first. If there is none yet, see
https://github.com/carderne/signal-export/releases and report the problem in
this plugin's issue tracker, so the pinned version can be updated and tested.

## Any other option

Everything after `--` is passed straight to the underlying `sigexport`
command. Its full option list is in the
[signal-export README](https://github.com/carderne/signal-export#usage).

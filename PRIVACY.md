# Privacy statement

Chat Export for Signal is a local tool. Its author collects no data from you.

## What the tool processes

To export your chats, the tool reads Signal Desktop's local data on your own
computer: your conversations, messages, contact names, phone numbers and
attachments, and on macOS the database key from your keychain (only after you
allow it). It writes the export to a folder you choose on the same computer.

## What leaves your computer

Nothing from your Signal data. The tool has no server, no account, no
telemetry and no analytics. Its only network access is uv downloading a
Python runtime and the pinned signal-export package from the official Python
Package Index on first use. Those downloads carry no data about you or your
messages.

## When you use it with Claude

If you run the tool through Claude, Claude sees what the script prints
(chat names, counts and folder paths) in your conversation, like any other
command output. The skill instructs Claude not to open, read or quote message
content unless you ask for it. If you do ask Claude to analyse an export, that
content becomes part of your conversation and is handled under Anthropic's
privacy policy and your Claude settings, not by this tool.

## Your responsibility for exports

Exports are unencrypted copies of your private messages and of other
people's messages to you. You decide where they are stored and with whom they
are shared. Please respect the privacy of the people in your chats, who did not
agree to their messages being stored or processed elsewhere.

## Contact

Questions about this statement: [philip.mueller.bueckeburg@gmail.com](mailto:philip.mueller.bueckeburg@gmail.com), or open an issue at
https://github.com/phillippmueller/chat-export-for-signal/issues.

Last updated: 20 October 2026

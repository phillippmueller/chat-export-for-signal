# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-10-20

### Changed

- Renamed to **Chat Export for Signal (unofficial)**: plugin and marketplace
  name `chat-export-for-signal`, repository
  `phillippmueller/chat-export-for-signal`.
- When the skill's files aren't on the Signal computer (the Claude app),
  Claude now copies the two bundled scripts there, after asking, instead of
  cloning the repository. Scripts are always started with `bash`.
- The data step runs through the same pinned `uv tool run` as the export.

### Added

- Example requests in the skill and README; sections on what the plugin runs
  and accesses, support, and limits.
- `PRIVACY.md` and `SECURITY.md`.
- `tests/demo.sh`: try the tool on a fake Signal database with invented data.

## [0.2.0] - 2026-10-20

### Added

- Machine-readable data in every export: `messages.jsonl`, `chats.jsonl` and
  `people.jsonl` with stable IDs (Signal service IDs for people, local and
  cross-device keys for messages), UTC timestamps, replies and reactions
  linked by ID, and attachment paths; plus `manifest.json` with versions,
  filters, counts and SHA-256 checksums. Schema documented in
  `reference/data-format.md`.
- Attachments are read from Signal's separate attachment table (newer Signal
  versions), so they appear in the data files too.
- `--no-data` option to skip the data files.
- The skill now also works when its files aren't on the Signal computer (for
  example from the Claude app): Claude clones this repository there first,
  after asking.
- Release workflow: a version tag publishes the skill as a ZIP for upload
  under Customize -> Skills. README covers installing from the Claude app.
- End-to-end test against a fake, encrypted Signal database, and unit tests
  for the converter; both run in CI.

## [0.1.0] - 2026-10-20

### Added

- `signal-export.sh` with `doctor`, `list`, `export`, `update`, `version` and
  `help` commands, running signal-export 3.9.3 through uv.
- Safety checks: refuses to run while Signal is open, refuses to overwrite an
  existing folder, refuses to export into the repository.
- `signal-export` Claude skill and plugin/marketplace manifests.
- Tests with a fake uv, and CI on macOS and Linux.

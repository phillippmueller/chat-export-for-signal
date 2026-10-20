# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

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

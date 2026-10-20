# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-20

### Added

- `signal-export.sh` with `doctor`, `list`, `export`, `update`, `version` and
  `help` commands, running signal-export 3.9.3 through uv.
- Safety checks: refuses to run while Signal is open, refuses to overwrite an
  existing folder, refuses to export into the repository.
- `signal-export` Claude skill and plugin/marketplace manifests.
- Tests with a fake uv, and CI on macOS and Linux.

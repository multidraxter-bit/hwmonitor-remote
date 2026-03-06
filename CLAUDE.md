# CLAUDE.md — hwremote-monitor

Project-level guidance for Claude Code when working in this repository.

## CI/CD & Release

When fixing CI/CD failures, check for stale lint configs, unused imports, missing dependencies, and version ordering issues before attempting the fix — don't just fix the immediate error.

## Code Quality

After making multi-file changes, verify import paths and module exports are consistent before committing. Run tests and lint checks proactively.

## Debugging Guidelines

When debugging Docker or credential/config issues, enumerate all attempted approaches and track what was tried. Avoid re-trying the same fix. Prefer creating minimal workarounds (e.g., no-op helpers) over repeated restarts.

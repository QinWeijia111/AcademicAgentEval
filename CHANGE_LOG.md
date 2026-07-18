# Change Log

All notable changes to this project are documented here.

This file follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [Unreleased]

### Added

- Sanitized `AgentQuery` boundary that prevents benchmark labels from reaching agents.
- Strict JSON configuration, CLI validation commands, dataset adapters, local ranking helpers, and baseline output parser contracts.
- Smoke configuration templates and evaluation/baseline integration documentation.
- Project-level Claude Code documentation-maintenance policy.
- Competition brief (`赛题描述.md`) under version control.

### Changed

- Expanded experiment documentation to distinguish offline parser contracts from unverified live PaSa, SPAR, and Asta runs.
- Added a documentation handoff policy: validate code first, update documentation and this log second, and commit only on explicit user request.

### Security

- Reject inline credentials in external-worker configuration and recursively strip label fields from baseline parser metadata.

## [0.1.0] - 2026-07-16

### Added

- Initial evaluation core with canonical schemas, deterministic F1 matching, usage tracking, runner artifacts, HTML reporting, and a deterministic demo.

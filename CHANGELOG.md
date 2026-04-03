# Changelog

All notable changes to Darts Kiosk are documented here.

The project follows semantic versioning for product releases.

## [4.1.0] - 2026-04-03

### Added
- One-click Windows installer via `release/windows/install.bat`.
- Direct update install path in **System → Updates** for Windows release packages.
- Public pairing-status endpoint so the kiosk can show the pairing code only when it is actually needed.
- Proper release documentation and product-facing release notes for the 4.1.0 line.

### Changed
- Admin UI reduced operator noise: slimmer navigation, less meta text, cleaner responsive shells, and more stable text wrapping.
- Dashboard keeps boards visible in the main control area after unlock so credits can be topped up immediately.
- System/Updates page now promotes the real primary action: install available updates directly instead of only listing them.
- Windows startup path now bootstraps backend + agent more reliably and prepares frontend build + runtime folders during setup.
- Built Windows bundles now ship with a correct default `GITHUB_REPO=orri58/darts-kiosk` and `AGENT_PORT=8003` example config.
- Agent defaults and docs now align on port `8003`.

### Fixed
- `BOARD-2` is no longer recreated automatically on startup.
- Agent health monitoring now normalizes missing URL schemes and checks the real agent status endpoint.
- GitHub update checks no longer break on a trailing slash in `GITHUB_REPO`.
- Kiosk lockscreen no longer permanently shows admin/footer noise and hides the pairing code unless pairing is required.
- Windows agent version/runtime messaging no longer depends on stale hardcoded values.

### Validation
- Focused backend validation suite passed.
- Frontend production build passed.
- Release artifacts for Windows, Linux, and source were built successfully.

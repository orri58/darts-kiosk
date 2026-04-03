# Changelog

All notable changes to Darts Kiosk are documented here.

The project follows semantic versioning for product releases.

## [4.2.2] - 2026-04-04

### Fixed
- Local leaderboard/statistics no longer depend on match sharing being enabled.
- Completed local matches now persist `MatchResult` records even when a session still has remaining credits/time.
- This makes local player names and rankings much more consistent across standalone devices.

### Validation
- Backend compile check passed.
- Focused backend validation suite passed (37 tests).

## [4.2.1] - 2026-04-04

### Fixed
- Direct update install now prefers the real public release asset download URL instead of accidentally routing public installs through the GitHub API asset URL.
- Added lightweight archive validation so broken HTML/JSON error responses are rejected before they are treated as update packages.
- System update UI now sends the correct preferred asset URL for Windows direct installs.

### Validation
- Backend compile check passed.
- Frontend production build passed.
- Release artifacts rebuilt successfully.

## [4.2.0] - 2026-04-03

### Added
- Separate settings buckets for `kiosk_theme`, `admin_theme`, and `kiosk_layout`.
- Shared kiosk branding header so the configured logo finally renders on major kiosk surfaces.
- Session charge booking model for proper unlock/top-up accounting history.

### Changed
- Dashboard was tightened to be more operator-first, with smaller summary cards and a less dominant page header.
- Top-up flow now displays the amount that will be booked.
- Admin theme selection is now independent from kiosk theme selection.
- Kiosk layout gained practical controls for logo visibility/size/alignment and pairing-code position.

### Fixed
- Additional credits / session extensions now count toward revenue/reporting instead of disappearing from bookkeeping.
- Kiosk logo uploads are now actually visible on the kiosk UI.
- Admin and kiosk surfaces no longer have to share the same palette choice.

### Validation
- Backend/agent compile check passed.
- Focused backend validation suite passed (37 tests).
- Frontend production build passed.

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

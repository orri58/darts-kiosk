# Changelog

All notable changes to Darts Kiosk are documented here.

The project follows semantic versioning for product releases.

## [4.4.3] - 2026-04-04

### Fixed
- Fixed kiosk browser supervision so the launcher restarts the dedicated kiosk Chrome process instead of considering any random `chrome.exe` good enough.
- Improved kiosk window detection to identify the kiosk process via command line markers and surface PID/visibility/reason diagnostics.
- Added explicit elevated/admin visibility to agent status so permission-related device-ops failures are easier to understand.
- Improved the Device Ops “Kiosk window” panel so it no longer appears blank when diagnostics exist.
- Relaxed the admin dashboard layout so the board-control area behaves more responsively on medium widths.

### Validation
- Agent/admin router Python compile sanity passed.
- Existing backend regression suites passed (`12 passed`).
- Frontend production build passed.

## [4.4.2] - 2026-04-04

### Fixed
- Fixed first-run setup completion crashing with `TypeError: is_setup_complete() takes 0 positional arguments but 1 was given`.
- Repaired the realtime websocket contract across backend and frontend:
  - backend now accepts both global and board-scoped websocket endpoints
  - websocket manager now supports both legacy and current broadcast call signatures
  - websocket payloads now expose both `event` and `type` for compatibility
  - frontend websocket hook now uses the correct path and forwards `(eventType, data)` correctly to consumers
- Removed the lingering reconnect-hook warning in `useBoardWS`.

### Validation
- Backup service export regression suite passed.
- Setup + websocket contract regression suite passed.
- Scheduler terminal cleanup regression suite passed.
- Session consistency detection/repair regression suite passed.
- Frontend production build passed.

## [4.4.1] - 2026-04-04

### Fixed
- Restored missing `start_backup_service` / `stop_backup_service` exports in `backend/services/backup_service.py`, which had caused the backend to crash immediately during Windows startup.
- Restored backup-service helper methods required by the backups API contract (`get_backup_path`, `delete_backup`, `get_backup_stats`).
- Added regression coverage so the backup service startup/router contract cannot silently break release builds again.

### Validation
- Backup service export regression suite passed.
- Scheduler terminal cleanup regression suite passed.
- Session consistency detection/repair regression suite passed.

## [4.4.0] - 2026-04-04

### Added
- Runtime session/board consistency diagnostics for detecting stale lifecycle mismatches after restarts, timeouts, or partial observer cleanup.
- Admin API + Health UI surface for reviewing lifecycle findings per board and triggering a one-click safe repair.
- Safe-repair path for common contradictions such as orphan active board states, duplicate active sessions, and terminal sessions that never cleaned up fully.

### Changed
- Recovery diagnostics are now more operationally visible instead of being spread across logs, health signals, and implicit runtime behavior.
- Shared terminal cleanup is reused when a consistency repair closes a stale terminal lifecycle state.

### Validation
- Scheduler terminal cleanup regression suite passed.
- Session consistency detection/repair regression suite passed.
- Frontend production build passed.

## [4.3.0] - 2026-04-04

### Changed
- Realtime runtime now has a stronger foundation: websocket fanout is more resilient, websocket clients support reconnect/backoff/heartbeat behavior, and the server understands ping/pong keepalive messages.
- SQLite backups now use native SQLite snapshotting and integrity checks instead of raw live-file copying.
- Restore flow now validates backup contents before replacing the live database.

### Stability
- Better protection against one slow/dead websocket client degrading all other realtime listeners.
- Safer backup artifacts for support, recovery, and update preparation.

### Validation
- Backend compile check passed.
- Focused backend validation suite passed.
- Frontend production build passed.

## [4.2.3] - 2026-04-04

### Fixed
- First-run setup can no longer be completed again once the system is already initialized.
- Update ZIP staging now rejects path traversal / unsafe archive members before extraction.
- Rebind-device licensing endpoint now requires superadmin instead of any admin.
- Admin CSV export no longer depends on JWT query parameters.

### Security
- Removed hardcoded static secret fallbacks for JWT and agent auth; missing secrets now use ephemeral runtime secrets instead of predictable defaults.

### Validation
- Backend compile check passed.
- Focused backend validation suite passed (39 tests).
- Frontend production build passed.

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

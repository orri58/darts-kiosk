## [4.5.5] - 2026-05-31

### Fixed
- Hardened active-session lookup so the backend no longer crashes with `500` when corrupted state leaves more than one active session on the same board.
- Added automatic duplicate-session self-healing: the newest active session is kept, older duplicates are cancelled with a consistency repair reason.
- Updated scheduler and remote-action session flows to use the hardened lookup path so idle-timeout, force-lock, and board session reads stay usable under bad data instead of throwing `MultipleResultsFound`.

### Validation
- Isolated backend regression suites passed:
  - `backend/tests/test_v440_session_consistency.py` → `6 passed`
  - `backend/tests/test_v430_scheduler_terminal_cleanup.py` → `4 passed`
  - `backend/tests/test_manual_unlock_pricing.py` → `2 passed`
- Release artifacts rebuilt for `v4.5.5`.

## [4.5.4] - 2026-05-18

### Fixed
- Fixed the mobile admin/operator shell so the sidebar menu no longer stays visually stuck open on small screens because the base shell CSS overrode the Tailwind translate state.
- Improved mobile shell behavior with cleaner slide-in/out handling, overlay dismissal, body-scroll locking while the menu is open, route-change auto-close, and desktop resize reset.
- Tightened the mobile shell layout so the sidebar sits below the sticky mobile header instead of awkwardly covering the whole viewport chrome.

### Validation
- Frontend production build passed.
- Shell/admin JSX parse sanity passed.
- Release artifacts rebuilt for `v4.5.4`.

## [4.5.3] - 2026-05-18

### Fixed
- Re-rolled the admin-panel free-unlock fix as a fresh updater version so Windows systems can pull the complete backend + frontend change set again via the built-in update flow.
- Keeps the same free/manual unlock behavior from `v4.5.2`, but under a newer version number to force a clean updater pass on machines that were left in a mixed UI/backend state.

### Validation
- Release artifacts rebuilt for `v4.5.3`.
- GitHub latest release updated so automatic update discovery resolves to `v4.5.3`.

## [4.5.2] - 2026-05-18

### Fixed
- Added the missing admin-panel option to unlock a board for free (`Kostenlos freischalten`) instead of only allowing credit-based unlocks.
- Wired the free unlock path through the backend via `manual_unlock`, so free/manual sessions no longer require credits and do not trigger later credit deductions.
- Preserved manual-unlock detection on active sessions by deriving the flag from the unlock charge note, keeping older sentinel-based pricing logic compatible without a schema migration.

### Validation
- Manual-unlock backend regression suite passed (`2 passed`): `backend/tests/test_manual_unlock_pricing.py`.
- Admin dashboard JSX parse sanity passed.
- Release artifacts rebuilt for `v4.5.2`.

## [4.5.1] - 2026-05-18

### Changed
- Published a clean canonical release line so automated update checks can resolve a single latest version with the correct Windows ZIP asset.
- Aligned the broader product/control-plane/UI/field-readiness cut under a higher semantic version than the earlier partial releases to avoid updater confusion.

### Validation
- Frontend production build passed.
- Release artifacts rebuilt for `v4.5.1`.
- GitHub release published with Windows ZIP, Linux TAR.GZ, and Source ZIP assets.

## [4.5.0] - 2026-05-18

### Changed
- Consolidated a large local working set into a real release instead of leaving major central, operator, portal, and field-readiness work unreleased.
- Refactored the central control plane heavily: remote actions, trust readbacks/enrollment, config profiles/effective config, licensing token flows, admin CRUD, device detail/readback, websocket status/handshake, and related telemetry/helper seams are now split out of the old monolith into dedicated route/service modules.
- Unified the product shell, page/data system, detail/dashboard system, fleet/device surfaces, and commercial/license drill-in flows across admin, operator, and portal so the product behaves much more like one coherent family.
- Added board-PC preflight/postflight evidence capture, certification exports, RC evidence artifacts, and support-bundle inclusion to make real Windows/board-PC validation auditable and repeatable.
- Added the new admin unlock option to free a board without credits/time and keep it manually unlocked until staff lock it again.

### Validation
- Focused central security, trust, runtime maintenance, field evidence, and manual-unlock backend suites passed locally.
- Focused operator frontend test passed.
- Frontend production build passed.
- Release artifacts rebuilt for `v4.5.0`.

# Changelog

All notable changes to Darts Kiosk are documented here.

The project follows semantic versioning for product releases.

## [4.4.21] - 2026-05-18

### Added
- Added a modular central-server route/service layout for config profiles, effective device config, device detail reads, device remote actions, trust enrollment/detail shaping, licensing token flows, websocket device status, and shared audit/auth helpers so the broader central control-plane work now ships as a coherent codebase instead of lingering only in the local tree.
- Added shared product-surface shell primitives (`ProductShell`, detail/data display helpers, and surface system components) plus an operator commercial-flow helper/test so operator and portal pages can reuse one cleaner interaction model.
- Added board-PC certification and RC field-evidence runbooks plus Windows preflight/postflight capture scripts so runtime rehearsal evidence can be collected more consistently on real machines.

### Improved
- Reworked `central_server/server.py` around the extracted central modules, drastically reducing the monolith and aligning the shipped server with the pending broader central work that was previously not part of `4.4.20`.
- Refreshed operator and portal surfaces — including dashboards, layouts, customers, locations, devices, users, licenses, audit, reports, and device/license detail flows — onto the newer product-shell design language for a more consistent commercial/operator experience.
- Tightened runtime maintenance and field-handoff documentation, readiness notes, and closed-loop support artifacts so the repo better distinguishes focused green lanes from historical/non-authoritative test noise.

### Fixed
- Fixed device pending remote-action delivery to evaluate TTL against the injected release/test clock instead of ambient wall time, preventing false expiry during deterministic validation.
- Restored manual-unlock session-pricing compatibility for the legacy manual-unlock regression tests by preserving the older sentinel/decision aliases alongside the current pricing model.
- Updated the repo-level release docs/version pointers so the shipped release line matches the actual cut instead of the earlier partial 4.4.20 note.

### Validation
- Focused central/runtime regression suite passed (`166 passed`): device-detail/config-profile/effective-config/licensing-token/remote-action/trust/ws-status service+router slices, `backend/tests/test_central_security_hardening.py`, `tests/test_device_trust.py`, `tests/test_runtime_field_evidence.py`, and `tests/test_runtime_maintenance_closed_loop.py`.
- Legacy manual-unlock compatibility suite passed (`2 passed`): `backend/tests/test_manual_unlock_pricing.py`.
- Python compile sanity passed for `central_server` and `release/runtime_windows`.
- Frontend production build passed (`cd frontend && npm run build`).
- Full historical `pytest -q` was re-checked and remains broadly red outside the focused release lanes; it is not claimed green for this release.

## [4.4.19] - 2026-04-27

### Added
- Added token-state enrichment and a dedicated token follow-up portfolio queue so operator surfaces can distinguish ready-to-send, missing, expired, and revoked activation paths instead of treating all activation gaps the same.
- Added direct device-detail routing from both operator and portal license/device flows, including license-to-device and device-to-license continuity for bound commercial troubleshooting.

### Improved
- Expanded the operator licenses command surface with token readiness KPIs, token badges, inline queue actions, and clearer activation feedback so commercial rollout work can be driven from list level with less context switching.
- Tightened license portfolio summarization coherence by reusing a single evaluation timestamp per request and surfacing richer token summary metadata for downstream UI decisions.
- Improved the shared device detail surface so operator routes no longer fall back to portal-only navigation and bound-license drill-ins stay in the active surface.

### Validation
- Focused backend regression suite passed (`11 passed`): `tests/test_license_portfolio_summary.py`, `tests/test_remote_action_operator_wave.py`.
- Python compile sanity passed for `central_server/server.py`.
- Frontend production build passed (`cd frontend && npm run build`).

## [4.4.18] - 2026-04-27

### Added
- Added a commercial readiness model for licenses plus a portfolio summary API so operator and portal surfaces can rank renewal pressure, activation gaps, capacity strain, and blocked device posture from one backend read model.
- Added targeted regression coverage for license portfolio summarization and remote-action problem-scope prioritization.

### Improved
- Expanded the operator dashboard, operator licenses view, portal dashboard, portal layout, and license detail flows so license readiness and drill-ins are consistent across operator and portal surfaces.
- Improved operator audit and remote-action triage flows with richer drill-down, scoped filtering, saved views, hotspot/problem-scope surfacing, and clearer escalation ordering.
- Tightened backend prioritization so remote-action hotspot ranking prefers pending-review pressure ahead of pure delivery volume, matching the intended operator triage model.

### Fixed
- Fixed an operator licenses runtime coherence bug where the route-surface prefix was read before initialization, which would have broken the page at runtime despite the feature work being present.

### Validation
- Focused backend regression suite passed (`5 passed`): `tests/test_license_portfolio_summary.py`, `tests/test_remote_action_operator_wave.py`.
- Python compile sanity passed for `central_server/server.py`.
- Frontend production build passed (`cd frontend && npm run build`).

## [4.4.17] - 2026-04-27

### Added
- Added a dedicated central remote-action policy module so the shippable action catalog, approval rules, expiry handling, and blocked high-risk actions are defined in one place instead of drifting between endpoints and UI assumptions.
- Added approval/review maturity to central remote actions with queue/review/outcome state fields, richer audit metadata, and focused regression coverage for the policy envelope.
- Added a central advisory device posture rollup that combines trust, credential, lease, license, and replacement diagnostics into stable operator-facing findings.
- Added an Operator Remote Actions page and routing so the central operator surface now has a dedicated workflow for queue, history, filters, and review handling.

### Improved
- Hardened central remote-action handling so only the current supported action set can be requested or delivered, expiry is enforced consistently, and legacy/stale action types are rejected instead of quietly leaking through.
- Improved operator authentication/session handling and scope-aware routing so the dedicated operator surface behaves coherently across login restore, `/api/auth/*` usage, and page-level navigation.
- Promoted advisory trust/commercial posture into the operator dashboard, device, license, and layout surfaces so operators can see commercial/trust risk in context without implying local enforcement.
- Aligned the operator Remote Actions filter UI with the tightened central policy and kept blocked board/session actions visible for audit/history triage without implying that central may still execute them.

### Validation
- Focused backend central/operator regression suite passed (`82 passed`).
- Python compile sanity passed for `central_server` and `backend`.
- Frontend production build passed.
- Release artifacts rebuilt for `v4.4.17`.

## [4.4.16] - 2026-04-25

### Improved
- Delivered a broader premium UI polish pass across both kiosk and admin so the product feels more cohesive, modern, and professionally shipped instead of partially refreshed.
- Upgraded shared frontend design primitives (`index.css`, buttons, inputs, tabs) with stronger dark-surface depth, more consistent radii, improved focus states, better shadows, and more polished control behavior.
- Refined the admin shell and major admin surfaces so Settings, Users, Licensing, Logs, Leaderboard, and Setup Wizard now share the same page language, spacing rhythm, card hierarchy, status treatment, and calmer operator-facing structure.
- Upgraded key kiosk surfaces — Locked, Setup, In-Game, Match Result, Credit Blocked, and Error — with clearer hierarchy, stronger hero/status panels, better cards, improved guidance text, and a more premium customer-facing flow.
- Improved operator clarity in high-friction states such as insufficient credits, match completion, recovery/error handling, role/status visibility, and first-run/security framing.

### Validation
- Frontend production build passed cleanly.
- Release artifacts rebuilt for `v4.4.16`.

## [4.4.15] - 2026-04-22

### Improved
- Continued breaking down the oversized Admin settings page by extracting dedicated section components for Language, Match Sharing, PWA/App, and Kiosk Control.
- Reduced `Settings.js` further so more of the admin surface now follows a reusable section-based structure instead of a single giant render file.

### Validation
- Focused settings contract regression suite passed (`4 passed`).
- Frontend production build passed.
- Release artifacts rebuilt for `v4.4.15`.

## [4.4.14] - 2026-04-21

### Improved
- Began decomposing the oversized Admin settings page into dedicated section components instead of continuing to grow a single monolithic `Settings.js` file.
- Extracted the Branding, Pricing, and Customization Profiles areas into reusable Admin settings modules, reducing central page complexity and making future settings work safer.

### Validation
- Focused settings contract regression suite passed (`4 passed`).
- Backend compile sanity passed.
- Frontend production build passed.
- Release artifacts rebuilt for `v4.4.14`.

## [4.4.13] - 2026-04-21

### Added
- Added professional customization profile tools in Admin settings for exporting, importing, and resetting the kiosk/admin customization state as a JSON profile.
- Added backend customization profile endpoints on top of the normalized settings contract for safe profile round-trips.

### Improved
- Normalized customization bundle import now sanitizes and restores the full contract-managed kiosk/admin settings family in one step.
- Admin settings now expose a practical operator workflow for backup/rollout/reset without touching raw storage manually.

### Validation
- Focused settings contract regression suite passed (`4 passed`).
- Backend compile sanity passed.
- Frontend production build passed.
- Release artifacts rebuilt for `v4.4.13`.

## [4.4.12] - 2026-04-21

### Added
- Added a normalized `customization-bundle` settings read model that returns merged/defaulted kiosk/admin customization data in one consistent payload.
- Added a dedicated backend settings-contract layer for branding, themes, kiosk layout, kiosk texts, PWA config, lock-screen QR, overlay, post-match delay, language, match sharing, palettes, and pricing.

### Improved
- Settings reads now return fully normalized objects with nested defaults instead of partial/raw JSON blobs for the contract-managed settings family.
- Contract-managed writes now sanitize and normalize stored values before persistence, reducing config drift and invalid enum/state combinations.
- Frontend `SettingsContext` now consumes the normalized bundle and exposes first-class update actions for kiosk texts, PWA config, and lock-screen QR.
- Config apply now normalizes contract-managed settings before writing them to local storage, improving upgrade/import consistency.

### Validation
- Added focused regression tests for the settings contract layer (`3 passed`).
- Backend compile sanity passed.
- Frontend production build passed.
- Release artifacts rebuilt for `v4.4.12`.

## [4.4.11] - 2026-04-21

### Added
- Added configurable lock-screen info cards for Credits, Matchstart, and Freischaltung so each card can be renamed, have custom value/hint text, or be disabled entirely from Admin settings.
- Added more kiosk logo sizing options (`xl`, `2xl`) plus lock-screen layout controls for centered content and a large hero-logo mode in the main screen area.

### Improved
- Lock-screen rendering now derives default card values from pricing settings but respects explicit custom text overrides, including intentionally blank text when desired.
- The lock screen can now present the venue logo either in the header or prominently in the main content area for more centered/branded layouts.

### Validation
- Backend compile sanity passed.
- Frontend production build passed.
- Changes pushed to `dev` and release artifacts rebuilt for `v4.4.11`.

## [4.4.10] - 2026-04-15

### Fixed
- Fixed per-player credit reconciliation when a match first starts through an early single-player fallback and the authoritative player count is corrected later.
- Late reconciliation now charges or blocks only for the missing delta instead of incorrectly demanding the full player-count total again.
- Clarified the pending-credit overlay wording so it emphasizes the missing additional credits instead of reading like the full requirement must be paid again.

### Validation
- Reproduced the issue against a real support bundle from field testing.
- Focused pricing regression suite passed (`15 passed`).
- Release artifacts rebuilt for `v4.4.10`.

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


## [4.4.20] - 2026-05-18

### Added
- Added an explicit admin unlock option to free a board without credits or time so it can stay manually unlocked until staff lock it again.

### Changed
- Manual unlock sessions are now marked explicitly in backend session data and kiosk UI so operators and players can see that the board is running in free/manual mode.
- Kiosk session handling now bypasses normal credit/time consumption for manual unlock sessions while keeping existing manual re-lock behavior.

### Validation
- Focused backend/manual-unlock + runtime/field-readiness + central security suites passed locally.
- Frontend production build passed.
- Release artifacts rebuilt for `v4.4.20`.


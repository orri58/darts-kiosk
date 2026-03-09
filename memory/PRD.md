# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Must behave like a real arcade machine on Windows kiosk PCs.

## Core Architecture
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Frontend:** React + Tailwind CSS + Shadcn/UI
- **Deployment:** Windows .bat scripts (non-Docker) for kiosk PCs
- **Integration:** Playwright for Autodarts browser automation
- **Update System:** GitHub Releases → Admin Panel → External Updater (updater.py)

## Observer State Machine (Three-Tier + Debounced)
```
States: closed, idle, in_game, round_transition, finished, unknown, error

DOM Detection (Three-Tier):
  Tier 1: Active match markers (scoreboard, dart-input) → IN_GAME
  Tier 2: Strong end buttons (Rematch/Share/NewGame text) → FINISHED
  Tier 3: Generic result CSS classes only → ROUND_TRANSITION
  Tier 4: No game markers → IDLE

Observer Loop:
  raw IN_GAME          → clear exit counter
  raw ROUND_TRANSITION → RESET exit counter (turn change)
  raw FINISHED         → increment exit counter
  raw IDLE             → increment exit counter
  exit_polls >= 3      → CONFIRMED exit → callback
```

## Update System Architecture
```
Admin Panel → Backend (prepare) → updater.py (execute)

Flow:
1. Admin: "Check for Updates" → GitHub API
2. Admin: "Download" → Backend downloads .zip to data/downloads/
3. Admin: "Install" → Backend: backup → extract → validate → manifest → launch updater.py
4. updater.py: stop → replace files → start → health check
5. On failure: automatic rollback from backup

Protected paths (NEVER overwritten):
- data/, logs/, chrome_profile/, .env files

Release asset naming: darts-kiosk-v{VERSION}-windows.zip
Version source: /VERSION file (single source of truth)
```

## All Implemented Features
- v1.0-1.5: Core system (Kiosk, Admin, Auth, Boards, Pricing, Sessions, Sound, i18n, White-Label)
- v1.6.0: Arcade Machine Runtime (overlay, window management)
- v1.6.1-1.6.3: Chrome profile persistence, extension support, automation banner removal
- v1.6.4: Observer Debounce Logic (3 polls × 2s = 6s confirmation)
- v1.6.5: Three-Tier State Detection & ROUND_TRANSITION
  - ROUND_TRANSITION prevents turn changes from locking the board
  - Strong match-end markers (Rematch/Share/NewGame buttons) required for FINISHED
  - 15 unit tests for observer logic
- v1.7.0: GitHub-based Update System
  - VERSION file as single source of truth
  - /api/system/version (public) and /api/health endpoints
  - Full app backup (backend + frontend + scripts + VERSION)
  - Update install pipeline: download → backup → extract → validate → manifest → updater.py
  - Standalone updater.py (stop → replace → restart → health check → auto-rollback)
  - Rollback from any app backup
  - Admin UI: Install button, Rollback button, Update Result banner, Progress display
  - Enhanced update history with event tracking
  - .gitignore for proper GitHub repo structure
  - RELEASE_GUIDE.md documentation
  - update.bat for manual Windows update
  - All 18 tests passed (13 backend API + 5 frontend UI)
- v1.7.1: GitHub Deployment Setup
  - GitHub Actions workflow (.github/workflows/build-release.yml)
    - Triggers: push tag v* OR manual workflow_dispatch
    - Builds: Windows .zip, Linux .tar.gz, Source .zip
    - Auto-creates GitHub Release with all 3 assets
    - Uses: actions/checkout@v4, actions/setup-node@v4, softprops/action-gh-release@v2
  - .env.example templates for backend and frontend
  - GITHUB_SETUP.md — complete manual checklist (repo setup, Actions, tokens, go-live)
  - Validated: version comparison, platform detection, asset naming, protected paths

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests (validate selectors against live site)

### P2
- [ ] Chromium Extension as alternative to Playwright observer
- [ ] PWA Install Prompt for public leaderboard page

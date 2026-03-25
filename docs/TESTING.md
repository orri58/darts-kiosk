# Testing Guide

## Test Categories

### 1. Baseline Recovery Tests
Verifies the 6 core flows of the frozen local core.

```bash
python -m pytest backend/tests/test_v400_recovery_baseline.py -v
```

Covers: auth, board unlock/lock, session flow, settings, revenue, observer status.

### 2. Regression E2E Tests
Broader regression suite covering data corruption handling and central server endpoints.

```bash
python -m pytest backend/tests/test_regression_e2e.py -v
```

**Note:** Some tests in this suite reference central server endpoints that are currently disabled. These tests will be skipped or need updating.

### 3. Historical Test Files
The `backend/tests/` directory contains 80+ test files from previous development iterations. These are preserved for reference but many are outdated. The authoritative tests for the current state are:

- `test_v400_recovery_baseline.py` — current baseline
- `test_regression_e2e.py` — regression suite (partially applicable)

---

## Running Tests

### Prerequisites
```bash
pip install pytest httpx
```

### Run All Current Tests
```bash
cd /app
python -m pytest backend/tests/test_v400_recovery_baseline.py -v --tb=short
```

### Run a Specific Test
```bash
python -m pytest backend/tests/test_v400_recovery_baseline.py::TestBoardControl -v
```

---

## What Is Mocked vs Real

| Component | In Tests | Notes |
|-----------|----------|-------|
| Backend API | **Real** | Tests use `httpx.AsyncClient` with the real FastAPI app |
| SQLite Database | **Real** | Tests use the actual database |
| Autodarts | **Not tested** | Requires Chrome, not available in CI. Verified manually on Windows. |
| Central Server | **Real** (when active) | Tests use `httpx` against port 8002 |
| Frontend | **Playwright** | Browser automation for UI verification |
| WebSocket | **Not tested** | Tested manually via browser |

---

## Manual Verification Checklist (Windows Device)

Before any release, verify on a real Windows machine:

### Board Control
- [ ] Start `start.bat` — backend starts without errors
- [ ] Open `http://localhost:8001` in browser
- [ ] Login as admin
- [ ] Click "Freischalten" on a board
- [ ] Verify kiosk screen shows "Entsperrt" on the kiosk display
- [ ] Click "Sperren" — board returns to locked
- [ ] Verify kiosk screen shows "Gesperrt"

### Autodarts
- [ ] Unlock a board
- [ ] Click "Autodarts Starten" on kiosk
- [ ] Verify Chrome opens and navigates to play.autodarts.io
- [ ] Verify observer detects game start/end

### Settings
- [ ] Change cafe name in admin settings
- [ ] Verify kiosk display updates with new name
- [ ] Change pricing mode
- [ ] Unlock board — verify new pricing is applied

### Revenue
- [ ] Create and finish a session (unlock → play → lock)
- [ ] Check revenue page — verify amount matches pricing config
- [ ] Export CSV report

### Session Flow
- [ ] Unlock with "Pro Spiel" pricing, 3 games, 2 players
- [ ] Verify session shows correct game count and total price
- [ ] End session — verify it shows as finished

---

## Release Acceptance Checklist

- [ ] All `test_v400_recovery_baseline.py` tests pass
- [ ] Backend starts without import errors
- [ ] Frontend compiles without errors
- [ ] Admin login works
- [ ] Board unlock/lock works
- [ ] Kiosk displays correct state
- [ ] Settings save and apply
- [ ] Revenue endpoint returns correct numbers
- [ ] Windows build runs from `start.bat`
- [ ] No 500 errors in backend logs after 5 minutes of operation

# Developing Darts Kiosk

This guide walks a developer through setting up the repository, running the code locally, and contributing changes.

## Prerequisites
- Python 3.11+ (for the backend)
- Node.js 18+ and npm (for the frontend)
- Git
- On Windows: Visual C++ Redistributable x64 (required by some Python wheels)

## Backend setup
```bash
# Clone the repo (if you haven't already)
git clone <repo-url>
cd darts-kiosk

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r backend/requirements.txt
```

### Run the backend
```bash
uvicorn backend.server:app --reload --port 8001
```
The API is now reachable at `http://localhost:8001/api`.

## Frontend setup
```bash
cd frontend
npm ci
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```
The admin UI is available at `http://localhost:8001/admin` and the kiosk UI at `http://localhost:8001/kiosk/BOARD-1`.

## Testing
Run the authoritative test suite (the subset that validates the protected local core):
```bash
source .venv/bin/activate
pytest backend/tests/test_phase34_autodarts_triggers.py \
       backend/tests/test_phase34_credits_pricing.py \
       backend/tests/test_phase56_stability_installation.py \
       backend/tests/test_phase789_local_core_validation.py -q
```
All tests must pass before committing.

## Contributing
- Fork the repository and create a feature branch.
- Follow the **single logical change per commit** rule.
- Update relevant docs (`DEVELOPING.md`, `OPERATIONS.md`, or `RELEASING.md`) when you alter behaviour.
- Run the full test suite locally (`pytest -q`).
- Open a Pull Request with a clear description of the change.

For more detailed contribution policies see `CONTRIBUTING.md`.
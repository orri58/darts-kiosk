# Autodarts Capture Harness

Local diagnostic tool for collecting real Autodarts runtime data on a test/board device.

## Why this exists

Some future features should not be built from guesswork alone, especially:

- tournament / lobby return flow after match end
- tournament billing vs per-match billing
- reliable match-end detection
- player-name extraction
- lobby / tournament / match context transitions
- bull-off vs non-bull-off lifecycle differences

This harness captures the signals we actually need so later implementation can be based on real traces.

## What it records

The script writes a capture session folder under:

- `data/autodarts_capture/<session>/`

Inside that folder:

- `meta.json` — run configuration
- `capture.jsonl` — newline-delimited event stream
- `summary.json` — compact overview of the session

### Event types currently captured

- `page_state`
- `navigation`
- `browser_event`
- `console`
- `http_request`
- `http_response`
- `websocket_open`
- `websocket_close`
- `websocket_frame`

### Useful extracted fields

Depending on the payload, the harness will try to extract:

- `match_id`
- `lobby_id`
- `tournament_id`
- `players`
- `variant`
- `winner`
- `state`
- `finished`
- `gameFinished`
- channel / topic names such as:
  - `autodarts.matches...`
  - `autodarts.lobbies...`
  - `autodarts.tournaments...`
  - `autodarts.boards...`

## Recommended usage on a board/test PC

### Windows quick path

After the normal board-PC install, run:

```bat
capture_autodarts.bat
```

This uses:

- `BOARD_ID` from `backend\.env`
- `AUTODARTS_URL` from `backend\.env`
- profile directory `data\chrome_profile\<BOARD_ID>`

### Optional arguments

Examples:

```bat
capture_autodarts.bat --duration-seconds 900
capture_autodarts.bat --capture-api-bodies
capture_autodarts.bat --headless --duration-seconds 300
```

### Linux / direct Python usage

```bash
source .venv/bin/activate
python scripts/autodarts_capture.py --duration-seconds 600
```

## Practical test plan

Run the harness and then deliberately play through:

1. normal match start/end
2. bull-off start/end
3. 2-player and 4-player matches
4. lobby matches
5. tournament matches
6. match result screen transitions
7. return to lobby / bracket / next match
8. abort / back / reconnect scenarios

The goal is not just "does it work" but:

- what channels appear
- what IDs stay stable
- when `finished` / `gameFinished` appears
- when lobby/tournament context is visible
- what URL/state the browser lands on after a match

## Important operational notes

- Prefer running this on a **test device** or after stopping the kiosk/browser process first.
- If Chrome reports the profile is already in use, stop the kiosk or use a different profile dir.
- The capture stays **local**. It does not upload anywhere.
- By default, HTTP response bodies are **not** stored.
- If you add `--capture-api-bodies`, JSON response previews from `api.autodarts.io` are included and can contain more context.

## Suggested next implementation steps after collecting traces

1. build `return_to_last_context()` instead of always returning home
2. distinguish:
   - casual flow
   - lobby flow
   - tournament flow
3. only then design tournament billing on top of real lifecycle traces

## Packaging

The Windows release bundle includes:

- `capture_autodarts.bat`
- `scripts/autodarts_capture.py`

So the harness can be executed directly on a packaged board PC.

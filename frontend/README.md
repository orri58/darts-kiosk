# Darts Kiosk frontend

React/CRACO frontend for:
- admin UI
- kiosk UI
- overlay/public runtime surfaces

## Development

From `frontend/`:

```bash
npm ci
REACT_APP_BACKEND_URL=http://localhost:8001 npm start
```

Default local dev assumptions:
- backend runs on `http://localhost:8001`
- admin UI is served from `/admin`
- kiosk UI is served from `/kiosk/<BOARD_ID>`

## Production build

```bash
npm run build
```

The output is written to:

```text
frontend/build/
```

## Notes

- The release/build path uses **npm**, not a separate yarn-only workflow.
- Root product/runtime docs live mainly in the repo root `README.md` and `docs/`.
- If you change operator-facing UI behavior, update the relevant docs in the same branch.

# Darts Kiosk — Release Notes v4.4.18

## Commercial/operator coherence wave after 4.4.17

Darts Kiosk 4.4.18 is the cleanup-and-ship pass for the commercial/operator work that landed after 4.4.17.

This release is not about another feature detour.
It is about turning several related central/operator improvements into one coherent release candidate that operators can actually trust in the field.

## What changed

### 1. License readiness is now a first-class operator signal
Central now builds a commercial-readiness model per license and a portfolio summary across the scoped license set.
That model combines:
- computed license status
- renewal timing / grace pressure
- activation gaps
- capacity usage
- bound-device advisory posture

The result is a practical operator view of which licenses are healthy, which need watching, and which need action now.

### 2. Dashboard, portfolio, and detail views now tell the same story
The operator dashboard, operator licenses page, portal dashboard, portal layout, and license detail flows were aligned so they all point at the same backend read model.

That matters because commercial workflows get messy fast when summary cards, list views, and drill-ins each invent their own logic.
This release removes that drift.

### 3. Remote-action triage is more honest about urgency
Operator remote-action triage now exposes stronger hotspot/problem-scope summaries, better audit drill-down, and prioritization that favors pending-review pressure before pure delivery backlog.

That is the correct tradeoff.
A queue waiting on human approval is usually the real operator bottleneck; raw volume alone should not outrank it.

### 4. One runtime bug was caught before it escaped
During release stabilization, the operator licenses surface was found reading its route prefix before initialization.
That would have been an annoying “looks finished, breaks on load” bug.
It is fixed in this release candidate.

## Why this matters

4.4.18 is the version where the post-4.4.17 commercial/operator work stops feeling like a stack of related changes and starts behaving like a release.

The backend summaries, operator dashboards, portal views, audit drill-ins, and triage ordering now line up.
That does not make the product magically finished forever, but it does make this wave coherent enough to ship without squinting.

## Validation performed for this release

Executed successfully:

```bash
./.venv/bin/pytest tests/test_license_portfolio_summary.py tests/test_remote_action_operator_wave.py
python3 -m py_compile central_server/server.py
cd frontend && npm run build
```

Observed result:
- focused backend regressions passed (`5 passed`)
- Python compile sanity passed for `central_server/server.py`
- frontend production build passed cleanly

## Release readiness

Recommendation: release candidate is ready for the post-4.4.17 commercial/operator wave.

Known boundary:
- this stabilization pass did not rebuild packaged release artifacts or intentionally touch `data/db.sqlite`
- broader end-to-end/operator acceptance would still be useful if a staging environment is available

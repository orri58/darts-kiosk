# Documentation Navigator

This `docs/README.md` is the **front‑door** for all documentation in the repository. It points developers to the current, canonical entry points and clearly marks legacy material.

## Quick links (canonical)

- **DEVELOPING.md** – Set up a development environment, run tests, and build the project.
- **OPERATIONS.md** – Operator run‑book, update workflow, and troubleshooting guide.
- **BOARD_PC_CERTIFICATION_RUNBOOK.md** – Real Windows board-PC certification flow and artifact expectations.
- **RC_FIELD_EVIDENCE_CHECKLIST.md** – RC gate for field evidence; the short "don't fake it" list.
- **RELEASING.md** – Release process, versioning, and packaging.
- **EXTERNAL_DEVELOPER_HANDOFF.md** – High‑level product overview for external contributors.
- **ARCHITECTURE.md** – Deep dive into the runtime architecture.

## Legacy / historical docs

Older wave notes, audits, and dated planning docs in this `docs/` folder are **not** part of the current truth set, but they are retained for reference.

Examples:
- `DEVICE_RUNTIME_PACKAGE_WAVE*.md`
- dated files such as `PROJECT_*_2026-05-06.md` and audit/checkpoint snapshots
- older analysis/readiness notes when superseded by the canonical docs above

> **Note:** When a legacy document is referenced elsewhere, it should be prefixed with *Legacy:* and linked via this navigator for context only.

## Suggested reading order for new contributors

1. `../README.md` – repository overview and latest product version.
2. `DEVELOPING.md` – how to get the code running locally.
3. `OPERATIONS.md` – how to operate a board‑PC in the field.
4. `BOARD_PC_CERTIFICATION_RUNBOOK.md` – how to certify one real machine before RC claims.
5. `RC_FIELD_EVIDENCE_CHECKLIST.md` – what evidence must exist before shipping an RC.
6. `RELEASING.md` – how releases are built and published.
7. `EXTERNAL_DEVELOPER_HANDOFF.md` – product summary and status.
8. `ARCHITECTURE.md` – technical architecture details.

---
## Surface matrix (supported / optional / legacy)

| Surface | Status | Description |
|---|---|---|
| Core local runtime (backend, frontend admin/kiosk) | **Supported** | Fully validated by the authoritative test suite and nightly smoke checks.
| Central adapter (`central_server/`) | Optional | Present in‑tree for future expansion; not required for local operation.
| Historical wave notes (`docs/history/`) | **Legacy** | Retained for context only; may contain outdated information.
| Early implementation plans (`docs/PROJECT_MASTERPLAN_*.md`) | **Legacy** | Provides roadmap context; the current truth is captured in the canonical docs.

Use this matrix to decide which documentation to update when making changes.

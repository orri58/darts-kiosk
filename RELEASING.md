# Releasing Darts Kiosk

This document outlines the official release process, versioning strategy, and packaging details for the Darts Kiosk project.

---
## 1. Versioning
- The repository follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`).
- The single source of truth for the version number is the `VERSION` file at the repository root.
- Update the version **only** when a release is cut. Increment:
  - **MAJOR** for breaking changes to the protected local core.
  - **MINOR** for new features or optional central‑adapter enhancements.
  - **PATCH** for bug fixes and documentation updates.

---
## 2. Release preparation checklist
1. **Run the repo validation you can honestly run here**
   ```bash
   source .venv/bin/activate
   pytest -q
   ```
   Do not confuse this with field signoff; repo-green and board-PC-green are different claims.
2. **Ensure RC field evidence exists for Windows claims**
   - one real board-PC drill folder
   - `BOARD_PC_CERTIFICATION.md`
   - `RC_EVIDENCE_CHECKLIST.md`
   - paired summary + paired bundle + current handoff acknowledgment
   - see `docs/BOARD_PC_CERTIFICATION_RUNBOOK.md` and `docs/RC_FIELD_EVIDENCE_CHECKLIST.md`
3. **Bump the version**
   ```bash
   echo "4.4.19" > VERSION   # example
   ```
4. **Update changelog** (`CHANGELOG.md`) with a concise summary of changes.
5. **Commit and tag** the release
   ```bash
   git add VERSION CHANGELOG.md
   git commit -m "Release v4.4.19"
   git tag v4.4.19
   git push origin main --tags
   ```
6. **Build release artifacts**
   ```bash
   bash release/build_release.sh
   ```
   This creates three artifacts in `release/build/`:
   - `darts-kiosk-v4.4.19-windows.zip`
   - `darts-kiosk-v4.4.19-linux.tar.gz`
   - `darts-kiosk-v4.4.19-source.zip`
7. **Upload to GitHub Releases**
   - Draft a new release with tag `v4.4.19`.
   - Attach the three artifacts.
   - Publish.

---
## 3. Windows board‑PC update flow (operator side)
1. Open the Admin UI → **System → Updates**.
2. Click **Jetzt installieren** – the UI downloads the latest Windows bundle from the GitHub release.
3. The updater creates a backup, validates the package, and restarts the services.
4. After the install, the UI runs a built‑in smoke test. If it fails, use **Rollback** from the same screen.

---
## 4. Linux/Source deployment (lab or CI)
- Extract the Linux tarball on the target machine.
- Follow the same backend/frontend setup steps in **DEVELOPING.md**.
- No special installer scripts are required for Linux; the standard Docker compose workflow is used.

---
## 5. Rollback policy
- The Windows updater always keeps the previous version as a backup.
- If the new version fails the post‑install smoke test, the operator can click **Rollback** to restore the previous backup automatically.
- For Linux/source deployments, the operator must manually revert to the previous tag or commit.

---
## 6. Release notes generation (automation)
- The CI pipeline runs `release/build_release.sh` which also generates `release/source/RELEASE_NOTES.md` based on the `CHANGELOG.md` entries for the tagged version.
- Contributors should keep changelog entries concise and grouped by **Added**, **Improved**, **Fixed**, and **Validation**.

---
## 7. When to involve the core team
- Any change that touches the protected local‑core modules (`backend/*`, `frontend/src/pages/*`).
- Changes to the versioning or release scripts themselves.
- Release of a new major version (breaking changes).

---
**End of Releasing guide**
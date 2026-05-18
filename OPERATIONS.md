# Operations – Runbook for Darts Kiosk

This document is the primary operational guide for board‑PC maintainers and venue staff. It complements the developer‑focused **DEVELOPING.md** and the release‑focused **RELEASING.md**.

---
## 1. Daily start‑up
1. Power on the board PC.
2. Verify the Windows auto‑login (or manually log in as the dedicated kiosk user).
3. Open a command prompt and run:
   ```bat
   cd /d C:\path\to\darts-kiosk
   release\windows\start.bat
   ```
4. Open a browser to `http://localhost:8001/admin` and confirm the health page shows **OK**.
5. Verify the kiosk UI (`http://localhost:8001/kiosk/BOARD-1`) displays the expected layout and logo.

---
## 2. Unlocking a board
1. In the Admin UI, navigate to **Boards → BOARD‑1**.
2. Click **Unlock** and enter the number of credits to credit the session.
3. The board should immediately switch to the **unlocked** state and display the credit overlay.
4. If the board stays locked, check:
   - `data/logs/app.log` for errors.
   - Autodarts observer status (`/api/kiosk/BOARD-1/observer-status`).

---
## 3. Updating the software
1. In the Admin UI open **System → Updates**.
2. Click **Jetzt installieren** to download and install the latest Windows bundle.
3. The system will create a backup, validate the package, and restart the services.
4. After the update, run the smoke test:
   ```bat
   release\windows\smoke_test.bat
   ```
5. Verify that the board can still be unlocked and that the observer connects.
6. For any release-candidate or field-certification run, do not stop here — continue with the formal drill flow in `docs/BOARD_PC_CERTIFICATION_RUNBOOK.md` and keep the generated drill folder under `data/support/drills/<label>/`.

---
## 4. Troubleshooting common issues
### 4.1 Backend does not start
- Check `logs\backend.log` for Python import errors.
- Ensure the virtual environment is activated and dependencies are installed.
- Re‑run the Windows setup script:
  ```bat
  release\windows\setup_windows.bat
  ```

### 4.2 Chrome observer hangs
- Open **System → Device Ops → Autodarts ensure** to restart the observer.
- If the profile is corrupted, delete `data\chrome_profile\<BOARD_ID>` and run `release\windows\setup_profile.bat` again.

### 4.3 Board stays locked after unlock
- Verify the `BOARD_ID` in `backend\.env` matches the board shown in the Admin UI.
- Ensure the session was created (`/api/boards/BOARD-1/session`).
- Check the credit balance; a negative or zero balance will keep the board in a blocked state.

---
## 5. Safe recovery actions
- Use **System → Device Ops → Restart backend** for a quick service reset.
- Use **System → Device Ops → Windows reboot** only when you cannot recover via the UI.
- Export a support bundle before performing a rollback (Admin → System → Diagnostics → Export support bundle).

---
## 6. Rollback procedure
1. In **System → Updates**, click **Rollback** to restore the previous backup.
2. The service will restart automatically.
3. Run the smoke test again to confirm the system is healthy.

---
## 7. When to involve developers
- Persistent observer crashes after profile recreation.
- Credit deduction logic appears inconsistent with the match start.
- New Windows release fails validation (build errors, missing files).
- Any change to the protected local‑core modules (`backend/*` or `frontend/src/pages/*`).

---
## 8. Release-candidate field certification
- Use `docs/BOARD_PC_CERTIFICATION_RUNBOOK.md` for the actual board-PC pass.
- Use `docs/RC_FIELD_EVIDENCE_CHECKLIST.md` before calling a build RC-ready.
- The drill workspace now generates:
  - `BOARD_PC_CERTIFICATION.md/.json`
  - `RC_EVIDENCE_CHECKLIST.md/.json`
  - `DRILL_HANDOFF.md/.json`
- If those are missing or stale, the machine may be working, but the certification trail is not.

## 9. Contact & support
- Internal ticket system: `darts‑kiosk‑ops`
- Email: `support@darts-kiosk.example.com`
- For urgent on‑site issues, call the on‑call engineer listed in the shift schedule.

---
**End of Operations guide**
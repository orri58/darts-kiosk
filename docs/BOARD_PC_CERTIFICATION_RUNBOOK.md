# Board-PC Certification Runbook

Use this for the real Windows machine pass before calling a release candidate field-ready.

## Goal
Produce one drill folder that proves:
- the board PC booted and launched cleanly on Windows
- a real Autodarts/operator session worked
- update and rollback both executed on the same machine
- the evidence bundle is complete, current, and attached to a ticket

## Required inputs
- candidate Windows runtime/build artifact
- real board PC
- real Autodarts-capable setup
- board/device ID
- operator name
- service ticket/reference

## Board-side flow
1. Install or extract the candidate build on the board PC.
2. Confirm Admin -> Health -> Board-PC readiness is green enough to proceed.
3. Initialize a dedicated drill workspace:
   ```bat
   app\bin\init_drill_workspace.bat board-pc-rc BOARD-17 <operator> <ticket>
   ```
4. Capture the board-PC preflight baseline on the actual machine:
   ```bat
   app\bin\capture_board_pc_preflight.bat board-pc-rc BOARD-17 <operator> <ticket> <expected-version>
   ```
5. Prepare the closed-loop rehearsal/update lane.
6. Capture update-before evidence:
   ```bat
   app\bin\capture_field_evidence.bat before board-pc-rc BOARD-17 <operator> <ticket> update
   ```
7. Execute the real update on the machine.
8. Capture update-after evidence:
   ```bat
   app\bin\capture_field_evidence.bat after board-pc-rc BOARD-17 <operator> <ticket> update
   ```
9. Run a real unlock/play/observer sanity pass.
10. Capture rollback-before evidence:
   ```bat
   app\bin\capture_field_evidence.bat before board-pc-rc BOARD-17 <operator> <ticket> rollback
   ```
11. Execute the rollback on the same machine.
12. Capture rollback-after evidence:
   ```bat
   app\bin\capture_field_evidence.bat after board-pc-rc BOARD-17 <operator> <ticket> rollback
   ```
13. Finalize the handoff set:
   ```bat
   app\bin\finalize_drill_handoff.bat board-pc-rc
   ```
14. Capture the real-machine result snapshot / signoff baseline:
   ```bat
   app\bin\capture_board_pc_postflight.bat board-pc-rc <tested-by> pass BOARD-17 <operator> <ticket> "real board pass looked clean"
   ```
   If any machine check was mixed, blocked, or failed, use the direct Python command so the individual status fields are explicit.
15. Attach the minimal handoff set from `DRILL_HANDOFF.md` and record acknowledgment.

## Required artifacts in the drill folder
- `BOARD_PC_PREFLIGHT.md/.json`
- `BOARD_PC_POSTFLIGHT.md/.json`
- `BOARD_PC_CERTIFICATION.md/.json`
- `RC_EVIDENCE_CHECKLIST.md/.json`
- `DRILL_CHECKLIST.md`
- `DRILL_HANDOFF.md/.json`
- `DRILL_TICKET_COMMENT.txt/.md/.json`
- update/rollback before+after field states
- update/rollback reports
- update/rollback leg summaries
- paired summary (`.json` + `.md`)
- paired support bundle zip
- attachment readiness review

## Hard RC gate
Do not call the build field-ready unless all are true:
- paired closed loop passed
- rollback restored the starting version
- freshness checks are clean
- the real Windows/Autodarts flow was executed on hardware
- operator signoff is filled in
- ticket attachment acknowledgment is current

## Still not proven by repo-only validation
- Windows autostart after real reboot
- real observer/browser behavior against a live Autodarts session
- venue-specific device quirks
- long-running soak behavior

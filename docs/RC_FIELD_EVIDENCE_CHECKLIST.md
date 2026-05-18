# RC Field Evidence Checklist

Short version: no real Windows run, no honest RC.

## Minimum evidence set
- one named drill workspace under `data/support/drills/<label>/`
- board-PC postflight/result artifact present from the real machine
- update leg summary: pass
- rollback leg summary: pass
- paired summary: `closed_loop_passed=true`
- paired bundle zip present
- `DRILL_HANDOFF.md` recommendation not degraded by freshness drift
- `BOARD_PC_CERTIFICATION.md` filled in by the operator on the real machine
- `RC_EVIDENCE_CHECKLIST.md` reviewed by release owner
- ticket/reference recorded for the attached artifact set

## Human checks that must be executed on the machine
- Windows login/autostart path
- Admin health/readiness review
- unlock -> observer/game start -> credit deduction sanity pass
- update execution on the board PC
- rollback execution on the same board PC
- post-rollback reopen sanity

## Recommended evidence attachment set
Attach at least:
- paired support bundle zip
- `DRILL_HANDOFF.md`

Useful extras:
- `DRILL_TICKET_COMMENT.txt`
- `BOARD_PC_POSTFLIGHT.md`
- `BOARD_PC_CERTIFICATION.md`
- screenshots of Admin readiness + kiosk/observer state if a human reviewer needs them

## Disqualifiers
Do not ship on this evidence if:
- paired bundle/summary was regenerated after acknowledgment and not re-attached
- freshness warnings show stale or misordered artifacts
- operator notes mention unresolved manual intervention
- the run was only a repo-side dry simulation

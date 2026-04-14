# Model Continuity Protocol

## Goal

Work on `darts-kiosk` must continue cleanly even if:
- the current model changes
- context is compacted
- token budget is exhausted
- a later session/agent resumes the project

The project must not depend on fragile chat continuity.

---

## 1. Source of truth order

When resuming, use this order:

1. `EXECUTION_BOARD.md`
2. `docs/IMPLEMENTATION_GOVERNANCE.md`
3. `docs/IMPLEMENTATION_PLAN.md`
4. `docs/CENTRAL_CONTRACT.md`
5. `docs/DEVICE_TRUST_MODEL.md`
6. wave-specific docs under `docs/DEVICE_RUNTIME_PACKAGE_WAVE*.md` and related files
7. current repo diff / current test/build status

Chat history is secondary, not primary.

---

## 2. Required persistence discipline

Any meaningful wave of work must leave behind at least:
- code changes
- updated docs and/or execution board
- validation notes in the repo or memory

Never leave important progress only in transient chat text.

---

## 3. Wave handoff format

Every wave should be resumable by answering these five questions in files, not only in chat:

1. **What changed?**
2. **Why was it done this way?**
3. **What was validated?**
4. **What remains risky or incomplete?**
5. **What is the next clean block?**

This should normally be reflected in:
- `EXECUTION_BOARD.md`
- affected docs
- durable memory entry if strategically important

---

## 4. Do not require conversational memory

The next model must be able to continue if it has zero access to prior turns.
That means:
- no hidden TODOs only in chat
- no branch strategy only described verbally
- no “I remember where we were” assumptions

---

## 5. Execution style

- Continue autonomously block-by-block
- Delegate internally where useful
- Return user-facing updates only on real completed work
- Avoid idle gaps between waves
- Keep the visible interface unified even when multiple specialists are used internally

---

## 6. Protected-core continuity rule

Continuity must not come at the cost of unsafe experimentation.
Every resumed model must still respect:
- protected local core boundaries
- release gates
- rollback rules
- feature-flag-first rollout

---

## 7. Resume checklist for a new model/session

A new model/session taking over must:
1. read `EXECUTION_BOARD.md`
2. confirm current active themes
3. inspect current unstaged/staged repo state
4. choose the highest-value next block that does not violate protected-core rules
5. continue implementation, not restart planning from scratch

---

## 8. Practical policy for model swaps

If the model changes due to token/context constraints:
- do not re-open broad strategy unless the files indicate strategy changed
- prefer continuing the current wave or the next queued wave
- use repo docs + execution board as the durable baton handoff

This protocol exists specifically so project execution remains seamless across model swaps.

# State model

The ledger separates four state axes. Never collapse them into one traffic light.

## Goal state

Allowed values:

- `draft`: contract exists but execution has not started;
- `active`: useful work is proceeding or ready to proceed;
- `paused`: intentionally stopped and resumable without a blocker;
- `blocked`: a concrete condition prevents meaningful progress;
- `complete`: the completion contract is fully evidenced;
- `abandoned`: the user explicitly ended the objective without completion.

Goal state belongs in both frontmatters and must agree.

## Execution health

Allowed values:

- `healthy`: root execution can proceed normally;
- `degraded`: execution can proceed with a material limitation;
- `interrupted`: root execution stopped unexpectedly and needs reconciliation;
- `blocked`: the execution layer cannot make progress;
- `inactive`: no root execution is expected, normally after pause, completion, or abandonment.

Execution health describes the current run, not the objective.

## Custody

Allowed work-item values:

- `queued`: assigned next but not started;
- `active`: currently owned and executing;
- `waiting`: owner is waiting on a named dependency;
- `complete`: output returned to a stable path and reconciled;
- `failed`: the attempt ended unsuccessfully with evidence;
- `lost`: ownership or output cannot currently be recovered.

Every non-complete item needs a recovery action. A worker's process state is evidence about custody, not goal completion.

## Evidence

Allowed verification results:

- `pending`: required but not yet run;
- `pass`: the stated check succeeded;
- `fail`: the stated check ran and disproved the requirement;
- `blocked`: the check could not run because of a named blocker;
- `skipped`: deliberately omitted under an explicit rule, with reason.

Only `pass` proves a criterion. `skipped` is acceptable only when the exact row label appears in goal frontmatter under `allowed_skipped_verifications`; use semicolons between multiple labels and `none` when no skip is permitted.

## Phase state

Allowed values are `pending`, `active`, `blocked`, `complete`, and `skipped`. A skipped phase must be named in goal frontmatter under `allowed_skipped_phases`. Keep at most one phase active. A blocked phase does not automatically make every other phase or the entire goal blocked.

## Reconciliation invariants

- `goal.status == progress.status`.
- `status: complete` implies `execution_health: inactive`.
- Complete goals have only `complete` required custody; queued, active, waiting, failed, and lost items remain unresolved.
- Complete goals have only `complete` or explicitly allowed `skipped` phases.
- Complete goals have no pending/fail/blocked required verification.
- Complete goals have no open blocking gate.
- Generated HTML carries the digest of the current `goal.md` and `progress.md`.
- Requested execution profile and effective execution profile are distinct fields.

When facts conflict, preserve the more conservative state and record the contradiction as an open gate until evidence resolves it.

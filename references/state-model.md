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

Aggregate health follows the latest attempt, not the quality of its paperwork.
If the most recent launch, run, or campaign attempt failed,
`execution_health: healthy` is forbidden; set `degraded` at minimum until a
subsequent attempt passes. Truthful evidence leaves cannot coexist with a false
healthy root, and documentation quality never upgrades health.

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
- Requested, invoked, and effective execution profiles are distinct fields. Configuration, session visibility, and runtime confirmation are distinct evidence states.
- A required GPT Pro plan review must be reconciled and signed off before Build is active or complete; a required implementation review must be signed off before goal completion.
- Review lifecycle completion and review verdict are independent dashboard facts. Historical reconciled rounds remain visible after stage or phase changes and receive a completed marker without rewriting `REVISE` or `BLOCKED` as approval.
- GPT Pro transport state is independent of goal state. `packet-ready`, `ui-ready`, and `manual-handoff-ready` are resumable round states for MCP App, browser, or owner delivery and do not alone make the goal blocked. Once `submission.json` exists, recovery stays on that exact packet and transport; optional MCP unavailability before submission must fall through to another selected authorized route rather than creating a scientific blocker.
- Dashboard review nodes and progress tracks are derived views. Their states must come from review artifacts, Verification rows, phase rows, and gates rather than a separate mutable dashboard record.
- A preview URL with a past health check is historical evidence. Treat a stopped or failed endpoint as stale until restarted and checked again.
- **Retry authorization is hash-based, never launch-count-based.** A started goal's recorded Scope and Authorization are one standing execution envelope across phases and sessions. A scientific review binds the frozen scientific closure, not the execution environment and not a number of launches. Single-use, per-launch, and "consumed" ledger permits are forbidden. Apply the litmus test at every retry: **if the scientific closure hash is unchanged, no new approval of any kind is needed to retry**. Waiting for renewed approval of web or literature research, hardware or component research, downloads, goal-scoped dependency setup, bounded local work, implementation, tests, benchmarks, qualification, configured reviews, frozen retries, or an in-scope replacement run is ledger drift and cannot support `blocked`; manifests, environment hashes, resource caps, and failed attempts are custody evidence rather than permission boundaries.

When facts conflict, preserve the more conservative state and record the contradiction as an open gate until evidence resolves it.

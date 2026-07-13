# Recovery playbook

Use this reference after abnormal termination, compaction with uncertain state, stale generated output, contradictory ledgers, or custody that did not return cleanly.

## Preserve before restarting

1. Read `goal.md` and `progress.md` in full.
2. Inspect the repository, goal-tool state, running work, returned outputs, and named evidence paths independently.
3. Preserve useful uncommitted or delegated output at a stable repository path.
4. Reconcile every custody row before launching replacement work.
5. Mark execution health from observed facts, then refresh the recovery capsule.
6. Render and validate. Resume only from the smallest safe next action.

Do not overwrite an existing ledger, discard an unverified output, or restart a work item while another owner may still be active.

## Failure cases

### Root execution stopped

Record `execution_health: interrupted`. This proves only that the root run stopped. Inspect delegated workers and outputs before changing goal state or custody.

### Worker returned after the root stopped

Move its output to a stable path, run the relevant check, and mark custody `complete` only after reconciliation. A returned artifact is evidence, not automatic proof of the success criterion.

### Worker is unreachable

Mark custody `lost` only when ownership or output cannot be recovered. Name the expected output and the evidence checked. Do not close while required custody is lost.

### Generated HTML is stale

Keep Markdown authoritative. Run `render_goal.py --check` to confirm drift, render from Markdown, then validate. Never repair generated HTML directly.

### Ledger facts conflict

Preserve the more conservative state and add an open gate describing the contradiction. Resolve it from repository, runtime, or external evidence before continuing.

### Validation or rendering was interrupted

Treat the check as `pending` unless a complete result and stable artifact exist. Re-run the bounded command; do not infer success from partial output.

### External dependency blocks progress

Name the dependency, attempted checks, authorization boundary, and smallest user or external action that unblocks the run. Set the repository goal to `blocked` as soon as that dependency prevents meaningful progress; otherwise keep it active with honest execution health. Update an external goal-state tool to blocked only when that separate tool's own threshold is met.

## Recovery capsule contract

Keep these five facts short and current:

- last verified truth;
- current layer or phase;
- exact resume point;
- unsafe assumptions;
- canonical files and evidence paths.

After recovery, change execution health back to `healthy` or `degraded` only when current evidence supports it.

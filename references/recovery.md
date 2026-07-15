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

### Preview URL is blocked or stale

Never retry `file://`. Read `evidence/preview-server.json`, then run `serve_dashboard.py <goal-dir> --check`. If the health check fails, stop or reconcile the old process and restart the server. Prefer a connected Tailscale address; otherwise use localhost. If health passes but the dashboard is absent from the active task, use the same task's Browser skill to claim or create the tab, request visibility, verify the DOM, and retain it as a `deliverable`. If visibility cannot be confirmed, keep browser QA blocked rather than treating a hidden or external tab as delivered. A prior successful check proves only that timestamp, not that the endpoint is still live or visible.

### Owned agent is configured but unavailable

Configuration does not refresh an already-open task. Run `execution_profile.py preflight`; it must verify the owned profiles, registrations, and required `[features.multi_agent_v2]` values before routing. Open a new task after installation and check session visibility again. Record runtime confirmation only after the launched worker reports effective model and effort evidence. Never substitute a stale LazyCodex role silently.

### Fable is selected but exact approval cannot reach the owner

A recorded Fable choice of `yes` plus `fable_review_rounds` authorizes preparing the configured sequence; it does not prove exact packet approval. Remove any gate that asks the user to type another consent sentence. Run `execution_profile.py preflight --require-external-review-approval`. If it reports `auto_review`, `never`, or missing settings, use the explicitly authorized installer repair and open a new task. Restore the goal from blocked when no other blocker remains, prepare a fresh allow-list with `run_fable_feedback.py --prepare-transmission`, and submit the matching digest-bound command through the owner-facing native checkbox without editing any manifest file in between. If native policy denies after that exact user action, record the result and do not bypass it.

### GPT Pro submission or capture was interrupted

Read `evidence/pro-review/<stage>/round-NNN/state.json` and follow [pro-review.md](pro-review.md). `packet-ready` means probe the next ordered surface in `delivery-plan.json`; record the result instead of guessing availability. `ui-ready` may be submitted once through the recorded ready surface. `manual-handoff-ready` means present the checksum-bound owner instructions without calling the goal blocked solely for awaiting handoff. `submitted-waiting-response` means reopen and poll the existing thread; never send again. `response-received` means reconcile the preserved full response. A partial UI copy is not a response artifact: resume ordered capture from the same answer, verify its beginning and end, then record it once. Never fall back to prompt-only or a separate `$pro` skill.

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

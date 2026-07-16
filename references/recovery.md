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

For a long-running command, inspect its recorded tmux session before concluding that work stopped. Use the session, process tree, heartbeat, monitor, immutable segment logs, and checkpoints together. A missing terminal does not invalidate a healthy detached supervisor. A missing tmux session does not prove every child exited. Do not kill an orphan reflexively: preserve the attempt and determine whether custody can be recovered first. Reuse only validated hash-bound checkpoints, carry cumulative budgets and resource maxima across segments, and retry only the interrupted uncommitted dependency-complete unit. If no admissible checkpoint exists, report that limitation and rerun the smallest sound unit rather than fabricating results from process-state metadata. Follow [durable-execution.md](durable-execution.md).

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

A recorded Fable choice of `yes` plus `fable_review_rounds` selects the configured sequence. Remove any gate that asks the user to type another consent sentence or approve each round. If no valid `evidence/fable-goal-authorization.json` exists, obtain one bounded native approval with `run_fable_feedback.py --authorize-goal`; otherwise verify the next exact manifest stays inside it and resume automatically. Use exact-digest approval only when the packet is outside the standing envelope.

### A scientific route was terminally closed without a rescue checkpoint

Treat the terminal route decision as incomplete. Preserve any ad-hoc Fable response as advisory evidence, but do not retroactively count it as a rescue incident. Reconstruct the state immediately before the terminal decision, exclude operational blockers, and evaluate all five rescue triggers. If a trigger qualifies, create the formal candidate and run `run_fable_rescue.py --candidate ... --prepare-transmission`. If none qualifies, record an evidence-backed `not_qualified` decision with `--record-eligibility`. If subsequent in-scope work has already resolved the ambiguity and is still reducing uncertainty, do not consume an incident retroactively; record why the earlier checkpoint was missed and require the checkpoint at the next terminal scientific branch.

### GPT Pro submission or capture was interrupted

Read `evidence/pro-review/<stage>/round-NNN/state.json` and follow [pro-review.md](pro-review.md). `packet-ready` means check the selected transport in `delivery-plan.json`; `auto-ui` continues through MCP App, native Chat, platform browser, and owner handoff. For `mcp-app`, restart the exact round-bound command from `run_review_bridge.py print-command` and rerun its packet preflight. For `native-chat`, present the existing hash-bound instructions and wait for the owner to click **Add to task**; do not drive the host app or resubmit. Record every result instead of guessing availability. `ui-ready` may be submitted once through the recorded ready route. `manual-handoff-ready` means present the checksum-bound owner instructions without calling the goal blocked solely for awaiting handoff. `submitted-waiting-response` means reopen the same Pro conversation or restart only the identical manifest-bound MCP bridge; never send again or switch transports. `response-received` means reconcile the preserved full response. A partial imported or UI copy is not a response artifact: resume capture from the same answer, verify its beginning and end, then record it once. Never fall back to prompt-only or a separate `$pro` skill.

### Ledger facts conflict

Preserve the more conservative state and add an open gate describing the contradiction. Resolve it from repository, runtime, or external evidence before continuing.

### Validation or rendering was interrupted

Treat the check as `pending` unless a complete result and stable artifact exist. Re-run the bounded command; do not infer success from partial output.

### In-scope work is waiting for renewed owner authorization

Treat this as ledger drift, not an external blocker. Starting the goal already authorized the entire accepted execution envelope, including web and literature research, hardware and component research, downloads, goal-scoped dependency setup, bounded local compute, tests, benchmarks, qualification campaigns, frozen retries, implementation, configured reviews, and in-scope replacement runs. A new manifest, hash, resource cap, failed attempt, contract revision, or resumed task does not revoke that authority. Remove the redundant gate, restore goal and phase state to the evidence-supported active state, preserve the prepared custody artifacts, and execute the smallest safe next action. Do not wait three turns, request a typed authorization sentence, or mark the goal blocked. Ask only if the next action is genuinely outside the recorded envelope or hits an unavoidable platform-native security boundary that was not pre-authorized.

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

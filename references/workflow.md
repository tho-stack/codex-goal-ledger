# Goal ledger workflow

Use this reference when initializing a long run, deciding update cadence, handing off work, recovering from interruption, or closing a goal.

## 1. Ask during planning, before execution

Read the supplied goal or brief in full, then perform only the bounded inspection needed to make contextual recommendations: inspect the repository, existing `docs/goals/`, git state, current goal-tool state, running workers, and known gates. Parallelize independent reads; keep dependent decisions sequential. Do not implement, delegate, or start long-running validation during this discovery pass.

Begin the planning checkpoint with an explicit input assessment:

- **Required before execution**: ask the smallest missing question only when its answer can change scope, architecture, permission, or the completion bar.
- **Optional, improves result**: list at most three concrete inputs that could materially improve quality, confidence, usability, or efficiency. For each, state **Information**, **What it improves**, and **Default if omitted**.

If no optional context would materially help, say so directly. Do not ask for information that repository or connected-tool discovery can answer. Optional context must not block the run: when omitted, use the stated default and record any decision-bearing assumption in `goal.md` or the Decision log.

Use this compact shape:

```text
Required before execution
- None, or the smallest blocking question.

Optional, improves result
Information | What it improves | Default if omitted
...
```

An effective required-input round covers:

- what outcome the user will recognize;
- why it matters;
- what proves completion;
- what actions need approval;
- whether to use the default Luna Max implementer, another owned preset, or a mixed swarm for genuinely independent work.

For an unattended or overnight goal, define one positive execution envelope rather than a list of command-level approvals. Include the repositories and data sources, web or literature research, hardware or component research, downloads and dependency setup, expected local or network tools, bounded compute and experiments, review destinations, hardware interfaces if any, and explicit exclusions. If the user says to authorize the whole goal, record the broad non-destructive envelope and proceed; do not turn every category into another question.

Make this the first interactive planning checkpoint. In the same checkpoint, ask for an explicit `yes` or `no` on all six independent items and show a contextual recommendation:

1. Claude Fable peer feedback — recommend `yes` when the plan is difficult, ambiguous, high-risk, or benefits from feature and science ideation by a second model before implementation; ask for 1-10 rounds (default 1) and explain that one bounded native approval can cover every configured round and rescue incident inside the disclosed path envelope;
2. Claude Fable scientific rescue — recommend `yes` for hard scientific goals, otherwise `no`; default to two lineage-scoped incidents, one round per incident, and XHigh effort;
3. native GPT Pro review — recommend `yes` for difficult, ambiguous, scientific, or high-risk work; use MCP-first `auto-ui`, followed by user-operated native Chat/Pro plus **Add to task**, Safari/Chrome, and owner handoff, while offering explicit transport, stage, gate, and 1-3-round selectors;
4. external LLM review prompt — recommend `yes` for non-trivial or high-risk work;
5. additional `$codex-review` — recommend `yes` when code changed and a second closeout pass is useful;
6. clean-session GPT handoff prompt — recommend `yes` for overnight, interruption-prone, or multi-session work.

Follow [planning-controls.md](planning-controls.md). When `request_user_input` is available, the six booleans must be two consecutive three-question native-control interactions, followed immediately by selected lane settings and the stepped implementation family/effort selector. Do not replace available native controls with a prose `yes/no` request. The current tool has no literal multi-select checkbox group or range slider; do not claim one. Use one concise Markdown checklist only when structured input is unavailable. Never split the checkpoint across unattended work or defer it to verification, a status update, or closeout.

Wait only for required missing facts and unresolved review choices unless the user asks to pause for optional context. Do not initialize the execution plan, implement, delegate, start long-running work, or enter unattended execution while a required item remains unresolved. Record review answers under `## Closeout options` plus Fable and GPT Pro selectors in `goal.md`. Use `ask` only while waiting at this checkpoint. Silence is not a `yes` or `no`. A Fable `yes` selects the lane; obtain one bounded native approval for the goal directory and any explicit extra files before the first external call, then reuse it for all covered rounds. Never ask for a typed consent sentence. A GPT Pro `yes` authorizes only the exact generated request and packet for ChatGPT Pro; never expand transmission silently.

Do not ask for labels or ceremony the repository can derive.

## 2. Initialize the durable contract

Run `scripts/init_goal.py` with a lowercase hyphenated slug. Pass `--fable-feedback`, `--fable-review-rounds`, `--fable-rescue`, its incident settings, `--pro-review` plus its stage, delivery, gate, and round settings, `--external-review-prompt`, `--codex-review`, and `--clean-session-handoff` with the recorded choices. The initializer accepts `ask` only as an honest temporary state. It creates the canonical Markdown, generated dashboard, shared assets, and evidence directory without network dependencies.

Review the generated contract before execution. Replace every scaffolded success criterion with an observable check. Record non-goals and approval boundaries once.

Initialization establishes standing execution authority for the entire accepted envelope. After the planning checkpoint is resolved and the goal starts, proceed automatically across phases and sessions with all recorded work: repository and browser actions, network/web and literature research, hardware and component research, downloads, goal-scoped dependency setup, implementation, delegation, bounded compute, tests, benchmarks, qualification campaigns, frozen retries, configured reviews, and temporary-environment work. Exact manifests, hashes, fixed resource limits, changed implementation details, failed attempts, successor fixtures, and resumed sessions strengthen custody but do not require renewed permission. Ask again only when the next action is outside the envelope or requires a platform-native security confirmation that was not safely pre-authorized. Purchases, public publishing or messages, destructive actions, secret disclosure, unsafe physical operations, and material scope expansion are outside the default envelope unless positively included and bounded. An explicitly owner-requested prepare-only contract is also a real boundary; the agent may not create that restriction after goal start.

Pass the primary preset as `init_goal.py --implementation-agent <agent-name>` and repeat `--swarm-implementer <agent-name>` only for additional independently owned lanes. Mirror that selection in `scripts/execution_profile.py preflight --implementer <agent-name>` with repeated `--swarm-implementer` arguments before routing implementation. Preflight must verify the owned agent registrations and the required `[features.multi_agent_v2]` values before swarm work is promised. If the owned profiles were just installed, open a new task and verify that every selected implementer plus `goal-ledger-reviewer` is session-visible. Record configured, session-visible, invoked, and runtime-confirmed states separately in the v4 Execution profile table.

When Fable feedback is `yes`, first run `execution_profile.py preflight --require-external-review-approval` while still in planning. Run `run_fable_feedback.py <goal-dir> --authorize-goal` once through the native owner-facing approval surface, adding `--authorization-context-file` only for known required files outside the goal directory. The authorization records destination, model, allowed efforts, configured planning and rescue counts, path envelope, and byte ceiling. Prepare round 1 after the contract and phase plan stabilize and before implementation. Every call still produces an exact manifest and durable hash evidence, but reconciled changes to covered files do not require another owner approval. Expand the envelope once only when a genuinely new path is required. Default to High effort; use XHigh only for difficult or high-risk planning. Reconcile each round before running the next one. See [fable-peer.md](fable-peer.md).

When scientific rescue is `yes`, keep it armed and evaluate it automatically before any scientific route is abandoned or receives a terminal `no-campaign`, `unresolvable`, or mechanism-rejection decision. A qualified route must enter the dedicated durable runner immediately; an unqualified route must have an evidence-backed `not_qualified` record covering every trigger. An ad-hoc Fable review is not a rescue checkpoint. Do not interrupt active work that is still reducing its declared uncertainty, issue raw Claude commands, or classify operational failures as scientific uncertainty. See [fable-rescue.md](fable-rescue.md).

When GPT Pro review is `yes`, follow [pro-review.md](pro-review.md) without invoking a separate `$pro` skill. Prepare an immutable prompt plus scoped ZIP after the selected stage is stable. With `mcp-app`, follow [review-bridge.md](review-bridge.md): bind the bundled server to that exact packet, connect through OpenAI Secure MCP Tunnel, and let Pro drive the bounded workspace with `open_workspace`, `list_files`, `read`, `search`, and one `write_review` call. In `auto-ui`, check routes in order: MCP App, user-operated native Chat/Pro, Safari/Chrome, then owner handoff. Preserve the entire raw response and record typed local reconciliation. A required plan lane gates Build; a required implementation lane gates completion.

When a goal-state tool is available, create a compact objective that points to `goal.md`. Do not duplicate a long contract into a goal field that may truncate or reject it.

## 3. Plan the run

Build phases around outcomes, not arbitrary task counts. A typical long run has discover, define, build, verify, and close phases, but change these when the work demands it.

Before unattended execution:

- confirm one active primary phase and one next critical-path gate; this is a milestone indicator, not a mutex or global execution lock;
- derive a dependency-aware workstream plan. For each lane record its deliverable, `blocked_by` prerequisites (or `none`), mutation class (`read-only`, `repository-write`, `external-write`, `live-hardware`, or `purchase`), owner/state, and stable evidence path;
- split research from implementation, live operation, and purchasing whenever their dependencies differ. Do not put independent hardware, literature, interface, operating-system, or component research behind a scientific implementation gate;
- allocate an explicit concurrency budget before launch: reserve slots for the root, active supervisors, and required gate reviewers, then assign the remaining slots to named dependency-free lanes. Delegated workers may not recursively spawn a second swarm unless the root allocated those slots and ownership boundaries in advance;
- launch every authorized dependency-free lane within that budget. Keep only true descendants queued, reconcile every started or interrupted descendant before closing its parent lane, and recompute ready lanes after every gate result, custody return, interruption, or contract revision;
- read `durable-execution.md`, run `execution_profile.py preflight --require-tmux`, and record the resolved tmux path/version before any long-running, monitored, overnight, or interruption-sensitive command;
- launch the outermost supervisor in a detached task-scoped tmux session, verify its session, process, and first heartbeat, and require atomic checkpoints for expensive multi-stage work; never detach only the scientific child while leaving its monitor terminal-bound;
- preflight the entire execution envelope, surface any platform-native confirmations that would otherwise interrupt the run, and obtain safely scoped reusable approvals while the owner is present when the platform supports them;
- include every selected closeout lane in the phase plan so it can complete without waiting for the user to return;
- assign every delegated work item in Custody;
- record expected outputs and stable evidence paths;
- record requested, invoked, and effective execution profiles;
- note time-sensitive, permission, network, or external-system blockers;
- update the recovery capsule.

Generate selected prompt artifacts once the contract is stable. After implementation verification, run a selected additional Codex review without another approval round, reconcile its findings, and rerun affected checks before final closeout. Never wait until the final response to discover or schedule a review the user selected during planning.

## 4. Execute with sparse updates

Send a short user-visible preamble before the first tool call. Update the user when a phase changes or a finding changes the plan. Each update states the concrete outcome and next step.

Update `progress.md` when:

- a phase starts, completes, blocks, or is skipped;
- a decision changes execution;
- a worker takes or returns custody;
- a required check passes, fails, or becomes unavailable;
- the root execution degrades or interrupts;
- a long unattended stretch is about to begin;
- the final response is imminent.

Render and validate after each material ledger update. Check selected prompt artifacts with `scripts/generate_closeout_prompts.py <goal-dir> --check`. Correct the Markdown when HTML exposes a contradiction; never patch generated HTML by hand.

The rendered review circuit must remain a derived view of Fable, GPT Pro, rescue, Codex-review, phase, Verification, and gate evidence. Keep run, evidence, reviews, and gates as separate discrete tracks. A return arrow represents a recorded revise or blocked verdict, not decoration; never replace the tracks with a weighted overall percentage.

After the render succeeds, start or reuse `scripts/serve_dashboard.py <goal-dir>`. Never navigate directly to `index.html` with `file://`. In automatic mode the server prefers a connected Tailscale IPv4 address and MagicDNS display name; if Tailscale is missing, disconnected, or cannot bind, it uses `127.0.0.1`. It selects an available port, confines file access to the goal directory plus the two allow-listed shared dashboard assets, writes `evidence/preview-server.json`, and exposes an HTTP health endpoint. Run `serve_dashboard.py <goal-dir> --check`, then use the Browser skill in the same Codex task. Claim a matching in-app tab or create one, navigate or reload the reported URL, request browser visibility, and verify both the visible-state capability and page DOM. Finalize the tab as a `deliverable` so it remains attached to the task. A healthy endpoint, an external browser window, or a hidden in-app tab does not satisfy in-session delivery. If visibility stays false or browser control is unavailable, record browser QA as pending or blocked, retain the URL and server evidence, and do not claim the dashboard loaded in the task.

## 5. Preserve evidence

Evidence is a path plus a result, not a confidence adjective. Record:

- the command or inspection performed;
- result: pass, fail, blocked, skipped, or pending;
- the artifact or stable path;
- material caveats.

Do not call a check passed because a related command succeeded. Do not turn absence of evidence into a factual negative.

If a log grows past roughly 30 entries, roll older entries into `evidence/log-<date>.md`, link the archive from the Work log, and keep the current decision-bearing entries visible.

## 6. Hand off custody

Every delegated item gets an owner, state, and recovery action. Until return, name the expected output in the recovery action; after return, repatriate it to a stable path and record that path before marking custody complete.

Use the selected Goal Ledger implementer preset for bounded implementation, `goal-ledger-gate-reviewer` for fast independent operational gates, and `goal-ledger-reviewer` for deep or final independent review. Give the gate reviewer only the immutable gate packet and named evidence required for `GO`, `BLOCKED`, or `NEEDS_DEEP_REVIEW`; escalate the last verdict rather than expanding the fast review indefinitely. A swarm may mix presets only across independently owned work items; record the exact agent name on every Custody row and reconcile each worker's runtime evidence separately. If the orchestration surface cannot expose a selected role or explicit model and effort controls, record that limitation. Do not encode configuration or desired routing as an accomplished runtime assignment.

## 7. Recover after interruption

Use this order:

1. read the goal and progress ledgers;
2. inspect actual repository state and evidence paths;
3. inspect root execution and worker state independently;
4. reconcile custody item by item;
5. preserve any returned or orphaned artifacts;
6. mark execution health and current phase honestly;
7. refresh the recovery capsule;
8. render and validate;
9. resume from the smallest safe next action.

A root task stopping proves only that the root execution stopped. It does not prove that workers did no work, files were not changed, or the goal failed.

## 8. Close honestly

Completion requires all of the following:

- every success criterion has direct evidence;
- every required verification is pass or a skip explicitly named in `allowed_skipped_verifications`;
- every skipped phase is explicitly named in `allowed_skipped_phases`;
- no blocking gate remains;
- every required custody item is complete;
- goal and progress statuses agree;
- generated HTML matches the Markdown digest;
- the dashboard was served through a health-checked HTTP endpoint rather than `file://`, with a visible same-task in-app Browser deliverable recorded or browser QA honestly blocked;
- all six review, rescue, and handoff choices are explicit `yes` or `no`;
- every selected Fable round exists, is structurally valid, and has one passing Verification row covering all round artifacts;
- every used Fable rescue incident is structurally valid, reconciled, and closed without serving as completion evidence;
- every selected GPT Pro stage and round has a valid immutable packet, observed submission, full raw response, typed reconciliation, and required sign-off when configured as a gate;
- each selected closeout prompt exists and passes the generator's synchronization check;
- any selected Codex review has completed under its advisory review contract;
- final git/commit state is stated exactly.

If any condition fails, keep the goal active or blocked as appropriate and record the smallest unblocking action.

Repository `status: blocked` describes the objective and may be recorded as soon as a concrete condition prevents meaningful work. An external goal-state tool may impose a separate repeated-blocker threshold; honor that threshold without rewriting the repository state to match it.

Waiting for renewed approval of already-authorized in-scope execution is not a concrete blocker. Remove that gate, restore the phase and goal to the evidence-supported active state, and continue from the prepared action. Three repeated idle turns do not legitimize an invented approval dependency.

When external LLM review is `yes`, generate `review-prompt.md` beside `goal.md`. When clean-session handoff is `yes`, generate `handoff-prompt.md` beside `goal.md`. Run:

```bash
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug>
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug> --check
```

When additional Codex review is `yes`, use `$codex-review` as an advisory gate: verify each finding against source and adjacent behavior, accept or reject it with evidence, rerun focused checks after accepted fixes, and rerun the review until no accepted actionable finding remains. Do not push merely to run or satisfy review.

See [closeout-kit.md](closeout-kit.md) for prompt contents, synchronization, and handoff rules.

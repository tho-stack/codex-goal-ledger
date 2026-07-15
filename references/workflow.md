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

Make this the first interactive planning checkpoint. In the same checkpoint, ask for an explicit `yes` or `no` on all six independent items and show a contextual recommendation:

1. Claude Fable peer feedback — recommend `yes` when the plan is difficult, ambiguous, high-risk, or benefits from feature and science ideation by a second model before implementation; ask for 1-10 rounds (default 1) and explain that `yes` authorizes preparing the Anthropic review lane while every fresh exact hashed manifest still receives an owner-facing native approval checkbox;
2. Claude Fable scientific rescue — recommend `yes` for hard scientific goals, otherwise `no`; default to two lineage-scoped incidents, one round per incident, and XHigh effort;
3. native GPT Pro review — recommend `yes` for difficult, ambiguous, scientific, or high-risk work; default to one required plan round through platform-aware `auto-ui` with a prompt plus deterministic ZIP, and offer explicit Safari, Chrome, ChatGPT desktop, owner-handoff, stage, gate, and 1-3-round selectors;
4. external LLM review prompt — recommend `yes` for non-trivial or high-risk work;
5. additional `$codex-review` — recommend `yes` when code changed and a second closeout pass is useful;
6. clean-session GPT handoff prompt — recommend `yes` for overnight, interruption-prone, or multi-session work.

Present the six booleans as independent checkboxes or yes/no toggles. Prefer consecutive structured-input modals of at most three questions each, followed immediately by any selected Fable or Pro selectors; this keeps proper app controls while completing one planning checkpoint. Use one concise Markdown checklist only when structured input is unavailable. Never split the choices across wakeups or defer them to verification, a status update, or closeout.

Wait only for required missing facts and unresolved review choices unless the user asks to pause for optional context. Do not initialize the execution plan, implement, delegate, start long-running work, or enter unattended execution while a required item remains unresolved. Record review answers under `## Closeout options` plus Fable and GPT Pro selectors in `goal.md`. Use `ask` only while waiting at this checkpoint. Silence is not a `yes` or `no`. A Fable `yes` is lane authorization; exact transmission approval comes later from the native checkbox after manifest disclosure. Never ask for a typed consent sentence or manufacture exact approval from the lane choice. A GPT Pro `yes` authorizes only the exact generated request and packet for ChatGPT Pro; respect the live Computer Use action-time policy and never expand transmission silently.

Do not ask for labels or ceremony the repository can derive.

## 2. Initialize the durable contract

Run `scripts/init_goal.py` with a lowercase hyphenated slug. Pass `--fable-feedback`, `--fable-review-rounds`, `--fable-rescue`, its incident settings, `--pro-review` plus its stage, delivery, gate, and round settings, `--external-review-prompt`, `--codex-review`, and `--clean-session-handoff` with the recorded choices. The initializer accepts `ask` only as an honest temporary state. It creates the canonical Markdown, generated dashboard, shared assets, and evidence directory without network dependencies.

Review the generated contract before execution. Replace every scaffolded success criterion with an observable check. Record non-goals and approval boundaries once.

Pass the primary preset as `init_goal.py --implementation-agent <agent-name>` and repeat `--swarm-implementer <agent-name>` only for additional independently owned lanes. Mirror that selection in `scripts/execution_profile.py preflight --implementer <agent-name>` with repeated `--swarm-implementer` arguments before routing implementation. Preflight must verify the owned agent registrations and the required `[features.multi_agent_v2]` values before swarm work is promised. If the owned profiles were just installed, open a new task and verify that every selected implementer plus `goal-ledger-reviewer` is session-visible. Record configured, session-visible, invoked, and runtime-confirmed states separately in the v4 Execution profile table.

When Fable feedback is `yes`, first run `execution_profile.py preflight --require-external-review-approval` while still in planning. If it fails, repair configuration only with explicit authority and open a new task; do not wait until the review call to discover that approval is auto-reviewed or disabled. Prepare round 1 after the contract and phase plan stabilize and before implementation. Add only repository-relative `--context-file` evidence needed beyond the automatically included goal, progress, and prior-round files. Inspect the emitted paths, sizes, hashes, destination, and digest, then submit the identical command with `--approve-transmission <digest>` through Codex `require_escalated`; put those concrete details in the native justification so the owner-facing checkbox is informed and exact. Do not create a reply-based approval gate. Default to High effort; use XHigh only for difficult or high-risk planning. After each round, surface optional information; verify and reconcile findings, feature ideas, and scientific hypotheses; record proposal decisions; update and validate the plan; then prepare a new manifest for the next round. In-scope proposals may enter the contract only after verification. Adjacent or future proposals remain deferred unless the user authorizes scope expansion. Do not run identical back-to-back reviews against an unreconciled plan. Record all round artifacts in Verification. See [fable-peer.md](fable-peer.md).

When scientific rescue is `yes`, keep it armed until a structured incident candidate qualifies. Use the dedicated durable runner and follow its prediction-lock, reconciliation, outcome, lineage-cap, and owner-gate contract. Do not issue raw Claude commands or classify operational failures as scientific uncertainty. See [fable-rescue.md](fable-rescue.md).

When GPT Pro review is `yes`, follow [pro-review.md](pro-review.md) without invoking a separate `$pro` skill. Prepare an immutable prompt plus scoped ZIP after the selected stage is stable. In `auto-ui`, probe the generated platform order with Computer Use and record every result. Submit once through the first ready Safari, Chrome, or ChatGPT desktop surface; if none is ready, present the generated checksum-bound owner handoff. Preserve the entire raw response and record typed local reconciliation. A required plan lane gates Build; a required implementation lane gates completion. Recover from the round state instead of resubmitting after interruption.

When a goal-state tool is available, create a compact objective that points to `goal.md`. Do not duplicate a long contract into a goal field that may truncate or reject it.

## 3. Plan the run

Build phases around outcomes, not arbitrary task counts. A typical long run has discover, define, build, verify, and close phases, but change these when the work demands it.

Before unattended execution:

- confirm one active phase and one next gate;
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

Use the selected Goal Ledger implementer preset for bounded implementation and `goal-ledger-reviewer` for independent read-only review. A swarm may mix presets only across independently owned work items; record the exact agent name on every Custody row and reconcile each worker's runtime evidence separately. If the orchestration surface cannot expose a selected role or explicit model and effort controls, record that limitation. Do not encode configuration or desired routing as an accomplished runtime assignment.

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

When external LLM review is `yes`, generate `review-prompt.md` beside `goal.md`. When clean-session handoff is `yes`, generate `handoff-prompt.md` beside `goal.md`. Run:

```bash
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug>
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug> --check
```

When additional Codex review is `yes`, use `$codex-review` as an advisory gate: verify each finding against source and adjacent behavior, accept or reject it with evidence, rerun focused checks after accepted fixes, and rerun the review until no accepted actionable finding remains. Do not push merely to run or satisfy review.

See [closeout-kit.md](closeout-kit.md) for prompt contents, synchronization, and handoff rules.

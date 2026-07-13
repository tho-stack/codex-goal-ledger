# Goal ledger workflow

Use this reference when initializing a long run, deciding update cadence, handing off work, recovering from interruption, or closing a goal.

## 1. Discover before asking

Read the supplied goal or brief in full, then inspect the repository, existing `docs/goals/`, git state, current goal-tool state, running workers, and known gates. Parallelize independent reads; keep dependent decisions sequential.

Ask the smallest missing question only when its answer can change scope, architecture, permission, or the completion bar. An effective first round covers:

- what outcome the user will recognize;
- why it matters;
- what proves completion;
- what actions need approval;
- whether to use a recommended quality-first profile or the current available runtime.

Include one bundled closeout choice in the same planning round. Ask for an explicit `yes` or `no` on all three items and show a contextual recommendation:

1. external LLM review prompt — recommend `yes` for non-trivial or high-risk work;
2. additional `$codex-review` — recommend `yes` when code changed and a second closeout pass is useful;
3. clean-session GPT handoff prompt — recommend `yes` for overnight, interruption-prone, or multi-session work.

Record the answers under `## Closeout options` in `goal.md`. Use `ask` only while an answer is unresolved. Silence is not a `yes` or `no`, and a ledger with an `ask` choice cannot close.

Do not ask for labels or ceremony the repository can derive.

## 2. Initialize the durable contract

Run `scripts/init_goal.py` with a lowercase hyphenated slug. Pass `--external-review-prompt`, `--codex-review`, and `--clean-session-handoff` with the recorded `yes` or `no` choices. The initializer accepts `ask` only as an honest temporary state. It creates the canonical Markdown, generated dashboard, shared assets, and evidence directory without network dependencies.

Review the generated contract before execution. Replace every scaffolded success criterion with an observable check. Record non-goals and approval boundaries once.

When a goal-state tool is available, create a compact objective that points to `goal.md`. Do not duplicate a long contract into a goal field that may truncate or reject it.

## 3. Plan the run

Build phases around outcomes, not arbitrary task counts. A typical long run has discover, define, build, verify, and close phases, but change these when the work demands it.

Before unattended execution:

- confirm one active phase and one next gate;
- assign every delegated work item in Custody;
- record expected outputs and stable evidence paths;
- record requested and effective execution profiles;
- note time-sensitive, permission, network, or external-system blockers;
- update the recovery capsule.

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

After the render succeeds, automatically show the generated `index.html` in Codex's in-app preview. Reuse and reload the existing preview tab for later renders instead of opening duplicates. Keep the preview available as a deliverable while work continues. This is an orchestration step: the renderer must not launch programs. Never use a shell `open` command, an external browser, a hardcoded executable, or a machine-specific application path. If the current Codex surface has no preview integration, record that limitation and continue with deterministic render checks; do not silently substitute another program.

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

If the orchestration surface cannot set a requested model per worker, record that limitation. Do not encode desired routing as an accomplished assignment.

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
- all three closeout choices are explicit `yes` or `no`;
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

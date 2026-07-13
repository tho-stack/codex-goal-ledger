---
name: codex-goal-ledger
description: Run, recover, audit, resume, and honestly close long-running Codex goals with repo-local goal and progress Markdown, generated interactive HTML, custody tracking, evidence gates, and capability-aware execution profiles. Use for overnight or interruption-prone work, durable handoffs, multi-agent recovery, or any task that must remain trustworthy across compaction, restarts, and new sessions.
---

# Codex Goal Ledger

Create a durable operating record for long-running work. A successful ledger lets another session determine the true state and smallest safe next action from repository files alone.

## Canonical artifacts

Keep one goal at:

```text
docs/goals/<goal-slug>/
├── goal.md
├── progress.md
├── index.html
├── review-prompt.md      # optional, when selected
├── handoff-prompt.md     # optional, when selected
└── evidence/
```

Shared presentation assets live in `docs/assets/goal-ledger.css` and `docs/assets/goal-ledger.js`.

- `goal.md` is the human contract: why, outcome, success criteria, scope, authorization, and completion bar.
- `progress.md` is live operational truth: phase, execution health, custody, evidence, gates, recovery, and next action.
- `index.html` is generated. Never treat it as the source of truth.
- `review-prompt.md` and `handoff-prompt.md` are deterministic, opt-in closeout artifacts. Regenerate them from the canonical choice table; do not hand-edit them.
- Evidence belongs under the goal directory or at a stable repo path linked from the ledger.

## Start or resume

1. Read any user-supplied goal, brief, gate, or policy file in full. Treat explicit choices and hard boundaries as authoritative.
2. Inspect the repository, current goal-tool state when available, and any existing goal directory before asking questions.
3. Ask only for missing facts that can materially change execution:
   - why the work matters;
   - the user-visible outcome;
   - observable completion criteria;
   - authorization boundaries;
   - execution profile when the user has not chosen one.
4. In that planning round, ask one bundled closeout question and recommend a choice for each item:
   - generate `review-prompt.md` for Claude or another independent LLM;
   - run an additional `$codex-review` closeout;
   - generate `handoff-prompt.md` for a new clean GPT session.
5. Record an explicit `yes` or `no` for all three rows in `goal.md` under **Closeout options**. Keep an unanswered item as `ask`; do not infer consent from silence or close the goal while any row remains `ask`.
6. Do not ask for ceremonial metadata such as a session name, arbitrary subgoal count, or preferred log length.
7. Initialize missing artifacts with `scripts/init_goal.py`. Preserve existing artifacts unless the user authorizes replacement.
8. If a goal-state tool exists and no matching goal is active, create a short pointer objective to `goal.md`; keep the full contract in the repository.

For difficult quality-first overnight builds, recommend this profile without making it universal:

- planning and architecture: GPT-5.6 Sol at `xhigh`; reserve `max` for the hardest pass;
- implementation: GPT-5.6 Terra at `max` when the runtime supports that selection;
- final adversarial review: GPT-5.6 Sol at `xhigh`, or `max` when justified.

Preserve explicit user selections. Record both requested and effective profiles. If the current surface cannot select a model or reasoning level, say so and record the fallback; never imply that a switch occurred. A subagent tool without model controls does not prove a model assignment. Read [model-execution-profile.md](references/model-execution-profile.md) when routing or runtime capability matters.

## Operate

Keep these four layers separate:

1. **Goal state**: whether the objective is draft, active, blocked, paused, complete, or abandoned.
2. **Execution health**: whether the current root execution is healthy, degraded, interrupted, or blocked.
3. **Custody**: who owns each work item and whether it is queued, active, waiting, complete, failed, or lost.
4. **Evidence**: what was actually verified, where the artifact lives, and what remains unproven.

Never infer one layer from another. A failed root execution can coexist with completed delegated work; a running worker does not make the goal complete.

Use one authorization policy:

- For review, diagnosis, or planning, inspect and report; do not implement unless asked.
- For build, change, or fix requests, make in-scope local edits and run non-destructive validation without another approval prompt.
- Ask before external writes, destructive actions, purchases, global installation, or material scope expansion.

Update `progress.md` at major phase changes, after meaningful evidence, before a long unattended stretch, after interruption, and before final response. Each update records one concrete outcome and the next gate. Do not narrate routine tool calls.

After every material ledger update:

1. render `index.html`;
2. run the validator;
3. check selected closeout prompts for synchronization;
4. open the generated progress dashboard in Codex's in-app preview, or reload its existing preview tab;
5. correct stale, contradictory, or unsupported claims before continuing.

Preview is an orchestration action, not a renderer side effect. Reuse the Codex preview tab and keep it available as a user-facing deliverable. Never shell-open a browser, launch an external browser executable, or hardcode an application path. If the active Codex surface has no in-app preview capability, report that limitation instead of substituting an external program.

When the work log becomes unwieldy, move older detail into `evidence/log-<date>.md`, link it, and retain only the recent decision-bearing entries in `progress.md`.

Read [workflow.md](references/workflow.md) for milestone cadence, long unattended runs, and custody handoffs. Read [state-model.md](references/state-model.md) when reconciling ambiguous states. Read [recovery.md](references/recovery.md) after abnormal termination, stale output, or lost custody.

## Recover

On resume or abnormal termination:

1. Read `goal.md` and `progress.md` before taking new action.
2. Inspect repository state, goal-tool state, running work, outputs, and evidence paths.
3. Reconcile each custody row. Do not report "nothing ran" merely because the root execution stopped.
4. Mark execution health honestly and preserve completed outputs before restarting work.
5. Refresh the recovery capsule with last verified truth, current layer, resume point, unsafe assumptions, and canonical files.
6. Render and validate before resuming implementation.

## Close

Close only when every required success criterion is evidenced, all blocking gates are resolved, every required custody item is complete, and verification contains no pending, failed, or blocked required check. A skipped phase or verification row is resolved only when its exact label is authorized in the matching `allowed_skipped_*` goal-frontmatter field.

Before closing:

1. resolve every **Closeout options** row to explicit `yes` or `no`;
2. generate each selected prompt and verify it with `generate_closeout_prompts.py --check`;
3. if additional Codex review is `yes`, follow `$codex-review`: treat findings as advisory, verify each against the real code, fix only accepted findings, rerun affected checks and review after edits, and never push unless the user requested it;
4. update both Markdown frontmatters to `status: complete`;
5. record the actual final repository/commit state without implying an unmade commit;
6. render and validate the final dashboard, then reload it in Codex preview;
7. mark the goal-state tool complete only after the repository contract is truly satisfied.

If a concrete condition prevents meaningful work, the repository ledger may use `status: blocked` immediately and name the smallest unblocking action. Update an external goal-state tool to blocked only when that tool's own threshold is met; do not conflate the two state machines.

## Commands

Resolve these paths relative to this skill directory.

Installing or replacing a global skill is an external write. Run the installer only after the user authorizes that destination. It defaults to `$CODEX_HOME/skills/codex-goal-ledger`, or `~/.codex/skills/codex-goal-ledger` when `CODEX_HOME` is unset, refuses drift by default, and preserves the previous directory when `--replace` is explicit.

```bash
python3 scripts/install_skill.py
python3 scripts/install_skill.py --check

python3 scripts/init_goal.py \
  --project-root . \
  --slug overnight-build \
  --title "Overnight build" \
  --why "Why this matters" \
  --outcome "Observable end state" \
  --planning-profile "gpt-5.6-sol xhigh" \
  --implementation-profile "gpt-5.6-terra max" \
  --review-profile "gpt-5.6-sol xhigh" \
  --external-review-prompt yes \
  --codex-review yes \
  --clean-session-handoff yes

python3 scripts/render_goal.py docs/goals/overnight-build
python3 scripts/generate_closeout_prompts.py docs/goals/overnight-build
python3 scripts/validate_goal.py docs/goals/overnight-build
python3 scripts/test_goal_ledger.py
python3 scripts/test_install_skill.py
```

Use `render_goal.py --sync-assets` after upgrading this skill's shipped CSS or JavaScript. Use `render_goal.py --check` and `generate_closeout_prompts.py --check` in validation lanes to detect stale generated artifacts without modifying files. Paths in examples are repository-relative or supplied at runtime; do not embed local application or dependency paths.

## References

- [workflow.md](references/workflow.md): full start, operate, recover, and close protocol.
- [closeout-kit.md](references/closeout-kit.md): planning choices, external-review prompt, Codex review, and clean-session handoff contract.
- [state-model.md](references/state-model.md): allowed states, invariants, and reconciliation rules.
- [recovery.md](references/recovery.md): failure-mode playbook and evidence-preserving recovery order.
- [model-execution-profile.md](references/model-execution-profile.md): requested/effective model routing and fallbacks.
- [prompting-gpt-5p6.md](references/prompting-gpt-5p6.md): lean prompt contract used by this skill.
- [progress-template.md](references/progress-template.md): Markdown schema and section contract.
- [latest-model-baseline.md](references/latest-model-baseline.md): dated capability snapshot; verify drift-prone claims.

# Progress ledger contract

The canonical templates are shipped in `assets/templates/goal.md` and `assets/templates/progress.md`. Initialize them with `scripts/init_goal.py`; do not copy this reference as a second source of truth.

## Required goal frontmatter

- `ledger_version`
- `title`
- `slug`
- `status`
- `created`
- `updated`
- `mode`
- `allowed_skipped_phases`
- `allowed_skipped_verifications`

Set each skip field to `none` by default. When the goal contract deliberately permits an omission, list the exact Phase tracker or Verification item labels separated by semicolons. A `skipped` row that is not named by its matching field is invalid.

Required sections: Why, Outcome, Success criteria, Scope, Non-goals, Execution profile, Closeout options, Authorization, and Completion contract.

Ask for the three closeout choices in one bundled planning round and record each choice as exactly `ask`, `yes`, or `no`. `ask` is an unresolved planning state and prevents completion.

Closeout options:

```text
Option | Choice | Artifact or action
External LLM review prompt | ask, yes, or no | Generate review-prompt.md for Claude or another independent LLM.
Additional Codex review | ask, yes, or no | Run the optional $codex-review closeout contract and record its evidence.
Clean-session handoff prompt | ask, yes, or no | Generate handoff-prompt.md for a new GPT session.
```

The row labels and order are canonical. `scripts/generate_closeout_prompts.py` creates the selected prompt files beside `goal.md`; its `--check` mode verifies exact content and the absence of unselected managed artifacts. If an option changes to `no`, synchronization reports the existing artifact but never deletes it automatically; preserve, move, or remove it only within the user's authority.

## Required progress frontmatter

- `ledger_version`
- `goal_slug`
- `status`
- `execution_health`
- `updated`

Required sections: At a glance, Phase tracker, Current focus, Work log, Decision log, Verification, Custody, Open gates, Recovery capsule, and Next action.

## Compactness rule

`At a glance`, `Current focus`, `Open gates`, `Recovery capsule`, and `Next action` are the live handoff surface. Keep them current and short. Archive old work-log detail under `evidence/` rather than allowing the operational ledger to become a transcript.

## Table schemas

Phase tracker:

```text
Phase | State | Evidence | Next gate
```

Decision log:

```text
Decision | Why | Status
```

Verification:

```text
Check | Result | Evidence
```

Custody:

```text
Work item | Owner | State | Recovery action
```

The renderer matches columns by position. Keep these column orders even when labels are localized.

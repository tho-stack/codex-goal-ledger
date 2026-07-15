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
- `fable_review_rounds` (1-10; defaults to 1 for legacy ledgers)
- `pro_review_rounds` (1-3), `pro_review_stage`, `pro_review_delivery`, and `pro_review_gate` for ledger v6-v7; v7 defaults delivery to `auto-ui`
- `allowed_skipped_phases`
- `allowed_skipped_verifications`

Set each skip field to `none` by default. When the goal contract deliberately permits an omission, list the exact Phase tracker or Verification item labels separated by semicolons. A `skipped` row that is not named by its matching field is invalid.

Ledger v4-v7 required sections: Why, Outcome, Success criteria, Scope, Non-goals, Planning input assessment, Execution profile, Closeout options, Authorization, and Completion contract. Validators continue to accept the legacy v2 and v3 section contract.

Ledger v4 Execution profile:

```text
Layer | Requested profile | Invoked profile | Effective profile | Evidence
Planning and architecture | ... | ... | ... | ...
Implementation | ... | ... | ... | ...
Claude Fable planning peer | ... | ... | ... | ...
Final adversarial review | ... | ... | ... | ...
```

Do not populate Effective profile from configuration or intent. Record `unconfirmed` until runtime evidence exists.

Ask for the six independent review, rescue, and handoff choices plus their selectors in the first planning checkpoint. Prefer consecutive structured-input controls of at most three questions each. Record each choice as exactly `ask`, `yes`, or `no`; `ask` is an unresolved planning state and prevents completion.

Closeout options:

```text
Option | Choice | Artifact or action
Claude Fable peer feedback | ask, yes, or no | Run configured critique and feature/science proposal rounds; save one evidence artifact per round.
Claude Fable scientific rescue | ask, yes, or no | Arm bounded scientific rescue under its incident contract.
GPT Pro review | ask, yes, or no | Run native prompt-plus-ZIP Pro review with full response custody and reconciliation.
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

The v4 progress template includes an `HTTP dashboard preview` Verification row. Resolve it with the served URL, health-check evidence, verified page DOM, and visible same-task in-app Browser deliverable. Never replace it with a direct local-file, external-browser, or hidden-tab claim.

The v7 dashboard derives its review circuit and separate run, evidence, reviews, and gates tracks from canonical review artifacts and these tables. Do not write dashboard-only progress percentages or graph states.

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

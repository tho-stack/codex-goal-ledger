---
ledger_version: 2
title: {{TITLE_YAML}}
slug: {{SLUG}}
status: active
created: {{DATE}}
updated: {{DATE}}
mode: {{MODE_YAML}}
allowed_skipped_phases: none
allowed_skipped_verifications: none
---

# {{TITLE_MD}}

## Why

{{WHY}}

## Outcome

{{OUTCOME}}

## Success criteria

{{SUCCESS_CRITERIA}}

## Scope

- Deliver the stated outcome inside the authorized repository or workspace.
- Keep goal, progress, evidence, and generated dashboard synchronized.
- Validate changed behavior in proportion to risk.

## Non-goals

- External writes, destructive actions, purchases, or material scope expansion without confirmation.
- Claims of completion without direct evidence.
- Claims of model or reasoning selection the runtime did not confirm.

## Execution profile

| Layer | Requested profile | Effective profile | Rule |
| --- | --- | --- | --- |
| Planning and architecture | {{PLANNING_PROFILE}} | unconfirmed | Preserve the request and record the actual runtime. |
| Implementation | {{IMPLEMENTATION_PROFILE}} | unconfirmed | Do not infer a model switch from intent. |
| Final adversarial review | {{REVIEW_PROFILE}} | unconfirmed | Reserve Max for the hardest quality-first pass. |

## Closeout options

| Option | Choice | Artifact or action |
| --- | --- | --- |
| External LLM review prompt | {{EXTERNAL_REVIEW_PROMPT}} | Generate `review-prompt.md` for Claude or another independent LLM. |
| Additional Codex review | {{CODEX_REVIEW}} | Run the optional `$codex-review` closeout contract and record its evidence. |
| Clean-session handoff prompt | {{CLEAN_SESSION_HANDOFF}} | Generate `handoff-prompt.md` for a new GPT session. |

## Authorization

In-scope local reads, edits, and non-destructive validation may proceed without another prompt. Ask before external writes, destructive actions, purchases, global installation, or material scope expansion.

## Completion contract

Completion requires every success criterion to have direct evidence, no open blocking gate, no unresolved required custody, no unresolved `ask` choice, synchronized selected closeout prompts, synchronized Markdown and generated HTML, and an exact final repository or commit-state statement.

---
ledger_version: 7
title: {{TITLE_YAML}}
slug: {{SLUG}}
status: active
created: {{DATE}}
updated: {{DATE}}
mode: {{MODE_YAML}}
fable_review_rounds: {{FABLE_REVIEW_ROUNDS}}
fable_rescue_max_incidents: {{FABLE_RESCUE_MAX_INCIDENTS}}
fable_rescue_rounds_per_incident: {{FABLE_RESCUE_ROUNDS}}
fable_rescue_effort: {{FABLE_RESCUE_EFFORT}}
fable_rescue_lineage: {{FABLE_RESCUE_LINEAGE}}
pro_review_rounds: {{PRO_REVIEW_ROUNDS}}
pro_review_stage: {{PRO_REVIEW_STAGE}}
pro_review_delivery: {{PRO_REVIEW_DELIVERY}}
pro_review_gate: {{PRO_REVIEW_GATE}}
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

## Planning input assessment

{{PLANNING_INPUT_ASSESSMENT}}

## Execution profile

| Layer | Requested profile | Invoked profile | Effective profile | Evidence |
| --- | --- | --- | --- | --- |
| Planning and architecture | {{PLANNING_PROFILE}} | current root task | unconfirmed | Record runtime metadata or keep the effective profile unconfirmed. |
| Implementation | {{IMPLEMENTATION_PROFILE}} | not-invoked | unconfirmed | Primary owned role: `{{IMPLEMENTATION_AGENT}}`. Optional mixed-swarm roles: {{IMPLEMENTATION_SWARM}}. Confirm every invoked worker before claiming its model and effort. |
| Claude Fable planning peer | {{FABLE_PROFILE}} | not-invoked | unconfirmed | Run only when selected; preserve requested, invoked, and effective model plus effort. |
| Final adversarial review | {{REVIEW_PROFILE}} | not-invoked | unconfirmed | Prefer `goal-ledger-reviewer`; record independent review evidence. |

## Closeout options

| Option | Choice | Artifact or action |
| --- | --- | --- |
| Claude Fable peer feedback | {{FABLE_FEEDBACK}} | `yes` selects {{FABLE_AUTHORIZATION}} for critique plus feature and science proposals; prepare one exact hashed file manifest, request native Codex transmission approval, and save one evidence artifact per round. |
| Claude Fable scientific rescue | {{FABLE_RESCUE}} | `yes` authorizes bounded, automatic scientific rescue within the approved allow-list after a structured trigger qualifies; rescue remains advisory and cannot be completion evidence. |
| GPT Pro review | {{PRO_REVIEW}} | `yes` selects {{PRO_REVIEW_AUTHORIZATION}} with a deterministic prompt plus scoped ZIP, platform-aware Safari/Chrome/ChatGPT routing or owner handoff, full raw-response custody, and typed reconciliation. |
| External LLM review prompt | {{EXTERNAL_REVIEW_PROMPT}} | Generate `review-prompt.md` for Claude or another independent LLM. |
| Additional Codex review | {{CODEX_REVIEW}} | Run the optional `$codex-review` closeout contract and record its evidence. |
| Clean-session handoff prompt | {{CLEAN_SESSION_HANDOFF}} | Generate `handoff-prompt.md` for a new GPT session. |

## Authorization

In-scope local reads, edits, and non-destructive validation may proceed without another prompt. A recorded Claude Fable choice of `yes` selects the configured read-only planning-review rounds without another conversational consent sentence. A recorded scientific-rescue choice of `yes` authorizes automatic rescue submissions only within the goal's approved repository scope and exact manifest; ask again only when the transmission or goal scope expands. A recorded GPT Pro choice of `yes` authorizes uploading only the exact generated `request.md` and hashed `context-packet.zip` to ChatGPT GPT Pro through the selected delivery lane; changed or additional files require a fresh packet and expanded scope requires confirmation. Before each external call, automatically submit its exact manifest-bound invocation to the applicable native approval layer. Ask before other external transmissions or writes, destructive actions, purchases, global installation, or material scope expansion.

## Completion contract

Completion requires every success criterion to have direct evidence, no open blocking gate, no unresolved required custody, no unresolved `ask` choice, required selected review evidence, honest requested/invoked/effective profile evidence, synchronized selected closeout prompts, synchronized Markdown and generated HTML, a health-checked HTTP dashboard presented as a visible same-task in-app Browser deliverable or an honestly blocked browser-QA gate, and an exact final repository or commit-state statement.

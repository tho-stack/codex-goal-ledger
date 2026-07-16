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
| Claude Fable peer feedback | {{FABLE_FEEDBACK}} | `yes` authorizes preparing {{FABLE_AUTHORIZATION}} through Anthropic Claude for critique plus feature and science proposals; every exact hashed manifest still requires native owner approval before transmission. |
| Claude Fable scientific rescue | {{FABLE_RESCUE}} | `yes` authorizes preparing bounded scientific rescue through Anthropic Claude within the approved allow-list after a structured trigger qualifies; every exact manifest still requires native owner approval, and rescue cannot be completion evidence. |
| GPT Pro review | {{PRO_REVIEW}} | `yes` selects {{PRO_REVIEW_AUTHORIZATION}} with a deterministic prompt plus scoped ZIP, the bundled restricted MCP App when configured, Safari/Chrome or owner fallback, one exact-packet submission, full raw-response custody, and typed reconciliation. |
| External LLM review prompt | {{EXTERNAL_REVIEW_PROMPT}} | Generate `review-prompt.md` for Claude or another independent LLM. |
| Additional Codex review | {{CODEX_REVIEW}} | Run the optional `$codex-review` closeout contract and record its evidence. |
| Clean-session handoff prompt | {{CLEAN_SESSION_HANDOFF}} | Generate `handoff-prompt.md` for a new GPT session. |

## Authorization

Starting this goal accepts this entire contract as one standing execution envelope across phases, retries, recovery, compaction, and new tasks. All non-destructive actions reasonably necessary to deliver the recorded Outcome inside Scope are authorized without another conversational prompt, including repository and browser work, web and literature research, hardware and component research, downloads, goal-scoped dependency setup, implementation, delegation, bounded compute, tests, benchmarks, qualification campaigns, frozen retries, and configured review lanes. A new manifest or digest, a fixed resource budget, a failed attempt, a contract revision, a resumed task, or an in-scope replacement run is custody evidence—not a new permission boundary. Never add a later typed-sentence, checkbox, or owner-authorization gate for that work. Before unattended execution, preflight the whole envelope and obtain unavoidable platform-native security approvals while the owner is present, using safely scoped reusable approvals when supported. Purchases, public publishing or messages, destructive actions, secret disclosure, unsafe physical operations, and material scope expansion remain outside the default envelope unless positively included and bounded in Scope or this Authorization section.

A recorded Claude Fable `yes` is lane authorization to prepare the configured reviews for Anthropic Claude through the owner's account; it is not a claim that any exact packet has been transmitted or approved. After the manifest discloses paths, hashes, bytes, destination, and risk, obtain exact transmission approval through Codex's native action-time checkbox—never through an agent-authored allow-list or a required typed sentence. Scientific rescue uses the same two-layer rule within its approved repository scope. A recorded GPT Pro choice of `yes` authorizes sending only the exact generated request and hashed ZIP to ChatGPT GPT Pro through the selected delivery lane. The restricted MCP App may expose only manifest-listed ZIP members and response custody; browser fallback may upload the request and ZIP. Changed or additional files require a fresh packet and expanded scope requires confirmation.

## Completion contract

Completion requires every success criterion to have direct evidence, no open blocking gate, no unresolved required custody, no unresolved `ask` choice, required selected review evidence, honest requested/invoked/effective profile evidence, synchronized selected closeout prompts, synchronized Markdown and generated HTML, a health-checked HTTP dashboard presented as a visible same-task in-app Browser deliverable or an honestly blocked browser-QA gate, and an exact final repository or commit-state statement.

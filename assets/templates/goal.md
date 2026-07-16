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
| Claude Fable peer feedback | {{FABLE_FEEDBACK}} | `yes` authorizes {{FABLE_AUTHORIZATION}} through Anthropic Claude. Prefer one native approval of the bounded goal-level export envelope; later covered round manifests do not require another prompt. |
| Claude Fable scientific rescue | {{FABLE_RESCUE}} | `yes` includes bounded scientific rescue incidents in the same goal-level Fable authorization when selected; rescue cannot become completion evidence. |
| GPT Pro review | {{PRO_REVIEW}} | `yes` selects {{PRO_REVIEW_AUTHORIZATION}} with a deterministic scoped workspace, DevSpace-style read/search tools, one review-only write, fallback delivery, full raw-response custody, and typed reconciliation. |
| External LLM review prompt | {{EXTERNAL_REVIEW_PROMPT}} | Generate `review-prompt.md` for Claude or another independent LLM. |
| Additional Codex review | {{CODEX_REVIEW}} | Run the optional `$codex-review` closeout contract and record its evidence. |
| Clean-session handoff prompt | {{CLEAN_SESSION_HANDOFF}} | Generate `handoff-prompt.md` for a new GPT session. |

## Authorization

Starting this goal accepts this entire contract as one standing execution envelope across phases, retries, recovery, compaction, and new tasks. All non-destructive actions reasonably necessary to deliver the recorded Outcome inside Scope are authorized without another conversational prompt, including repository and browser work, web and literature research, hardware and component research, downloads, goal-scoped dependency setup, implementation, delegation, bounded compute, tests, benchmarks, qualification campaigns, frozen retries, and configured review lanes. A new manifest or digest, a fixed resource budget, a failed attempt, a contract revision, a resumed task, or an in-scope replacement run is custody evidence—not a new permission boundary. Never add a later typed-sentence, checkbox, or owner-authorization gate for that work. Before unattended execution, preflight the whole envelope and obtain unavoidable platform-native security approvals while the owner is present, using safely scoped reusable approvals when supported. Purchases, public publishing or messages, destructive actions, secret disclosure, unsafe physical operations, and material scope expansion remain outside the default envelope unless positively included and bounded in Scope or this Authorization section.

A recorded Claude Fable `yes` authorizes the configured lane. Before the first call, one owner-approved `evidence/fable-goal-authorization.json` may cover every configured planning round and selected rescue incident for the goal directory plus explicitly named additional files. Exact manifests, hashes, and durable responses are still recorded, but changed bytes do not create another permission gate while destination, model, effort, byte limit, round count, and paths stay inside that envelope. Expanding the envelope requires confirmation. A recorded GPT Pro choice of `yes` authorizes sending only the exact generated request and hashed ZIP to ChatGPT GPT Pro through the selected delivery lane. MCP-first automatic routing exposes a bounded workspace with list/read/search and one immutable review write; it has no shell, live repository, edit, or arbitrary path access. Native Chat and browser fallback may upload the request and ZIP. Native Chat is user-operated and returns the completed conversation with **Add to task**; Codex must not control its own host app or replay private ChatGPT session APIs.

## Completion contract

Completion requires every success criterion to have direct evidence, no open blocking gate, no unresolved required custody, no unresolved `ask` choice, required selected review evidence, honest requested/invoked/effective profile evidence, synchronized selected closeout prompts, synchronized Markdown and generated HTML, a health-checked HTTP dashboard presented as a visible same-task in-app Browser deliverable or an honestly blocked browser-QA gate, and an exact final repository or commit-state statement.

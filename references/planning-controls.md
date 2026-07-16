# Planning controls

Use this reference for the first interactive planning checkpoint.

## Native-control rule

Prefer the already-connected bundled Goal Ledger app. Call `open_goal_ledger` in unbound planning mode immediately after bounded discovery. It renders literal checkboxes for all six choices, bounded lane and implementation selectors, a separate one-time Fable authorization checkbox, and an **Approve selected lanes** button.

When Fable planning or scientific rescue is checked, the approval button remains disabled until the owner checks **Approve the selected Fable lanes once**. The posted structured result contains:

```json
{
  "owner_approval": {
    "fable_goal_authorization": true,
    "includes_planning_rounds": true,
    "includes_scientific_rescue": true
  }
}
```

Treat that click-generated record as the owner's planning answer and authorization to create the bounded `fable-goal-authorization.json`. Do not ask for a typed approval sentence afterward. The same authorization covers both selected Fable lanes.

When the app is unavailable and `request_user_input` exists, call it immediately. The current Codex control supports clickable single-choice cards, not a literal multi-select checkbox group or range slider. Treat each independent boolean as its own Yes/No control and use a stepped model-family plus effort selector. If neither structured surface is available, use one concise Markdown checklist. Do not turn app setup into a new blocking gate.

## Required sequence

1. Present any required goal facts and up to three optional inputs.
2. Ask review choices 1-3 in one interaction:
   - Claude Fable peer feedback;
   - Claude Fable scientific rescue;
   - GPT Pro review.
3. Ask review choices 4-6 in the next interaction:
   - external LLM review prompt;
   - additional Codex review;
   - clean-session handoff prompt.
4. Immediately ask settings for every selected lane. Keep each question independent; do not encode several settings into one ambiguous label.
5. Ask the primary implementation model family:
   - Luna;
   - Terra;
   - Sol.
6. Ask the compatible owned effort preset:
   - Luna: High or Max;
   - Terra: record Ultra directly because it is the only owned Terra preset;
   - Sol: Medium, XHigh, or Ultra.
7. Map the result exactly:

| Family | Effort | Owned implementer |
| --- | --- | --- |
| Luna | High | `goal-ledger-implementer-luna-high` |
| Luna | Max | `goal-ledger-implementer` |
| Terra | Ultra | `goal-ledger-implementer-terra-ultra` |
| Sol | Medium | `goal-ledger-implementer-sol-medium` |
| Sol | XHigh | `goal-ledger-implementer-sol-xhigh` |
| Sol | Ultra | `goal-ledger-implementer-sol-ultra` |

Ask about a mixed swarm only when discovery found independently owned work. If selected, present each additional owned preset as its own Yes/No control in batches of at most three; never imply that a single-choice control is multi-select.

## GPT Pro submission choice

A selected GPT Pro `yes` must disclose that the exact generated `request.md` and hashed `context-packet.zip` will be sent to OpenAI through the selected transport. Default to MCP-first `auto-ui`: restricted `mcp-app`, user-operated native Chat/Pro plus **Add to task**, Safari/Chrome, then owner handoff. With `mcp-app`, Pro reads only manifest-listed ZIP members through the restricted bridge; native Chat and browser delivery upload the ZIP and request. That selection authorizes one submission of exactly those artifacts after readiness and native security confirmation. Native Chat is not Computer Use automation; the owner performs the host-app actions and returns the completed conversation with **Add to task**. Do not ask the user to type or click a second conversational `Press Send` approval. Ask again only if the destination changes, the goal scope expands, or the packet would include files outside its generated manifest.

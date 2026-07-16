# Planning controls

Use this reference for the first interactive planning checkpoint.

## Native-control rule

When `request_user_input` is available, call it immediately after bounded discovery. Do not render a prose questionnaire, ask the user to reply `yes/no`, or postpone the interaction until the end. Use at most three questions per call and two or three mutually exclusive options per question. Put the contextual recommendation first and suffix its label with `(Recommended)`.

The current Codex control supports clickable single-choice cards in Plan mode. It does not expose a literal multi-select checkbox group or range slider. Do not claim otherwise. Treat each independent boolean as its own Yes/No control, and use a stepped model-family plus effort selector for implementation.

When native structured input is unavailable, prefer the bundled Goal Ledger MCP App if it is already connected: run its unbound planning server and call `open_goal_ledger`. The widget renders six actual checkboxes plus bounded round, stage, delivery, gate, model-family, and effort selectors, then posts one structured user message into the conversation. Read [review-bridge.md](review-bridge.md). If the app is not connected, explicitly say native controls require Plan mode in the current task and use one concise Markdown checklist so planning can still proceed. Do not turn app setup into a new blocking gate for an otherwise answerable planning checkpoint.

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

A selected GPT Pro `yes` must disclose that the exact generated `request.md` and hashed `context-packet.zip` will be sent to OpenAI through the selected transport. With `mcp-app`, Pro reads only manifest-listed members from that ZIP through the restricted bridge; with browser delivery, the ZIP and request are uploaded. That selection authorizes one submission of exactly those artifacts after readiness and native security confirmation. Do not ask the user to type or click a second conversational `Press Send` approval. Ask again only if the destination changes, the goal scope expands, or the packet would include files outside its generated manifest.

# Native GPT Pro review

Use this reference whenever **GPT Pro review** is selected. Goal Ledger owns the whole workflow; do not invoke, read, or depend on a separate `$pro` skill.

## Contents

- [Selection contract](#selection-contract)
- [Prepare the prompt and ZIP](#prepare-the-prompt-and-zip)
- [Review directly through the Goal Ledger MCP App](#review-directly-through-the-goal-ledger-mcp-app)
- [Route and submit through a supported UI](#route-and-submit-through-a-supported-ui)
- [Capture the complete response](#capture-the-complete-response)
- [Reconcile](#reconcile)
- [Gate and round behavior](#gate-and-round-behavior)
- [Recovery](#recovery)
- [Validation](#validation)

## Selection contract

Record these values in `goal.md` during the first planning checkpoint:

- choice: `ask`, `yes`, or `no`;
- stage: `plan`, `implementation`, or `both`;
- rounds: 1-3 for every selected stage;
- delivery: `mcp-app`, `auto-ui`, `safari-assisted`, `chrome-assisted`, or `owner-handoff`;
- gate: `required` or `advisory`.

Recommend one required plan round through `mcp-app` when the restricted Goal Ledger app and Secure MCP Tunnel pass preflight; otherwise use `auto-ui`. Recommend `both` only when implementation evidence will materially change the decision. More than one round is useful when a blocked review will be revised and checked again.

A `yes` records specific pre-approval to upload only the generated `request.md` and exact hashed `context-packet.zip` to ChatGPT GPT Pro. The user must see that scope in the planning choice. Do not ask for a ceremonial consent sentence later. Ask again only when the destination changes, the goal scope expands, or files outside the generated manifest would be transmitted.

## Prepare the prompt and ZIP

After the relevant plan or implementation evidence is stable, prepare a round:

```bash
python3 scripts/run_pro_review.py prepare docs/goals/<goal-slug> \
  --stage plan \
  --round 1 \
  --decision "Approve this plan for implementation." \
  --review-question "Which blocking assumptions or missing tests remain?" \
  --context-file path/to/operative-plan.md \
  --context-reason "path/to/operative-plan.md=Operative plan under review."
```

The runner always includes `goal.md` and `progress.md`. Add only decision-relevant files with repository-relative `--context-file` arguments. Each optional `--context-reason` uses `PATH=REASON`. Do not include the whole repository.

The runner rejects files outside the project, symlinks, likely secret paths, dependency trees, VCS internals, oversized files, and its own Pro evidence tree. Inspect the generated manifest before transmission. Human judgment remains required for secrets or private data that filenames cannot reveal.

Each immutable round lives at:

```text
evidence/pro-review/<stage>/round-NNN/
├── request.md
├── context-packet.zip
├── packet-manifest.json
├── packet-manifest.md
├── delivery-plan.json
├── transport-attempts.json # after the first assisted probe
├── packet-read-receipts/   # one hash-bound receipt per MCP member read
├── manual-handoff.md       # owner delivery or exhausted assisted route
└── state.json
```

The ZIP uses stable member ordering, fixed timestamps, normalized permissions, and exact SHA-256 custody. It contains:

- `START-HERE.md`, byte-identical to `request.md`;
- `packet-index.json` with source paths, byte counts, hashes, and inclusion reasons;
- `repo-state.txt` with bounded git identity and status evidence;
- `context/<repo-relative-path>` for every allow-listed source.

The prompt follows [prompting-gpt-5p6.md](prompting-gpt-5p6.md): role, decision, observable success criteria, constraints, evidence received, review questions, output shape, and stop rules. It does not repeat generic process narration or imply access to local paths.

Never edit or replace a prepared round after submission. If evidence or the decision changes, increment the round and create a new packet.

## Review directly through the Goal Ledger MCP App

`mcp-app` uses the server and widget shipped inside this skill. It is not DevSpace, a separate plugin dependency, or the external `$pro` skill. Read and follow [review-bridge.md](review-bridge.md).

The app reads only the prepared ZIP and verifies its complete manifest before every member read. It exposes no shell, generic read/write/edit tool, live repository access, or arbitrary output path. Its only write is the normal immutable Pro response and custody metadata for the bound round.

Preflight and print the exact stdio command:

```bash
python3 scripts/run_review_bridge.py check \
  --goal-dir docs/goals/<goal-slug> --stage plan --round 1 \
  --require-tunnel-client

python3 scripts/run_review_bridge.py print-command \
  --goal-dir docs/goals/<goal-slug> --stage plan --round 1
```

Run that command through the configured OpenAI Secure MCP Tunnel profile. In a visibly selected GPT Pro or Pro Extended conversation, enable the `Codex Goal Ledger` developer app and call `open_goal_ledger`. The widget records the `mcp-app` ready attempt and submission only after the user confirms the visible Pro label and presses **Begin exact-packet review**. **Ask Pro to review now** posts the packet-reading and response-submission instruction into the same conversation.

GPT Pro must read every listed member, follow `START-HERE.md`, and call `submit_pro_review_response` with its complete answer. Each MCP read writes a deterministic receipt bound to the packet hash, member path, and member hash. The bridge refuses the response until every declared member has a valid receipt. It stores the same `submission.json`, `response.md`, response metadata, state, and later reconciliation used by browser delivery. Stop the round-bound tunnel after the response is stored.

If the bridge is unavailable before submission, record the failed `mcp-app` attempt and use another authorized transport. If `submission.json` already exists, restart only the identical manifest-bound bridge and never submit through another transport.

## Route and submit through a supported UI

Use this browser lane when delivery is `auto-ui`, `safari-assisted`, or `chrome-assisted`, or when an authorized MCP attempt failed before submission. Use the installed Computer Use capability directly. Read its current skill instructions, initialize its supported UI runtime, and operate the selected surface through accessibility state, clicks, typing, screenshots, and fresh state reads. Do not substitute the in-app Browser, Playwright, shell-launched browser automation, `open`, AppleScript, or machine-specific executable paths. The built-in Browser is not eligible for this fallback because its documented Computer Use surface cannot automate file uploads.

`auto-ui` uses this order:

- macOS: Safari, Chrome, then owner handoff;
- Windows and Linux: Chrome, then owner handoff.

Do not probe or control the ChatGPT desktop/classic app. Computer Use cannot inspect or operate its own host app under the desktop security boundary, so it is not an assisted transport. An explicit browser or owner-handoff selection wins over automatic browser routing. A browser surface is ready only when Computer Use can inspect it, ChatGPT is authenticated, GPT Pro or Pro Extended is visibly selectable, and file upload plus text input are available. After every assisted probe, record `unavailable`, `not-authenticated`, `pro-unavailable`, `ready`, or `failed`:

```bash
python3 scripts/run_pro_review.py record-attempt docs/goals/<goal-slug> \
  --stage plan --round 1 \
  --surface safari-assisted \
  --result ready \
  --detail "Authenticated Pro Extended mode, upload, and text input are visible."
```

The runner enforces candidate order, refuses duplicate probes, stores the observed detail, and moves a ready round to `ui-ready`. When every assisted candidate fails, it generates `manual-handoff.md` and moves the round to `manual-handoff-ready`; that is a resumable owner action, not immediate proof that the goal is blocked.

1. Open or focus the selected surface through Computer Use.
2. Reuse the relevant ChatGPT thread when its context remains clean; otherwise start a new thread.
3. Verify the visible model picker identifies GPT Pro or Pro Extended. Record the exact visible label. If Pro is unavailable, stop and record the specific blocker.
4. Attach exactly `context-packet.zip` and paste exactly `request.md`.
5. The recorded planning `yes` authorizes automatic upload and submission of the exact generated request and ZIP to ChatGPT Pro. Do not stop for a second prose `Press Send` question. Follow any native Computer Use or platform confirmation that actually appears; it does not authorize added data.
6. Click Send once, verify the visible control changes to an active-generation state, capture the resulting `chatgpt.com/c/...` URL, and only then record the observed submission:

```bash
python3 scripts/run_pro_review.py record-submission docs/goals/<goal-slug> \
  --stage plan \
  --round 1 \
  --model-visible "Pro Extended" \
  --transport safari-assisted \
  --thread "Goal title planning review"
```

Do not record submission before the visible send completes. If the prompt was sent on another model, do not use that answer; switch to Pro and send the same self-contained packet once. Do not resubmit merely because the outer Codex turn or UI polling was interrupted.

For `owner-handoff` or `manual-handoff-ready`, give the owner the generated `manual-handoff.md`, exact `request.md`, and ZIP, then wait for the response. After the owner confirms the actual Pro submission, record it with `--transport owner-handoff`. Owner handoff is a transport fallback, not a prompt-only downgrade.

## Capture the complete response

GPT Pro may take 10-15 minutes. Poll the existing thread patiently with fresh UI state. An unchanged screen is waiting, not failure.

Capture the complete response, including every required change, risk, test, reasoning note, link, and footer that belongs to the answer. Do not preserve only a summary or the first visible screen. Use UI text extraction when complete; otherwise scroll and copy the full answer in ordered chunks into one UTF-8 file without paraphrasing. Verify the first line and final lines after assembly.

Record the raw response:

```bash
python3 scripts/run_pro_review.py record-response docs/goals/<goal-slug> \
  --stage plan \
  --round 1 \
  --response-file /path/to/full-pro-response.md
```

The response must begin with `Verdict: SIGNED OFF` or `Verdict: BLOCKED`, then contain exactly one non-empty `Required changes`, `Risks`, `Tests or verification`, and `Reasoning notes` section in that order. The runner copies the exact bytes to `response.md`, records byte count and SHA-256 in `response-metadata.json`, and changes `state.json` to `response-received`.

## Reconcile

Verify every Pro claim against current repository files, tests, live state, and goal constraints. Do not implement feedback blindly. Create a reconciliation JSON:

```json
{
  "pro_verdict": "BLOCKED",
  "items": [
    {
      "classification": "FIX",
      "finding": "Short finding",
      "disposition": "Exact accepted change or reasoned response",
      "evidence": ["repo-relative/path:line or command result"]
    }
  ],
  "local_verification": ["Command or inspection and result"],
  "next_action": "Smallest safe next action"
}
```

Classify every actionable item as:

- `FIX`: verified, in scope, and accepted;
- `DEFER`: valid but outside the active scope or better handled later;
- `DISMISS`: contradicted or already satisfied by named evidence;
- `QUESTION`: requires an owner decision before proceeding.

Record it:

```bash
python3 scripts/run_pro_review.py reconcile docs/goals/<goal-slug> \
  --stage plan \
  --round 1 \
  --reconciliation-file reconciliation.json
```

The runner binds reconciliation to the full raw-response hash and generates `reconciliation.md`. A `BLOCKED` response must retain at least one `FIX` or `QUESTION`; do not reconcile a blocking verdict into silent approval.

## Gate and round behavior

For a required plan review, Build may not become `active` or `complete` until the latest configured plan round is reconciled and `SIGNED OFF`. For a required implementation review, completion requires signed-off reconciliation. An advisory review still requires full capture and reconciliation but does not convert the external verdict into an execution gate.

Run sequential rounds only. Reconcile round N, update the reviewed artifacts, then prepare round N+1. Never run multiple Pro rounds against an unreconciled packet. Preserve every earlier packet and response as historical evidence.

If Pro returns `BLOCKED`, apply only verified, authorized `FIX` items. Resolve `QUESTION` items with the user. Rerun affected local checks, update the ledger, and prepare the next configured round. Do not infer sign-off from a locally fixed plan; only a later recorded Pro response can sign off a required gate.

## Recovery

Read the round's `state.json` before acting:

- `packet-ready`: start the selected bridge or probe the selected browser lane once;
- `ui-ready`: the recorded MCP App or browser surface is ready; submit the prepared packet once;
- `manual-handoff-ready`: give the owner `manual-handoff.md`, the request, and the exact ZIP without marking the goal blocked merely for awaiting that action;
- `submitted-waiting-response`: reopen and poll the existing thread; never send again;
- `response-received`: reconcile the stored full response;
- `reconciled-signed-off`: advance the configured gate;
- `reconciled-blocked`: follow the recorded next action and prepare a new round only after changes.

If Codex stops after submission, the UI thread and `submission.json` retain custody. If the answer exists but capture was interrupted, resume capture from the same response and compare the assembled start/end before recording. If local artifacts and the visible thread disagree, preserve both facts and stop at the contradiction.

Do not mark the goal blocked merely because Pro is still thinking or a manual handoff is ready. Mark a repository blocker only when every authorized transport is unusable, the owner cannot complete the handoff, a response is unavailable, or a required Pro finding actually prevents meaningful progress. External goal-state tools keep their own repeated-blocker threshold.

## Validation

Run:

```bash
python3 scripts/run_pro_review.py check docs/goals/<goal-slug>
python3 scripts/run_pro_review.py check docs/goals/<goal-slug> --require-closed
python3 scripts/validate_goal.py docs/goals/<goal-slug>
```

`--require-closed` verifies every selected stage and round, packet/member hashes, model evidence, full raw response, response metadata, reconciliation hash binding, and required sign-off. Before closing a selected Pro lane, add a passing `GPT Pro review` Verification row that names the review evidence paths and local reconciliation checks.

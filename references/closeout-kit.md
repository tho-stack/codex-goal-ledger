# Closeout kit

Use this reference when planning or executing the optional Fable planning-feedback, Fable scientific-rescue, native GPT Pro review, independent-review, Codex-review, and clean-session handoff lanes.

## Ask once during planning, before execution

Bundle the six independent choices into one planning checkpoint. Show a recommendation for the actual task, then require an explicit `yes` or `no` for each:

| Option | Recommend `yes` when | Result |
| --- | --- | --- |
| Claude Fable peer feedback | The goal or plan is difficult, ambiguous, high-risk, or benefits from critique plus feature and science ideation by another model. | `yes` plus a 1-10 round count selects that sequence; every round uses one exact hashed file manifest and native Codex approval, with one evidence artifact per reconciled round. |
| Claude Fable scientific rescue | The goal contains hard scientific questions where qualified impasses may benefit from an independent diagnosis and discriminating experiment. | `yes` authorizes up to two lineage-scoped rescue incidents by default, each with exact manifests, durable raw capture, prediction locking, reconciliation, and outcome evidence. |
| GPT Pro review | The plan or implementation is difficult, ambiguous, scientific, high-risk, or needs a high-context independent gate. | `yes` selects native prompt-plus-ZIP preparation, platform-aware Safari/Chrome/ChatGPT routing or owner handoff, full response custody, typed reconciliation, and configured stage/gate behavior without a separate skill. |
| External LLM review prompt | The work is non-trivial, high-risk, or benefits from an independent model. | Generate `review-prompt.md` for Claude or another LLM. |
| Additional Codex review | Code changed and a second closeout review is proportionate. | Run the installed `$codex-review` workflow. |
| Clean-session handoff prompt | The work is overnight, interruption-prone, or likely to cross sessions. | Generate `handoff-prompt.md` for a new clean GPT or Codex session. |

Ask immediately after the bounded discovery needed to make those recommendations. Present independent checkboxes or yes/no toggles plus Fable and Pro selectors. Prefer consecutive structured-input interactions of at most three questions each so every choice uses app controls in the same checkpoint; use one concise Markdown checklist only when structured input is unavailable. Do not begin implementation, delegation, long-running commands, or unattended execution before the answers arrive, and never move this checkpoint to the final closeout response.

Record the answers in the exact `## Closeout options` table and the Fable and GPT Pro selectors in frontmatter. `ask` means the skill is waiting at the planning checkpoint; it is not a default recommendation or permission to proceed. A Fable choice of `yes` selects that lane within the recorded scope; never ask for a second conversational approval. A GPT Pro `yes` pre-approves only the exact generated request and packet for ChatGPT Pro; expanded data or destination requires confirmation. Do not close a goal while any choice remains `ask`.

Schedule every selected lane before unattended work starts. Generate selected prompt artifacts once the goal contract is stable. When additional Codex review is `yes`, run it after implementation verification without waiting for the user to return, then reconcile findings and rerun affected checks before closeout.

## Generate and check prompt artifacts

The selected prompt artifacts live beside the canonical Markdown:

```text
docs/goals/<goal-slug>/
├── goal.md
├── progress.md
├── index.html
├── review-prompt.md     # external review = yes
├── handoff-prompt.md    # clean-session handoff = yes
└── evidence/
    ├── fable-feedback.md # Fable round 1
    ├── fable-feedback-round-N.md # configured rounds 2-10
    ├── fable-transport/ # durable planning-call output
    ├── fable-rescue/rescue-NNN/ # candidate, response, reconciliation, outcome, transport
    └── pro-review/<stage>/round-NNN/ # prompt, ZIP, manifest, submission, response, reconciliation
```

From the skill directory, synchronize them with:

```bash
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug>
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug> --check
```

Generation is deterministic and repository-relative. The generator creates or refreshes selected artifacts but never deletes an existing prompt. The check compares exact bytes for selected artifacts and rejects a managed prompt that remains after its option changes to `no`. Preserve, rename, or remove that now-unselected artifact deliberately within the active authority boundary, then recheck. Do not hand-edit generated prompt files; change the shipped template or canonical goal choice and regenerate.

## Claude Fable peer feedback

When selected, prepare the next configured round automatically after planning and before implementation. The runner first emits an exact allow-list manifest without contacting Claude. Submit the matching digest-bound command through Codex's native external-transmission approval rather than asking for a prose reply. Claude receives only embedded approved files, has no local repository tools, and returns critique, feature opportunities, and science/research hypotheses. Reconcile findings and proposal decisions, then validate the updated ledger before preparing the next round. Run the approved direct `claude -p` command outside the sandbox; a sandboxed logged-out result is not a valid authentication diagnosis. Use tmux only as an authenticated fallback for the same approved command, never as an approval bypass. Use High effort by default, XHigh only for difficult or high-risk planning, and never select Max automatically. Results are advisory; adjacent and future proposals do not expand the active goal without user authorization. See [fable-peer.md](fable-peer.md).

## Claude Fable scientific rescue

When selected, arm the rescue lane but invoke it only after `run_fable_rescue.py` accepts a structured scientific incident candidate. Operational blockers never qualify. The response must commit to diagnoses, one highest-information experiment, and expected outcomes before results exist. Record typed reconciliation and a hash-linked outcome before another incident. The default cap is two incidents across the goal lineage. Rescue output is advisory and cannot appear in completion evidence. Always use the durable runner; if an outer wrapper loses stdout, recover the matching transport instead of sending the prompt again. See [fable-rescue.md](fable-rescue.md).

## Native GPT Pro review

When selected, use Goal Ledger's own [pro-review.md](pro-review.md) and `scripts/run_pro_review.py`; never invoke or depend on a separate `$pro` skill. Prepare one GPT-5.6-shaped request plus a deterministic, explicitly scoped ZIP. Route exactly those artifacts through platform-aware `auto-ui`, an explicit supported surface, or owner handoff; preserve the complete raw response, verify every finding locally, and record typed reconciliation. Required plan review gates Build and required implementation review gates completion. Every round is immutable and recovery resumes from `state.json` without duplicate submission.

## External LLM review prompt

`review-prompt.md` is a read-only independent completion-review brief. It directs the reviewer to:

- read `goal.md` and `progress.md` in full;
- derive requirements and gates from the goal contract;
- inspect current implementation and direct evidence rather than trusting completion claims;
- check correctness, safety, recovery, usability, portability, verification, and repository state;
- return severity-ordered findings, repository-relative references, a requirement-to-evidence matrix, uncertainties, and one `READY` or `NOT READY` verdict.

The prompt is provider-neutral. It names no local application, executable, dependency cache, or machine-specific path.

## Additional Codex review

When **Additional Codex review** is `yes`, invoke `$codex-review` and follow its contract:

1. choose the review target that matches the real repository state;
2. treat every finding as advisory;
3. verify findings against the real code path, adjacent files, and dependency behavior when relevant;
4. accept, reject, or defer findings with evidence rather than applying them blindly;
5. after an accepted fix, rerun affected checks and rerun Codex review;
6. continue until no accepted actionable finding remains;
7. report the command, tests, accepted and rejected findings, and final review result.

Review does not authorize a push. Never push merely to run or satisfy this lane.

## Clean-session handoff prompt

`handoff-prompt.md` starts a new clean GPT or Codex session from repository truth. It directs the new session to:

- read both canonical Markdown files and inspect current repository state before acting;
- reconcile goal, execution health, custody, evidence, gates, and recovery independently;
- verify referenced evidence instead of trusting prior chat or generated output;
- resume the smallest safe next action for active work, preserve a real blocker, or audit completed work;
- respect the recorded authority boundary;
- regenerate and validate after material changes and refresh the dashboard in Codex preview when available.

The handoff is durable because it points to canonical files; it does not duplicate volatile progress claims.

## Preview behavior

After a material render, start or reuse `scripts/serve_dashboard.py`, health-check the endpoint, and open or reload the reported HTTP URL through the Browser skill in the same Codex task. Never use `file://`. Prefer Tailscale when connected and fall back to localhost. Claim or create the matching in-app tab, request and verify visibility, inspect the DOM, and retain the tab as a `deliverable`. The render and closeout scripts remain headless: never shell-open a browser, invoke an external browser executable, or hardcode an application path. Endpoint health and a hidden tab do not prove in-session delivery. If the in-app Browser or visible presentation is unavailable, report that exact limitation, retain server-health, render, and synchronization checks, and do not claim browser QA passed.

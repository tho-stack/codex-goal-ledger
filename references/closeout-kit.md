# Closeout kit

Use this reference when planning or executing the optional independent-review, Codex-review, and clean-session handoff lanes.

## Ask once during planning

Bundle the three choices into one planning question. Show a recommendation for the actual task, then require an explicit `yes` or `no` for each:

| Option | Recommend `yes` when | Result |
| --- | --- | --- |
| External LLM review prompt | The work is non-trivial, high-risk, or benefits from an independent model. | Generate `review-prompt.md` for Claude or another LLM. |
| Additional Codex review | Code changed and a second closeout review is proportionate. | Run the installed `$codex-review` workflow. |
| Clean-session handoff prompt | The work is overnight, interruption-prone, or likely to cross sessions. | Generate `handoff-prompt.md` for a new clean GPT or Codex session. |

Record the answers in the exact `## Closeout options` table in `goal.md`. `ask` means unresolved; it is not a default recommendation or permission. Do not close a goal while any choice remains `ask`.

## Generate and check prompt artifacts

The selected prompt artifacts live beside the canonical Markdown:

```text
docs/goals/<goal-slug>/
├── goal.md
├── progress.md
├── index.html
├── review-prompt.md     # external review = yes
└── handoff-prompt.md    # clean-session handoff = yes
```

From the skill directory, synchronize them with:

```bash
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug>
python3 scripts/generate_closeout_prompts.py docs/goals/<goal-slug> --check
```

Generation is deterministic and repository-relative. The generator creates or refreshes selected artifacts but never deletes an existing prompt. The check compares exact bytes for selected artifacts and rejects a managed prompt that remains after its option changes to `no`. Preserve, rename, or remove that now-unselected artifact deliberately within the active authority boundary, then recheck. Do not hand-edit generated prompt files; change the shipped template or canonical goal choice and regenerate.

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

After a material render, open `index.html` in Codex's in-app preview or reload the existing preview tab. Keep that preview available to the user. The render and closeout scripts must remain headless and portable: never shell-open a browser, invoke an external browser executable, or hardcode an application path. If Codex preview is unavailable, report that exact limitation and retain deterministic render and synchronization checks as evidence.

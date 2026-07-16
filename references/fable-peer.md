# Claude Fable planning peer

Use this reference when **Claude Fable peer feedback** is `yes` in `goal.md`.

## Contract

The planning checkbox plus `fable_review_rounds` count authorize preparing 1-10 external, read-only Claude Fable rounds through Anthropic for the current goal. Each round critiques the plan and proposes grounded feature and science/research opportunities. This is lane authorization, not approval of an exact export. Do not ask for a typed consent sentence. At action time, prepare an exact hashed file manifest and submit it through Codex's native owner-facing external-transmission approval UI. Default to one round. Recommend two when a follow-up critique after reconciliation adds material value; use more than three only when the user explicitly wants the added usage.

```bash
python3 scripts/run_fable_feedback.py docs/goals/<goal-slug>
python3 scripts/run_fable_feedback.py docs/goals/<goal-slug> \
  --context-file path/to/needed-context.md \
  --prepare-transmission
python3 scripts/run_fable_feedback.py docs/goals/<goal-slug> \
  --context-file path/to/needed-context.md \
  --approve-transmission <approval_digest>
python3 scripts/run_fable_feedback.py docs/goals/<goal-slug> --round 2
python3 scripts/run_fable_feedback.py docs/goals/<goal-slug> --check
```

The preparation step never invokes Claude. It always includes `goal.md`, `progress.md`, and prior-round artifacts, and accepts only repeated, repository-relative UTF-8 `--context-file` paths for extra evidence. Its manifest identifies every path, byte count, SHA-256, total bytes, destination, model, effort, and available tools. The invocation refuses a missing or stale digest, embeds only those approved bytes in the prompt, and exposes no local `Read`, `Glob`, `Grep`, `LS`, or shell tool to Claude.

The runner captures Claude stdout and stderr into `evidence/fable-transport/planning-round-N/attempt-1/`, records the PID and invocation digest, flushes and atomically finalizes raw output before parsing, and then writes the human feedback artifact. If an outer Codex wrapper loses stdout, rerun the identical manifest-bound runner command. A completed matching transport is reused without another Claude call; a live matching PID causes a duplicate-submission refusal. A timeout or stale started/running record has an unknown remote outcome and blocks resubmission instead of launching attempt 2. Keep `--transport-attempts 1`; inspect the durable files and obtain owner direction before any new external request.

Before preparing a packet, run `execution_profile.py preflight --require-external-review-approval`. It requires root `approvals_reviewer = "user"` and `approval_policy = "on-request"`; if configuration changes, open a new task because an existing task retains its original approval route. Then run the bound command directly with Codex `require_escalated` and a justification that names Anthropic Claude, the manifest digest, file list, total bytes, and private-data export risk. The resulting owner-facing checkbox is the exact transmission approval. Do not replace it with an agent-authored `owner_allowlisted` record or a prose reply gate in `progress.md`. The runner uses `claude --print` with model `claude-fable-5`, safe mode, `dontAsk`, WebSearch/WebFetch only, structured JSON output, and no session persistence. Default to `high` effort. Use `xhigh` only when the plan is difficult, ambiguous, high-risk, or an initial High pass leaves material uncertainty. Never select `max` automatically. It removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and `NODE_OPTIONS` from the child environment so the logged-in CLI path is used instead of a stray API credential. It never falls back to another model.

On this Codex Desktop environment, a sandboxed Claude process may report `loggedIn: false` because it cannot access the macOS credential context; allocating a PTY does not fix that. A direct `claude -p` invocation under the approved external execution context has been verified to work. Therefore request the exact native escalation before diagnosing authentication. When a user says the same command worked before, compare execution boundaries first: an earlier `require_escalated` call and a later sandboxed probe are different authentication environments, even with the same Claude binary and version. If the approved direct call still reports logged out, verify the same binary in an existing authenticated tmux session and use tmux only as a fallback for the exact same manifest-bound command. Never use tmux to bypass a denied Codex approval.

Round 1 is `evidence/fable-feedback.md`; rounds 2-10 use `evidence/fable-feedback-round-N.md`. Each new result contains its round number, requested/invoked/effective profile evidence, a `READY` or `REVISE` verdict, summary, strengths, severity-ordered concerns, recommendations, at most three optional information requests, up to three feature proposals, up to three science/research proposals, an amended brief, and the structured JSON payload. Feature proposals include opportunity, user value, goal fit, and validation. Science proposals include a falsifiable hypothesis, value, method, evidence needs, and goal fit. Legacy artifacts without proposal fields remain readable. A successful invocation does not prove the effective model or effort when the Claude envelope omits that metadata.

## Reconcile feedback

Treat Fable as an advisory planning peer, not an authority:

1. verify every concern against the goal, repository, and active constraints;
2. accept or reject it explicitly in the Decision log;
3. update the contract or phase plan only for accepted findings;
4. classify each feature and science proposal as accepted, rejected, or deferred in the Decision log with evidence;
5. accept an in-scope proposal only after verifying its fit; default adjacent and future proposals to deferred unless the user authorizes scope expansion;
6. rerender and validate the ledger;
7. when another round remains, run it only after the accepted changes are reflected in the current ledger;
8. record a **Claude Fable peer feedback** Verification row as `pass` with every artifact path after all configured rounds are reconciled.

Surface Fable's additional-information items before implementation when they materially improve the plan. They remain optional unless independent verification shows that an item actually changes scope, authorization, architecture, or the completion bar.

Without `--round`, the runner advances to the next missing or invalid configured round; after all rounds exist it reuses the final artifact. `--round N` targets one round but rejects out-of-order execution until every earlier artifact is valid. `--force` permits replacing that target (or the final round when no target is supplied). Prepare a fresh manifest after every reconciliation because changed files invalidate the prior digest. If the native approval, CLI, authentication, model, or network is unavailable, record the exact capability or policy decision as blocked. Do not silently skip, substitute, or bypass it.

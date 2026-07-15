# Capability-aware execution profiles

Use this reference when the user asks for particular GPT-5.6 models or reasoning effort, when work is delegated, or when the current runtime's controls are unclear.

## Recommended quality-first overnight profile

| Layer | Recommended request | Why |
| --- | --- | --- |
| Planning and architecture | GPT-5.6 Sol at `xhigh` | Strong quality-first reasoning without assuming the highest cost tier. |
| Hardest planning pass | GPT-5.6 Sol at `max` | Reserve for genuinely difficult, quality-first work after checking the prompt and success criteria. |
| Implementation | GPT-5.6 Luna at `max` through `goal-ledger-implementer` | Owned, reproducible implementation lane without a plugin dependency. |
| Final adversarial review | GPT-5.6 Sol at `xhigh`, optionally `max` | Independent closeout against the completion contract. |

This is a recommendation, not a universal default. Preserve the user's explicit model and effort choices. For routine or latency-sensitive work, establish a baseline and test lower effort when quality remains acceptable.

## Owned implementation fleet

| Agent name | Requested profile | Intended lane |
| --- | --- | --- |
| `goal-ledger-implementer` | GPT-5.6 Luna `max` | Default implementation lane. |
| `goal-ledger-implementer-luna-high` | GPT-5.6 Luna `high` | Routine or latency-sensitive implementation. |
| `goal-ledger-implementer-terra-ultra` | GPT-5.6 Terra `ultra` | Balanced implementation with deeper reasoning. |
| `goal-ledger-implementer-sol-medium` | GPT-5.6 Sol `medium` | Frontier implementation at moderate effort. |
| `goal-ledger-implementer-sol-xhigh` | GPT-5.6 Sol `xhigh` | Difficult, reasoning-heavy implementation. |
| `goal-ledger-implementer-sol-ultra` | GPT-5.6 Sol `ultra` | Highest-scrutiny implementation lane. |

Choose one primary preset during planning. Use a mixed swarm only when the implementation decomposes into independent file ownership or responsibilities. Record each worker separately in Custody, list every invoked role in the Implementation evidence, and preserve per-worker runtime confirmation; a configured or session-visible fleet is not proof that every requested worker ran with that profile.

## Requested, invoked, and effective

Record all three values in ledger v4 `goal.md`:

- **Requested profile**: what the user or plan wants.
- **Invoked profile**: the named role or explicit model/effort sent to the execution surface.
- **Effective profile**: what the current runtime actually confirmed.

Valid effective values include an exact confirmed model/effort, `current-runtime-default`, or `unconfirmed`. Never copy the requested value into the effective column without evidence.

## Runtime decision rule

1. Run `scripts/execution_profile.py preflight --implementer <agent-name>` and repeat `--swarm-implementer <agent-name>` for the planned mix; verify the owned fleet, every selected profile, and `[features.multi_agent_v2]` with `hide_spawn_agent_metadata = false`, `max_concurrent_threads_per_session = 8`, and `tool_namespace = "agents"`.
2. Treat `configured`, `session-visible`, and `runtime-confirmed` as separate states. Open a new task after installation before assessing session visibility.
3. Prefer the selected owned implementer; use explicit model and effort overrides only when the current delegation surface supports both.
4. Record the invoked role before execution and the effective model/effort only from runtime evidence. Configuration or a desired assignment is not runtime proof.
5. If exact controls do not exist, continue only when the fallback stays within scope; record the fallback or blocker visibly.

The shipped reviewer is `goal-ledger-reviewer`, pinned to GPT-5.6 Sol at `xhigh`. Keep interactive planning in the root task so required questions and optional-information prompts reach the user immediately.

## Drift

Model names, effort levels, defaults, and surface capabilities can change. Treat [latest-model-baseline.md](latest-model-baseline.md) as a dated snapshot. Verify current official documentation or live tool schemas when exact routing affects cost, latency, or correctness.

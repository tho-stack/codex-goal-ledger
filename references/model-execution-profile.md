# Capability-aware execution profiles

Use this reference when the user asks for particular GPT-5.6 models or reasoning effort, when work is delegated, or when the current runtime's controls are unclear.

## Recommended quality-first overnight profile

| Layer | Recommended request | Why |
| --- | --- | --- |
| Planning and architecture | GPT-5.6 Sol at `xhigh` | Strong quality-first reasoning without assuming the highest cost tier. |
| Hardest planning pass | GPT-5.6 Sol at `max` | Reserve for genuinely difficult, quality-first work after checking the prompt and success criteria. |
| Implementation | GPT-5.6 Terra at `max` | User-preferred implementation lane when the execution surface can select it. |
| Final adversarial review | GPT-5.6 Sol at `xhigh`, optionally `max` | Independent closeout against the completion contract. |

This is a recommendation, not a universal default. Preserve the user's explicit model and effort choices. For routine or latency-sensitive work, establish a baseline and test lower effort when quality remains acceptable.

## Requested versus effective

Record both values in `goal.md`:

- **Requested profile**: what the user or plan wants.
- **Effective profile**: what the current runtime actually confirmed.

Valid effective values include an exact confirmed model/effort, `current-runtime-default`, or `unconfirmed`. Never copy the requested value into the effective column without evidence.

## Runtime decision rule

1. Inspect the current surface or tool schema for model and effort controls.
2. If exact controls exist, use the requested values within the user's authorization.
3. If controls do not exist, continue with the current runtime only when that fallback stays within scope; record it visibly.
4. If exact routing is material to the result and requires a new user-owned task or external action, ask before creating it.
5. Do not claim per-subagent routing when the delegation tool exposes no model selector.

## Drift

Model names, effort levels, defaults, and surface capabilities can change. Treat [latest-model-baseline.md](latest-model-baseline.md) as a dated snapshot. Verify current official documentation or live tool schemas when exact routing affects cost, latency, or correctness.

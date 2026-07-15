# GPT-5.6 prompt contract for goal-ledger work

This skill follows the user-supplied GPT-5.6 Sol prompting guidance. Keep the operational prompt lean and validate changes on representative tasks.

## Preserve

- the user-visible outcome;
- observable success criteria and stopping conditions;
- authorization, safety, evidence, and business constraints;
- tool-routing rules only where context changes the route;
- required artifact shape and validation.

## Remove

- repeated versions of the same rule;
- examples that do not change behavior;
- process narration the model already performs reliably;
- unrelated tools and generic exhortations;
- absolute words for judgment calls.

## Intake shape

For a complex goal, establish:

```text
Role: operate and preserve a durable long-running goal
Goal: user-visible outcome
Success criteria: observable completion evidence
Constraints: authorization, scope, safety, and evidence rules
Tools: prerequisite retrieval and validation routes
Output: goal.md, progress.md, generated index.html, and final closeout
Stop rules: retry limits, blockers, completion bar, and smallest missing question
```

Ask only for a missing field that can change the path. Separately identify up to three optional inputs that would materially improve the result; name the benefit and the default assumption if omitted. Optional inputs never block execution. Preserve explicit user values instead of replacing them with keyword maps or global defaults.

## Long-running behavior

- Give a one- or two-sentence preamble before tools.
- Update only at major phase changes or when evidence changes the plan.
- Compact after milestones, not every turn.
- Keep objective, assumptions, priorities, and recovery state in repo files rather than relying on persisted reasoning.
- Re-evaluate stale reasoning after interruption.

## Tool and validation behavior

Resolve required discovery before action. Parallelize independent reads and synthesize before editing. Use deterministic scripts for bounded rendering and validation; keep semantic judgment, approval, and closeout in the model loop.

After implementation, run the most relevant targeted checks. Render visual artifacts and inspect layout, clipping, spacing, content, keyboard behavior, responsive behavior, and consistency before finalizing.

## Reasoning effort

Do not solve a missing success criterion or tool rule by automatically increasing effort. Establish a baseline, test lower levels when appropriate, use `high` or `xhigh` when they yield material gains, and reserve `max` for the hardest quality-first work.

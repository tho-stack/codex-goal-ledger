<p align="center">
  <img src="assets/icon-large.svg" alt="Codex Goal Ledger" width="112">
</p>

<h1 align="center">Codex Goal Ledger</h1>

<p align="center">
  Durable, inspectable state for long-running Codex work.
</p>

Codex Goal Ledger is a reusable Codex skill for work that must survive long runs,
context compaction, interruptions, delegated agents, and clean-session handoffs. It
keeps the execution contract and current truth in repository-local Markdown, then
renders an interactive HTML dashboard for fast human review.

The central rule is simple: **the ledger records what was actually verified, not what
the current session merely expects to be true.**

## What it provides

- A durable `goal.md` contract covering outcome, scope, authorization, success
  criteria, and closeout choices.
- A live `progress.md` ledger for phases, execution health, custody, evidence, gates,
  recovery state, and the smallest safe next action.
- A generated, responsive `index.html` dashboard with system/light/dark themes,
  search and state filters, keyboard shortcuts, phase navigation, and copy actions.
- Explicit separation between goal state, execution health, delegated-work custody,
  and verification evidence.
- Recovery rules that preserve completed work and reconcile real repository state
  before execution resumes.
- Deterministic, opt-in prompts for an independent LLM review and a new clean GPT
  session handoff.
- An optional additional `$codex-review` closeout gate.
- A portable installer with drift detection and backup-before-replace behavior.

The dashboard has no third-party runtime dependency, print/PDF workflow, external
browser launcher, or hardcoded application path. Codex opens or refreshes it through
the in-app preview when that capability is available.

## Install

Requirements:

- Codex with local skills support
- Python 3.10 or newer
- Git, if installing from a clone

Clone the repository and run the installer:

```bash
git clone https://github.com/tho-stack/codex-goal-ledger.git
cd codex-goal-ledger
python3 scripts/install_skill.py
python3 scripts/install_skill.py --check
```

The default destination is:

```text
$CODEX_HOME/skills/codex-goal-ledger
```

When `CODEX_HOME` is unset, the installer uses
`~/.codex/skills/codex-goal-ledger`. To choose another location:

```bash
python3 scripts/install_skill.py \
  --destination /path/to/skills/codex-goal-ledger
```

The installer copies only the actual skill package: `SKILL.md`, `agents/`, `assets/`,
`references/`, and `scripts/`. Repository documentation such as this README is not
placed in the installed skill.

### Update an installation

```bash
git pull --ff-only
python3 scripts/install_skill.py --replace
python3 scripts/install_skill.py --check
```

`--replace` never silently destroys a drifted installation. It first preserves the
existing directory as a timestamped sibling backup.

## Use it in Codex

Invoke the skill explicitly when a task needs durable execution state:

```text
Use $codex-goal-ledger to plan and run this overnight implementation. Keep the
goal contract, evidence, recovery state, and interactive dashboard current.
```

It also supports recovery and audit requests:

```text
Use $codex-goal-ledger to recover this interrupted task from the repository and
resume from the smallest safe next action.
```

```text
Use $codex-goal-ledger to audit whether this goal is genuinely complete and report
every unsupported or contradictory claim.
```

During planning, the skill asks one bundled question with recommendations for three
closeout options:

1. Generate a review prompt for Claude or another independent LLM.
2. Run an additional `$codex-review` at the end.
3. Generate a handoff prompt for a new clean GPT session.

Each choice remains explicit—`yes`, `no`, or temporarily `ask`. A goal cannot close
while any closeout choice is still unresolved.

## What it creates

Each goal lives inside the project being worked on:

```text
docs/
├── assets/
│   ├── goal-ledger.css
│   └── goal-ledger.js
└── goals/
    └── <goal-slug>/
        ├── goal.md
        ├── progress.md
        ├── index.html
        ├── review-prompt.md       # optional
        ├── handoff-prompt.md      # optional
        └── evidence/
```

`goal.md` and `progress.md` are canonical. `index.html` and the optional prompts are
generated artifacts; edit the Markdown sources and regenerate rather than patching
generated output by hand.

## Manual commands

Codex normally orchestrates these commands. They are also available for direct use,
automation, and debugging:

```bash
python3 scripts/init_goal.py \
  --project-root /path/to/project \
  --slug overnight-build \
  --title "Overnight build" \
  --why "Why this work matters" \
  --outcome "The observable finished state" \
  --external-review-prompt yes \
  --codex-review yes \
  --clean-session-handoff yes

python3 scripts/render_goal.py \
  /path/to/project/docs/goals/overnight-build

python3 scripts/generate_closeout_prompts.py \
  /path/to/project/docs/goals/overnight-build

python3 scripts/validate_goal.py \
  /path/to/project/docs/goals/overnight-build
```

Use `render_goal.py --check` and `generate_closeout_prompts.py --check` in CI or
read-only validation lanes. Use `render_goal.py --sync-assets` after upgrading the
shipped dashboard CSS or JavaScript.

## Repository layout

```text
SKILL.md       Authoritative instructions loaded by Codex
agents/        Codex UI metadata
assets/        Dashboard assets, icons, and ledger templates
references/    Detailed workflow, recovery, state, and closeout contracts
scripts/       Initializer, renderer, validator, installer, and tests

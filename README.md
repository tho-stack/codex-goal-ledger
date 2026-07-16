# Codex Goal Ledger

Codex Goal Ledger turns a long-running task into a durable, repository-local run record. The canonical plan and progress stay in Markdown; the generated dashboard makes execution state, evidence, review loops, recovery, and remaining gates easy to inspect.

It is designed for work that can outlive one chat session: difficult implementations, research programs, scientific investigations, and high-context reviews where “done” needs evidence.

<p align="center">
  <img src="docs/images/dashboard-full.png" alt="Goal Ledger dashboard showing the active objective, operational instruments, and separate run, evidence, review, and gate progress tracks" width="100%">
</p>

<p align="center"><sub>Real Goal Ledger rendering from a neutral synthetic fixture. No user, client, or project data is included.</sub></p>

<details>
  <summary>Responsive mobile view</summary>
  <p align="center">
    <img src="docs/images/dashboard-mobile.png" alt="Responsive mobile view of the Goal Ledger objective and latest verified truth" width="390">
  </p>
</details>

## What it adds

- Durable `goal.md` and `progress.md` files with generated HTML, never HTML as the source of truth.
- Separate progress tracks for run phases, evidence, selected reviews, and open gates—without a synthetic overall percentage.
- Optional multi-round Claude Fable planning review with critique, feature proposals, science proposals, and explicit reconciliation.
- Native GPT Pro review packets: a GPT-5.6-oriented review prompt, scoped context ZIP, checksummed manifest, complete raw response, and typed local reconciliation.
- A bundled restricted MCP App that gives ChatGPT real planning checkboxes and lets GPT Pro review only the immutable packet—without DevSpace, a separate plugin, live repository access, or shell tools.
- MCP-first GPT Pro delivery routing: the bundled restricted MCP App for structured subscription review, then user-operated native Chat/Pro with **Add to task**, Safari/Chrome, and a checksum-bound manual handoff. Computer Use never controls the ChatGPT/Codex host app.
- Bounded Claude Fable scientific rescue when a hard scientific question stalls implementation.
- Owned Codex implementation and review agents, including Luna, Sol, and Terra effort presets and mixed swarms.
- HTTP preview over Tailscale when available, with a localhost fallback; no `file://` dependency.
- Recovery capsules and clean-session handoffs that state the last verified truth and exact next action.
- One goal, one execution envelope: once planning is resolved, in-scope web and literature research, hardware investigation, dependency setup, implementation, local compute, qualification, testing, reviews, recovery, and frozen retries continue unattended without repeated consent prompts.
- Durable unattended execution: tmux availability is preflighted, the outer supervisor runs detached from the Codex terminal, and validated checkpoints let recovery reuse completed work instead of restarting an entire campaign.

## Review and rescue circuit

The dashboard derives this circuit from preserved evidence. A blocked or revise verdict creates a visible return path; a selected but unfinished review stays dashed.

<p align="center">
  <img src="docs/images/dashboard-review-circuit.png" alt="Review circuit showing Fable and GPT Pro revision rounds, a bounded Fable scientific rescue path, and the independent closeout review path" width="100%">
</p>

The three review roles are intentionally different:

- **Fable planning peer** challenges the plan before Build. It may propose missing information, features, and scientific hypotheses. One bounded owner approval covers all configured planning and rescue calls inside the disclosed goal-path envelope; every exact manifest and response is still preserved.
- **GPT Pro** is an independent high-context gate for the plan, the implementation, or both. A `BLOCKED` result returns to revision; `SIGNED OFF` advances only after Codex records a typed, locally verified reconciliation.
- **Fast gate reviewer** uses Luna High for repeated manifest, custody, dashboard, launch, recovery, and narrow post-fix checks. It returns `GO`, `BLOCKED`, or `NEEDS_DEEP_REVIEW` without occupying the Sol Ultra planning lane.
- **Codex closeout reviewer** uses Sol XHigh after Verify. Accepted findings return to Build or Verify, then the closeout evidence is refreshed before Close.

**Fable rescue is not another routine review.** Before Build abandons a scientific route or records a terminal `no-campaign`, `unresolvable`, or mechanism-rejection decision, the skill automatically evaluates the rescue triggers. A qualified route enters the formal prediction-locked rescue runner; an unqualified route gets a durable evidence-backed checkpoint explaining why. Extra pasted or ad-hoc Fable reviews do not satisfy this gate or consume the incident budget. Fable remains advisory; Codex must classify every proposal, run the authorized prediction-locked experiment, record the outcome, and return the verified learning to Build. Rescue advice can never serve as completion evidence by itself.

For GPT Pro, `auto-ui` prefers the restricted MCP App because it provides manifest reads, response submission, and deterministic receipts. If MCP is unavailable, the skill generates a native Chat handoff: open **Chat**, select Pro, upload the exact packet, wait for the complete response, and click **Add to task** to return it to Codex. Safari and Chrome remain later fallbacks. The native route uses the ChatGPT subscription and never extracts session cookies, device attestation, Sentinel tokens, or private ChatGPT API calls.

```mermaid
flowchart LR
    Plan --> FablePlan[Fable planning rounds]
    FablePlan -->|REVISE| PlanFix[Revise plan]
    PlanFix --> FablePlan
    FablePlan -->|READY| ProPlan[GPT Pro plan review]
    ProPlan -->|BLOCKED| ContractFix[Revise contract]
    ContractFix --> ProPlan
    ProPlan -->|SIGNED OFF| Build

    Build -->|qualified scientific impasse| Rescue[Fable scientific rescue]
    Rescue --> Reconcile[Codex reconciliation]
    Reconcile --> Experiment[Prediction-locked experiment]
    Experiment --> Outcome[Recorded outcome]
    Outcome --> Build

    Build --> Verify
    Verify --> ProImplementation[Optional GPT Pro implementation review]
    ProImplementation --> CodexReview[Optional Codex closeout review]
    CodexReview -->|accepted fixes| Build
    CodexReview --> Close
```

The incident budget, approved repository scope, exact transmitted manifest, and experiment authority are fixed in the goal contract. A new scientific question or expanded file scope requires a new authorized incident rather than silently extending the old one.

## Install

From this repository:

```bash
python3 scripts/install_skill.py --with-agents --with-review-bridge
python3 scripts/install_skill.py --replace --configure-review-approvals
python3 scripts/install_skill.py --check --with-agents --with-review-bridge
python3 scripts/install_skill.py --check --configure-review-approvals
```

The installer copies the skill and its owned agents into the Codex skill directory. It also checks the multi-agent settings the workflow depends on:

Replaced skill versions are archived under `$CODEX_HOME/backups/skills/`, never beside the active skill where Codex could discover them as duplicate skills. A normal install also migrates legacy sibling `codex-goal-ledger.backup-*` directories into that archive; `--check` reports legacy backups without changing them.

```toml
[features.multi_agent_v2]
hide_spawn_agent_metadata = false
max_concurrent_threads_per_session = 8
tool_namespace = "agents"

[agents]
max_threads = 8
max_depth = 1
```

If configuration is missing or incompatible, the skill reports the exact fix rather than silently claiming that an agent profile was used.

`--with-review-bridge` makes the private GPT Pro bridge an installer-owned, resumable setup. Existing Keychain credentials, tunnel profiles, managed runtimes, and the verified ChatGPT app are reused automatically. On first install, Codex continues in Safari, then Chrome if needed, and asks only at the required account-security boundaries: creating the Tunnels-only runtime key and enabling/connecting ChatGPT Developer mode. The key is restricted to Tunnels Read + Use, stored in macOS Keychain, removed from the clipboard, and never written to the skill, profile, ledger, or Git. No API credits or model permissions are enabled; GPT Pro usage remains on the ChatGPT subscription.

Fable needs an owner-facing native approval route for its one-time bounded goal envelope. The explicit `--configure-review-approvals` option preserves a backup of `config.toml` and sets only:

```toml
approvals_reviewer = "user"
approval_policy = "on-request"
```

Open a new Codex task after changing these values. Run `run_fable_feedback.py <goal-dir> --authorize-goal` once through that native route. Later manifests need no new prompt while their paths and call parameters remain inside the recorded envelope.

### Optional direct GPT Pro bridge

Goal Ledger ships `scripts/run_review_bridge.py` inside the skill. The bridge is bound to one prepared review round and exposes a familiar but bounded workspace over manifest-listed members from `context-packet.zip`. It has no Git, shell, edit, arbitrary-path, or live-repository tools.

Use OpenAI Secure MCP Tunnel so the local server remains private. After the one-time ChatGPT developer-app connection, preflight and print the exact round-bound command:

```bash
python3 scripts/run_review_bridge.py check \
  --goal-dir docs/goals/example-goal --stage plan --round 1 \
  --require-tunnel-client
python3 scripts/run_review_bridge.py print-command \
  --goal-dir docs/goals/example-goal --stage plan --round 1
```

Use the printed stdio command in the tunnel profile, then open the `Codex Goal Ledger` app in a visible GPT Pro conversation. Pro receives a bounded DevSpace-style workspace with `open_workspace`, `list_files`, `read`, `search`, and `write_review`. It can inspect the immutable packet and save its complete answer without ZIP handling or a widget begin step, but it receives no shell, live-repository, edit, or arbitrary-write access. Packet-hash-bound receipts prove every file was read before the response is accepted. The [detailed one-time setup and review bridge runbook](references/review-bridge.md#detailed-one-time-setup) covers installation, Platform permissions, tunnel and runtime-key creation, ChatGPT developer mode, private app registration, verification, per-review rebinding, credential handling, and recovery.

The [automatic Codex-driven setup](references/review-bridge.md#automatic-codex-driven-setup) documents the exact Safari/Chrome, Keychain, managed-runtime, subscription-only, connection-verification, and idempotent recovery sequence used by the installer.

<p align="center">
  <img src="docs/images/mcp-planning-controls.png" alt="Goal Ledger MCP planning controls with six review checkboxes, one-time Fable approval, bounded round settings, GPT Pro selectors, and an implementation preset" width="100%">
</p>

<p align="center"><sub>Planning mode replaces typed approval text with real checkboxes, bounded selectors, and one Approve selected lanes button.</sub></p>

<details>
  <summary>Immutable GPT Pro packet console</summary>
  <p align="center">
    <img src="docs/images/mcp-pro-review.png" alt="Goal Ledger MCP review console showing an immutable packet digest, bounded packet members, exact-packet custody controls, and a manual response fallback" width="100%">
  </p>
</details>

## Use

Invoke `$codex-goal-ledger` in Plan mode and describe the outcome. When connected, the bundled app presents six real checkboxes, bounded selectors, a one-time Fable disclosure covering planning and scientific rescue, and an **Approve selected lanes** button. No typed approval sentence follows that click. If the app is unavailable, the skill uses native click controls or one concise checklist.

For direct initialization, this is the minimal shape:

```bash
python3 scripts/init_goal.py \
  --project-root /path/to/project \
  --slug example-goal \
  --title "Example Goal" \
  --why "The work needs a durable execution contract." \
  --outcome "The result is verified and recoverable." \
  --fable-feedback yes \
  --fable-rescue yes \
  --pro-review yes \
  --codex-review yes
```

Then render and serve the dashboard over HTTP:

```bash
python3 scripts/render_goal.py docs/goals/example-goal --sync-assets
python3 scripts/serve_dashboard.py docs/goals/example-goal --host-mode auto
```

## Custody model

Goal Ledger treats the phase rail as the primary milestone, not a mutex. Independent workstreams may run concurrently when their real prerequisites are satisfied. Planning records each lane's deliverable, blockers, mutation class, state, owner, evidence path, and bounded slot allocation; research is kept separate from implementation, purchases, and live hardware actions so a scientific gate does not unnecessarily idle hardware or software research. Root orchestration reserves capacity for supervision and review, and workers cannot recursively create an unplanned second swarm.

External reviewers receive only the files listed in the packet manifest. Every packet is hashed, every response is preserved in full, and every recommendation gets an explicit local disposition. Requested, invoked, and effective model identities are recorded separately; an unconfirmed runtime identity stays unconfirmed.

The dashboard is a view over those artifacts. It does not infer success from prose, elapsed time, a reviewer’s confidence, or an agent’s claim.

## Validate

```bash
python3 scripts/test_goal_ledger.py
python3 scripts/test_execution_profile.py
python3 scripts/test_fable_feedback.py
python3 scripts/test_fable_transport.py
python3 scripts/test_fable_rescue.py
python3 scripts/test_pro_review.py
python3 scripts/test_review_bridge.py
python3 scripts/test_setup_review_bridge.py
python3 scripts/test_review_graph.py
python3 scripts/test_preview_server.py
python3 scripts/test_closeout_prompts.py
python3 scripts/test_install_skill.py
```

Before a long-running or overnight command, verify the durable execution dependency:

```bash
python3 scripts/execution_profile.py preflight --require-tmux
```

Goal Ledger records the tmux binary and version, launches the outermost monitor or supervisor in a detached task-scoped session, and verifies its first heartbeat. Tmux prevents terminal/task boundaries from killing the monitor; atomic result checkpoints remain required for true computational resume.

The README screenshots are generated from a synthetic goal named **Aurora Research Program** and neutral MCP fixtures. They contain no real goal, repository, user, or client information.

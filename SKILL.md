---
name: codex-goal-ledger
description: Run, recover, audit, resume, and honestly close long-running Codex goals with repo-local goal and progress Markdown, generated interactive HTML, custody tracking, evidence gates, capability-aware execution profiles, optional Fable review and rescue, and GPT Pro review through a bundled restricted MCP App, native Chat handoff, or prompt-plus-ZIP fallback. Use for overnight or interruption-prone work, durable handoffs, hard scientific impasses, multi-agent recovery, high-context plan or implementation review, or any task that must remain trustworthy across compaction, restarts, and new sessions.
---

# Codex Goal Ledger

Create a durable operating record for long-running work. A successful ledger lets another session determine the true state and smallest safe next action from repository files alone.

## Canonical artifacts

Keep one goal at:

```text
docs/goals/<goal-slug>/
├── goal.md
├── progress.md
├── index.html
├── review-prompt.md      # optional, when selected
├── handoff-prompt.md     # optional, when selected
└── evidence/
    ├── fable-feedback.md # optional round 1, when selected and completed
    ├── fable-feedback-round-N.md # optional configured rounds 2-10
    ├── fable-transport/ # durable raw planning-review transport state
    ├── fable-rescue/rescue-NNN/ # qualified rescue request, response, reconciliation, outcome, and transport
    ├── pro-review/<stage>/round-NNN/ # native prompt, ZIP, manifest, submission, full response, and reconciliation
    └── preview-server.json # generated runtime endpoint evidence
```

Shared presentation assets live in `docs/assets/goal-ledger.css` and `docs/assets/goal-ledger.js`.

- `goal.md` is the human contract: why, outcome, success criteria, scope, authorization, and completion bar.
- `progress.md` is live operational truth: phase, execution health, custody, evidence, gates, recovery, and next action.
- `index.html` is generated. Never treat it as the source of truth.
- `review-prompt.md` and `handoff-prompt.md` are deterministic, opt-in closeout artifacts. Regenerate them from the canonical choice table; do not hand-edit them.
- Evidence belongs under the goal directory or at a stable repo path linked from the ledger.

## Start or resume

1. Read any user-supplied goal, brief, gate, or policy file in full. Treat explicit choices and hard boundaries as authoritative.
2. Perform only the bounded discovery needed to make contextual recommendations: inspect the repository, current goal-tool state when available, and any existing goal directory. Do not begin implementation, delegation, or long-running validation during discovery.
3. Make the first interactive planning checkpoint happen immediately after bounded discovery. Start it with a **Planning input assessment** that separates:
   - **Required before execution**: only missing facts whose answer can materially change scope, architecture, authorization, or the completion bar;
   - **Optional, improves result**: at most three high-leverage inputs the user could provide, each stated as **Information**, **What it improves**, and **Default if omitted**.
   Say `No additional information would materially improve this plan` when the optional lane is empty. Do not ask the user for information the repository or connected tools can discover safely.
4. Ask only the required missing facts:
   - why the work matters;
   - the user-visible outcome;
   - observable completion criteria;
   - authorization boundaries;
   - execution profile when the user has not chosen one, including the primary implementation preset and any mixed-swarm profiles justified by independently owned work.
   Optional inputs must not block execution. If the user omits or skips one, use its stated default, record any material assumption in `goal.md` or the Decision log, and proceed after the required questions and review choices are resolved.
5. In that same checkpoint, ask the six independent review, rescue, and handoff choices and recommend a contextual choice for each item:
   - ask Claude Fable through Anthropic for read-only plan critique plus feature and science/research proposals before implementation; when selected, also ask for 1-10 review rounds (default 1), and state that one goal-scoped native approval can authorize every configured round whose files remain inside the disclosed goal directory and explicit additional-file envelope;
   - enable bounded Claude Fable scientific rescue for qualified hard scientific impasses; recommend `yes` only for hard/scientific goals, otherwise `no`; default to two lineage-scoped incidents, one round per incident, and XHigh effort;
   - run native GPT Pro review with a GPT-5.6-shaped prompt plus deterministic scoped ZIP, full raw-response custody, and typed reconciliation; recommend `yes` for difficult, ambiguous, scientific, or high-risk plans; default to MCP-first `auto-ui`, which routes through the restricted `mcp-app`, user-operated native Chat/Pro plus **Add to task**, Safari/Chrome, and finally owner handoff, with explicit transport, `implementation`, `both`, `advisory`, or 2-3 rounds available when justified;
   - generate `review-prompt.md` for Claude or another independent LLM;
   - run an additional `$codex-review` closeout;
   - generate `handoff-prompt.md` for a new clean GPT session.
6. Read and follow [planning-controls.md](references/planning-controls.md). Prefer the bundled Goal Ledger app when connected: it renders six literal checkboxes, bounded selectors, a one-time Fable-envelope checkbox, and an **Approve selected lanes** button. Treat the resulting structured `owner_approval.fable_goal_authorization: true` event as the owner's answer for both selected Fable planning and scientific-rescue lanes; do not ask for a typed approval sentence afterward. When the app is unavailable but `request_user_input` exists, use its clickable controls immediately and never replace them with prose asking the user to type `yes` or `no`. Use one concise Markdown checklist only when neither structured surface is available. Never split the checkpoint across unattended work or defer it to status, verification, or closeout.
7. Wait only for required missing facts and unresolved review choices unless the user explicitly asks to pause for optional context. Do not initialize the execution plan, implement, spawn or delegate workers, start a long-running command, or enter unattended execution while a required item remains unresolved.
8. Record an explicit `yes` or `no` for all six rows in `goal.md` under **Closeout options**, plus the Fable and GPT Pro selectors in frontmatter. Use `ask` only while waiting at this planning checkpoint; never infer consent from silence. A Fable `yes` authorizes the configured lane. Before round 1, prefer one native owner approval of `run_fable_feedback.py --authorize-goal`; it records a bounded envelope covering the goal directory, explicitly named additional files, configured rounds and rescue incidents, Anthropic destination, model, efforts, and per-call byte limit. Later changing hashes do not require another approval while the exact manifest remains inside that envelope. Use exact digest approval only as a fallback or when expanding the envelope. Never ask for a typed consent sentence. A GPT Pro `yes` pre-approves only the exact generated request plus hashed ZIP for ChatGPT Pro; ask again only for expanded transmission, destination, or goal scope. Recommend one planning round normally, two when reconciliation benefits from a follow-up critique, and more than three only when the user explicitly wants the added usage.
9. Do not ask for ceremonial metadata such as a session name, arbitrary subgoal count, or preferred log length.
10. Initialize missing artifacts with `scripts/init_goal.py`. Preserve existing artifacts unless the user authorizes replacement.
11. If a goal-state tool exists and no matching goal is active, create a short pointer objective to `goal.md`; keep the full contract in the repository.

For difficult quality-first overnight builds, recommend this profile without making it universal:

- planning and architecture: GPT-5.6 Sol at `xhigh`; reserve `max` for the hardest pass;
- implementation: `goal-ledger-implementer` at Luna Max by default; optionally select Luna High, Terra Ultra, Sol Medium, Sol XHigh, or Sol Ultra from the owned fleet;
- final adversarial review: GPT-5.6 Sol at `xhigh`, or `max` when justified.
- frequent operational gate review: `goal-ledger-gate-reviewer` at Luna High; reserve the slower Sol reviewer for deep or final review.

Preserve explicit user selections. Record requested, invoked, and effective profiles separately. Before unattended implementation, run `scripts/execution_profile.py preflight --implementer <agent-name>` for the primary preset; it checks the owned agent files, registrations, and `[features.multi_agent_v2]` values `hide_spawn_agent_metadata = false`, `max_concurrent_threads_per_session = 8`, and `tool_namespace = "agents"`. When either Fable lane is selected, add `--require-external-review-approval` during planning, before preparing a packet. It fails fast unless root Codex config routes action-time approval to the owner with `approvals_reviewer = "user"` and `approval_policy = "on-request"`. Configuration proves only readiness for a newly opened task; after changing it, open a new task before claiming the live approval route is effective. Record any preset as effective only when that worker runtime confirms its model and effort. Use a mixed implementation swarm only when work has independent ownership boundaries, list every invoked role in Custody and evidence, and never infer that all workers used the primary preset. Never depend on a LazyCodex role or stale role advertised by an already-open task. Read [model-execution-profile.md](references/model-execution-profile.md) for the full fleet and routing rules.

Also require native `[agents]` limits `max_threads = 8` and `max_depth = 1`. Root sessions start at depth 0, so this permits root-owned workers while preventing workers from recursively creating an unplanned second generation. Treat any other depth as configuration drift and open a new task after repair.

When **Claude Fable peer feedback** is `yes`, first run `scripts/execution_profile.py preflight --require-external-review-approval`; repair configuration only with explicit user authority and open a new task after any change. Then obtain one goal-scoped approval with `scripts/run_fable_feedback.py <goal-dir> --authorize-goal`, adding repeated `--authorization-context-file <repo-relative-file>` only for files outside the goal directory that later rounds or rescue may transmit. Run that authorization command through the native owner approval surface once and request a safely scoped reusable execution approval when supported. The stored `evidence/fable-goal-authorization.json` permits every configured planning round and rescue incident while each exact manifest remains inside the recorded path, destination, model, effort, and byte envelope. The runner still hashes and records every exact packet; it simply stops asking again when the standing envelope covers it. A later file outside the envelope requires one explicit envelope expansion or the legacy exact-digest approval. Then run the configured sequential, read-only Claude CLI rounds. The runner always includes `goal.md`, `progress.md`, and prior-round artifacts; Claude receives only embedded allow-listed files and has no local repository tools. Use `high` effort normally, `xhigh` only for difficult, ambiguous, or high-risk planning, and never select `max` automatically. After the goal contract and initial phase plan are stable—but before implementation—start round 1 immediately. Each round returns critique, optional information, up to three feature opportunities, and up to three science/research hypotheses with validation methods. Treat everything as advisory: verify concerns and proposals, record each accepted/rejected/deferred decision, and update the contract only for accepted in-scope items. Default adjacent and future proposals to deferred; adding them to the active goal requires normal scope-expansion authorization. Render and validate after reconciliation, then run the next round against the changed plan without another owner prompt when covered. Never run later rounds against an unreconciled plan. Round 1 is `evidence/fable-feedback.md`; later rounds are `evidence/fable-feedback-round-N.md`. Record the passing **Claude Fable peer feedback** Verification row only after every configured round is reconciled. If direct escalated `claude -p` cannot see the logged-in account, follow the tmux diagnostic and fallback in [fable-peer.md](references/fable-peer.md); a sandboxed `auth status` result alone is not proof that the account is logged out. Do not silently substitute another model.

When **Claude Fable scientific rescue** is `yes`, read and follow [fable-rescue.md](references/fable-rescue.md). Before abandoning a scientific route or recording a terminal scientific decision such as `no-campaign`, `unresolvable`, or a mechanism rejection, automatically evaluate all rescue triggers after operational failures are excluded. If one qualifies, immediately use the schema-valid candidate with `scripts/run_fable_rescue.py`; never substitute an ad-hoc Fable review. If none qualifies, record the evidence-backed `not_qualified` checkpoint with `--record-eligibility` before closing that route. Do not force a checkpoint while an active method is still reducing the declared uncertainty. Manual or pasted Fable advice is advisory only, does not satisfy the checkpoint, and does not consume the incident budget. The runner persists eligibility, candidate, request, exact manifest, raw stdout/stderr, transport state, parsed response, usage, reconciliation, and outcome under `evidence/fable-rescue/`. It hash-locks predictions before the experiment and requires an outcome against that lock before another incident. Rescue is advisory and its hashes may never appear in completion evidence.

Both Fable runners use the shared durable transport. Raw output is flushed and atomically finalized inside the goal before parsing. If Codex's outer command wrapper detaches, expires, or loses stdout, inspect the transport record and rerun the identical manifest-bound runner command: it reuses a completed matching response, refuses a duplicate while the recorded PID is alive, and never silently resubmits. A timeout or stale started/running record has an unknown remote outcome and forbids automatic resubmission; preserve it for owner-guided recovery. `--transport-attempts` must remain `1`. Do not fall back to a raw `claude -p` rerun just because wrapper output was empty.

When **GPT Pro review** is `yes`, read and follow [pro-review.md](references/pro-review.md). Goal Ledger owns this workflow; never invoke, read, or depend on a separate `$pro` skill. Prepare every selected stage and round with `scripts/run_pro_review.py prepare`, which creates an immutable GPT-5.6-shaped `request.md`, deterministic scoped `context-packet.zip`, exact source/member manifest, a delivery plan, and durable state. `auto-ui` is MCP-first: try the bundled goal-scoped workspace app, then the user-operated native Chat/Pro surface, then Safari/Chrome, then owner handoff. For `mcp-app`, also read [review-bridge.md](references/review-bridge.md), run `scripts/run_review_bridge.py check`, and serve only the manifest-bound packet through the bundled MCP App and OpenAI Secure MCP Tunnel. In a visible Pro conversation, ask Pro to `open_workspace`, read `START-HERE.md`, use `list_files`, `read`, and `search` across the bounded immutable workspace, then call `write_review` once. This DevSpace-style interaction makes Pro the active reviewer without giving it shell, live-repository, arbitrary-read, edit, or arbitrary-write access. Every read receives a packet-hash-bound audit receipt; the sole content write is the immutable review plus submission custody. A verdict without complete receipts or response structure is invalid. If MCP is unavailable before submission, use `native-chat-handoff.md`, then browser or owner fallback. Never downgrade to prompt-only or resubmit after `submission.json` exists. Verify every Pro claim locally and record typed `FIX`, `DEFER`, `DISMISS`, or `QUESTION` reconciliation. Required plan review must be signed off before Build; required implementation review must be signed off before completion.

Before unattended execution, put every selected closeout lane into the execution plan. Generate selected prompt artifacts as soon as the contract is stable, and run a selected additional Codex review automatically after verification without waiting for the user to return. Never postpone a previously selected review until the final response.

Before freezing the execution plan, decompose the goal into dependency-aware workstreams. Treat the single active Phase tracker row as the primary milestone, not a mutex over all work. For each workstream record its deliverable, real prerequisites, mutation class, owner, state, and stable evidence path in **Parallel workstreams** and Custody. Split research, design, implementation, live operation, and purchasing when their dependencies differ; never hide safe research inside a broadly gated implementation row. Start every authorized dependency-free workstream promptly, up to an explicit concurrency budget, while blocked descendants remain queued. Reserve slots for the root, any active supervisor, and required gate review; assign the remaining slots to named lanes. Delegated workers must not recursively spawn subworkers unless the root allocated that fan-out in advance. Reconcile every started or interrupted descendant before calling its parent lane complete. A scientific qualification may block scientific implementation, plant access, or outcome-dependent deployment selection without blocking independent literature, hardware, interface, operating-system, or component research. Write gates narrowly against their actual descendants; never use “no delegation before X” unless every possible delegated item truly depends on X. Recompute ready workstreams after every gate result, custody return, interruption, or plan revision.

Before any long-running, overnight, monitored, or interruption-sensitive command, read [durable-execution.md](references/durable-execution.md) and run `scripts/execution_profile.py preflight --require-tmux`. Freeze two separately hashed artifacts: the **scientific closure** binds only the contract, algorithm sources, tolerances, dimensions, evaluator, and fold or experiment design; the **execution environment** binds interpreter or toolchain binaries and paths, venvs, temporary or scratch paths, host specifics, and PIDs. If a proposed frozen artifact contains an absolute path outside the repository, an interpreter or toolchain binary hash, or a machine-specific path, classify it as environment-tier by definition and remove it from the review-bound scientific closure. An environment-only change never invalidates scientific review. A review authorizes the frozen scientific closure, not a launch count: single-use, per-launch, or "consumed" ledger permits are forbidden. Apply the litmus test before every retry: **if the scientific closure hash is unchanged, no new approval of any kind is needed to retry** an operational failure.

On macOS or Linux, launch the outermost supervisor in a detached, task-scoped tmux session; do not leave the supervisor attached to Codex's terminal while only its child is detached. Record the resolved tmux path/version, session name, separately hashed scientific-closure and environment identities, supervisor PID, monitor, logs, and checkpoint paths in Custody. Before a detached or overnight launch, require at least one test that spawns the real entrypoint as a real subprocess under the real target interpreter through the real argv-construction path; in-process suites do not qualify. Any dry-run, smoke test, or preflight must traverse the same validation and gate path it claims to test, stopping only before the declared side effect. A hardcoded passing result is worse than no gate and is forbidden. Verify the session, supervisor, and first heartbeat before marking work active. Tmux protects terminal continuity but does not replace checkpointing: expensive multi-stage work must atomically preserve validated dependency-complete results, cumulative budgets, and segment resource evidence so recovery reruns only the interrupted uncommitted unit. If tmux is unavailable, do not start fragile foreground work; install it when goal authority covers the dependency or stop once with the missing capability. Never use tmux to bypass a denied native approval.

For repeated operational gates, delegate the review immediately to `goal-ledger-gate-reviewer` instead of making the root planning model perform a fresh deep review. Give it the smallest immutable packet that can decide the gate: canonical ledger paths, exact artifact or manifest identity, relevant changed paths, required checks, and the expected `GO`, `BLOCKED`, or `NEEDS_DEEP_REVIEW` verdict. It is the default for manifest/custody checks, dashboard truth, launch readiness, recovery readiness, and narrow post-fix rechecks. If an already-open task cannot see the newly installed named role but its delegation surface supports explicit controls, spawn a read-only default subagent with model `gpt-5.6-luna` and effort `high`, record that invoked fallback and keep effective identity unconfirmed until runtime evidence exists; do not make the Sol root perform the review. Keep the reviewed bytes stable while it runs; continue only independent non-gated work in parallel. A `BLOCKED` verdict returns the exact findings for repair and a fresh fast recheck. `NEEDS_DEEP_REVIEW`, scientific or mathematical judgment, architecture/security ambiguity, and final adversarial closeout route to `goal-ledger-reviewer`, Fable, or GPT Pro as the contract requires. Never let the fast lane waive a selected review or substitute for implementation.

## Operate

Keep these four layers separate:

1. **Goal state**: whether the objective is draft, active, blocked, paused, complete, or abandoned.
2. **Execution health**: whether the current root execution is healthy, degraded, interrupted, or blocked.
3. **Custody**: who owns each work item and whether it is queued, active, waiting, complete, failed, or lost.
4. **Evidence**: what was actually verified, where the artifact lives, and what remains unproven.

Never infer one layer from another. A failed root execution can coexist with completed delegated work; a running worker does not make the goal complete.

One active phase may coexist with several active custody workstreams. Keep the phase rail focused on the primary critical path and use **Parallel workstreams** plus Custody for concurrent lanes. A blocked workstream does not block the goal while another in-scope workstream can make meaningful progress.

Use one authorization policy:

- For review, diagnosis, or planning, inspect and report; do not implement unless asked.
- For build, change, or fix requests, make in-scope local edits and run non-destructive validation without another approval prompt.
- Once the planning checkpoint is resolved and the goal starts, the accepted goal contract is the authorization event. Its recorded Scope and Authorization remain standing authority across phases, retries, recovery, compaction, and new tasks. Run all in-envelope work without asking again: repository and browser work, web and literature research, hardware and component research, downloads, goal-scoped dependency setup, bounded local compute, tests, benchmarks, qualification campaigns, frozen retries, implementation, delegation, and configured review lanes. A new manifest, digest, resource budget, failed attempt, contract revision, resumed task, or replacement run is custody evidence, not a new permission boundary.
- Interpret an explicit user statement such as “authorize the whole goal” as approval for every non-destructive action reasonably necessary to deliver the recorded outcome, including network research and hardware investigation. Record any narrower exclusions in the contract instead of asking category by category.
- Ask only when an action is outside the accepted envelope or the platform requires a native security confirmation that cannot be pre-authorized. Purchases, public publishing or messages, destructive actions, secret disclosure, unsafe physical operations, and material scope expansion are outside the default envelope unless the user positively includes and bounds them in the contract.

Never invent a later owner-authorization gate for work already covered by the started goal. Do not require a typed sentence, a fresh checkbox, or three unanswered turns before continuing. The repeated-blocker threshold applies only to a real dependency outside standing authority; it cannot convert redundant reauthorization into a valid blocker. Before an unattended stretch, preflight the full execution envelope and obtain any unavoidable platform-native approvals while the owner is present, using a safely scoped reusable approval when supported. If a prepared action truly falls outside the recorded envelope, stop once with the exact delta; do not relitigate the rest of the goal.

Update `progress.md` at major phase changes, after meaningful evidence, before a long unattended stretch, after interruption, and before final response. Each update records one concrete outcome and the next gate. Do not narrate routine tool calls.

At every update, apply these forced transitions before doing more bookkeeping:

- If the most recent launch, run, or campaign attempt failed, set `execution_health: degraded` at minimum and keep it there until a subsequent attempt passes. Honest failure evidence and documentation quality never upgrade aggregate health. The next commit must address or diagnose the cause; it may not add failure-recording machinery instead. Cap per-failure evidence at one file, and create no per-failure review-request document unless the owner asks. Additional recording is allowed only after the causal fix is identified and scheduled.
- If three consecutive commits or two elapsed hours produced only custody, binding, or ledger bookkeeping with no newly passing test, solver or experiment second, or artifact named by a success criterion, set `execution_health: degraded`, add one paragraph to the ledger naming the ceremony loop, and either simplify the process or escalate it to the owner. Do not continue the same loop silently.
- If harness or custody code exceeds roughly three times the object-level code it protects, record the ratio and justification in the ledger and surface it to the owner at the next checkpoint before growing it further.

After every material ledger update:

1. render `index.html`;
2. run the validator;
3. check selected closeout prompts for synchronization;
4. start or reuse `scripts/serve_dashboard.py <goal-dir>`, health-check it, and open or reload its HTTP URL in the same Codex task's in-app Browser;
5. correct stale, contradictory, or unsupported claims before continuing.

The dashboard review circuit is derived from Fable artifacts, GPT Pro state and reconciliation, rescue incidents, Verification rows, and phase or gate state. Do not hand-edit graph state or invent a dashboard-only completion source. Never remove historical review nodes when a configured round count, stage, or current phase changes. Mark a reconciled round as completed with an accessible checkmark while preserving its original verdict and revision-return evidence. Show review returns as revision loops and keep run, evidence, reviews, and gates as separate discrete progress tracks; never collapse them into one weighted percentage.

Preview is an orchestration action, not a renderer side effect. Never navigate to `file://`. The preview server binds only to a connected Tailscale IPv4 address when available and otherwise to `127.0.0.1`; it serves the goal directory plus the allow-listed shared dashboard CSS and JavaScript, reports the actual port, writes `evidence/preview-server.json`, and exposes a health endpoint. Use the Browser skill from the same Codex task: claim the matching in-app tab when it already exists or create one, navigate or reload the reported HTTP URL, request browser visibility, verify the page DOM, and retain that tab as a `deliverable` when finalizing browser work. Server health or a hidden tab is not proof that the dashboard was presented in the task. If visibility cannot be confirmed, keep browser QA pending or blocked and report the URL; do not claim the preview loaded in-session. Never shell-open a browser, launch an external browser executable, or hardcode an application path. If the active Codex surface has no in-app Browser capability, report that limitation without claiming browser QA passed.

When the work log becomes unwieldy, move older detail into `evidence/log-<date>.md`, link it, and retain only the recent decision-bearing entries in `progress.md`.

Read [workflow.md](references/workflow.md) for milestone cadence, long unattended runs, and custody handoffs. Read [state-model.md](references/state-model.md) when reconciling ambiguous states. Read [recovery.md](references/recovery.md) after abnormal termination, stale output, or lost custody.

## Recover

On resume or abnormal termination:

1. Read `goal.md` and `progress.md` before taking new action.
2. Inspect repository state, goal-tool state, running work, outputs, and evidence paths.
3. Reconcile each custody row. Do not report "nothing ran" merely because the root execution stopped.
4. Mark execution health honestly and preserve completed outputs before restarting work.
5. Refresh the recovery capsule with last verified truth, current layer, resume point, unsafe assumptions, and canonical files.
6. Render and validate before resuming implementation.

## Close

Close only when every required success criterion is evidenced, all blocking gates are resolved, every required custody item is complete, and verification contains no pending, failed, or blocked required check. A skipped phase or verification row is resolved only when its exact label is authorized in the matching `allowed_skipped_*` goal-frontmatter field.

Before closing:

1. resolve every **Closeout options** row to explicit `yes` or `no`;
2. verify every configured Fable round with `run_fable_feedback.py --check`, every selected GPT Pro lane with `run_pro_review.py check --require-closed`, and each selected prompt with `generate_closeout_prompts.py --check`;
3. if additional Codex review is `yes`, follow `$codex-review`: treat findings as advisory, verify each against the real code, fix only accepted findings, rerun affected checks and review after edits, and never push unless the user requested it;
4. update both Markdown frontmatters to `status: complete`;
5. record the actual final repository/commit state without implying an unmade commit;
6. render and validate the final dashboard, then reload it in Codex preview;
7. mark the goal-state tool complete only after the repository contract is truly satisfied.

If a concrete condition prevents meaningful work, the repository ledger may use `status: blocked` immediately and name the smallest unblocking action. Update an external goal-state tool to blocked only when that tool's own threshold is met; do not conflate the two state machines.

## Commands

Resolve these paths relative to this skill directory.

Installing or replacing a global skill, agent profile, root approval setting, or review bridge is an external write. Run the installer only after the user authorizes that destination and selected integrations. It defaults to `$CODEX_HOME/skills/codex-goal-ledger`, or `~/.codex/skills/codex-goal-ledger` when `CODEX_HOME` is unset, refuses skill drift by default, and preserves replaced skills under `$CODEX_HOME/backups/skills/` when `--replace` is explicit. A normal install migrates legacy sibling `codex-goal-ledger.backup-*` directories out of the discoverable `skills/` directory; `--check` reports them without mutating. `--with-agents` installs only the owned implementer fleet and reviewer plus a delimited config block, and verifies or configures the three required `[features.multi_agent_v2]` values. `--configure-review-approvals` is a separate explicit opt-in that backs up `config.toml` and sets only root `approvals_reviewer = "user"` and `approval_policy = "on-request"`. It never modifies or removes LazyCodex remnants. Open a new task after agent or approval configuration before checking session effectiveness.

The same `--with-agents` operation verifies or configures `[agents] max_threads = 8` and `max_depth = 1`; these native limits bound total agent concurrency and spawned depth independently of the `multi_agent_v2` presentation settings.

When `--with-review-bridge` is authorized, read [review-bridge.md](references/review-bridge.md) and continue the installer-owned bootstrap in the same task; do not stop at printed manual instructions. Reuse an existing tunnel, Keychain item, app record, profile, and managed runtime. On macOS drive Safari first and Chrome second; on Windows or Linux use Chrome; never control the ChatGPT desktop/classic app. Create only a Tunnels Read + Use runtime key with every non-tunnel permission set to None, never add API credits, store it in the OS secret manager, and clear the clipboard. Ask for action-time confirmation immediately before key creation and again before enabling Developer mode and connecting the private app. Run `setup_review_bridge.py` for profile, `doctor`, managed-runtime, app-record, and ready checks. If first app discovery stops the runtime, restart it and refresh the existing connector instead of creating duplicates. Treat the bridge as ready only after ChatGPT visibly reports `Connected to Codex Goal Ledger`, the bounded workspace tools are visible, and the managed runtime is running, healthy, and ready.

```bash
python3 scripts/install_skill.py --with-agents --with-review-bridge
python3 scripts/install_skill.py --check --with-agents --with-review-bridge
python3 scripts/install_skill.py --replace --configure-review-approvals
python3 scripts/install_skill.py --check --configure-review-approvals
python3 scripts/setup_review_bridge.py check --require-chatgpt-app

python3 scripts/init_goal.py \
  --project-root . \
  --slug overnight-build \
  --title "Overnight build" \
  --why "Why this matters" \
  --outcome "Observable end state" \
  --planning-profile "gpt-5.6-sol xhigh" \
  --implementation-agent "goal-ledger-implementer-sol-xhigh" \
  --swarm-implementer "goal-ledger-implementer-luna-high" \
  --swarm-implementer "goal-ledger-implementer-terra-ultra" \
  --fable-profile "claude-fable-5 high" \
  --review-profile "gpt-5.6-sol xhigh" \
  --fable-feedback yes \
  --fable-review-rounds 2 \
  --fable-rescue yes \
  --fable-rescue-max-incidents 2 \
  --fable-rescue-rounds-per-incident 1 \
  --fable-rescue-effort xhigh \
  --pro-review yes \
  --pro-review-rounds 1 \
  --pro-review-stage plan \
  --pro-review-delivery auto-ui \
  --pro-review-gate required \
  --external-review-prompt yes \
  --codex-review yes \
  --clean-session-handoff yes

python3 scripts/render_goal.py docs/goals/overnight-build
python3 scripts/execution_profile.py preflight \
  --require-external-review-approval \
  --implementer goal-ledger-implementer-sol-xhigh \
  --swarm-implementer goal-ledger-implementer-luna-high \
  --swarm-implementer goal-ledger-implementer-terra-ultra
python3 scripts/run_fable_feedback.py docs/goals/overnight-build
python3 scripts/run_fable_feedback.py docs/goals/overnight-build --authorize-goal
python3 scripts/run_fable_feedback.py docs/goals/overnight-build --prepare-transmission
python3 scripts/run_fable_feedback.py docs/goals/overnight-build \
  --approve-transmission <SHA256>
python3 scripts/run_fable_feedback.py docs/goals/overnight-build --check
python3 scripts/run_fable_rescue.py docs/goals/overnight-build \
  --candidate rescue-candidate.json --prepare-transmission
python3 scripts/run_fable_rescue.py docs/goals/overnight-build \
  --record-eligibility rescue-not-qualified.json
python3 scripts/run_fable_rescue.py docs/goals/overnight-build \
  --candidate rescue-candidate.json --approve-transmission <SHA256>
python3 scripts/run_fable_rescue.py docs/goals/overnight-build \
  --incident 1 --reconcile reconciliation.json
python3 scripts/run_fable_rescue.py docs/goals/overnight-build \
  --incident 1 --record-outcome outcome.json
python3 scripts/run_fable_rescue.py docs/goals/overnight-build \
  --incident 1 --supplement path/requested-by-fable.md --prepare-transmission
python3 scripts/run_fable_rescue.py docs/goals/overnight-build \
  --incident 1 --record-owner-resolution owner-resolution.json
python3 scripts/run_fable_rescue.py docs/goals/overnight-build --check
python3 scripts/run_pro_review.py prepare docs/goals/overnight-build \
  --stage plan --round 1 \
  --decision "Approve this plan for implementation." \
  --context-file path/to/operative-plan.md
python3 scripts/run_review_bridge.py check \
  --goal-dir docs/goals/overnight-build --stage plan --round 1
python3 scripts/run_review_bridge.py print-command \
  --goal-dir docs/goals/overnight-build --stage plan --round 1
python3 scripts/run_pro_review.py record-attempt docs/goals/overnight-build \
  --stage plan --round 1 --surface safari-assisted \
  --result ready --detail "Authenticated Pro Extended mode and file upload are visible."
python3 scripts/run_pro_review.py record-submission docs/goals/overnight-build \
  --stage plan --round 1 --model-visible "Pro Extended" \
  --transport safari-assisted --thread "Overnight build plan review"
python3 scripts/run_pro_review.py record-response docs/goals/overnight-build \
  --stage plan --round 1 --response-file /path/to/full-pro-response.md
python3 scripts/run_pro_review.py reconcile docs/goals/overnight-build \
  --stage plan --round 1 --reconciliation-file reconciliation.json
python3 scripts/run_pro_review.py check docs/goals/overnight-build --require-closed
python3 scripts/generate_closeout_prompts.py docs/goals/overnight-build
python3 scripts/validate_goal.py docs/goals/overnight-build
python3 scripts/serve_dashboard.py docs/goals/overnight-build
python3 scripts/serve_dashboard.py docs/goals/overnight-build --check
python3 scripts/test_goal_ledger.py
python3 scripts/test_execution_profile.py
python3 scripts/test_fable_feedback.py
python3 scripts/test_fable_rescue.py
python3 scripts/test_fable_transport.py
python3 scripts/test_pro_review.py
python3 scripts/test_review_bridge.py
python3 scripts/test_setup_review_bridge.py
python3 scripts/test_review_graph.py
python3 scripts/test_install_skill.py
python3 scripts/test_preview_server.py
```

Use `render_goal.py --sync-assets` after upgrading this skill's shipped CSS or JavaScript. Use `render_goal.py --check` and `generate_closeout_prompts.py --check` in validation lanes to detect stale generated artifacts without modifying files. Paths in examples are repository-relative or supplied at runtime; do not embed local application or dependency paths.

## References

- [workflow.md](references/workflow.md): full start, operate, recover, and close protocol.
- [durable-execution.md](references/durable-execution.md): tmux preflight, detached supervisor launch, checkpointing, monitoring, and recovery across task boundaries.
- [planning-controls.md](references/planning-controls.md): mandatory app-native planning controls and implementation-profile selector mapping.
- [fable-peer.md](references/fable-peer.md): optional read-only Fable planning feedback contract.
- [fable-rescue.md](references/fable-rescue.md): qualified scientific-rescue triggers, schemas, prediction lock, durable transport, and recovery.
- [pro-review.md](references/pro-review.md): self-contained GPT Pro immutable-packet preparation, restricted MCP App delivery, cross-platform UI routing, manual fallback, full response custody, reconciliation, gates, and recovery.
- [review-bridge.md](references/review-bridge.md): bundled restricted MCP App, detailed one-time Secure MCP Tunnel and ChatGPT connection setup, real planning controls, immutable packet access, direct Pro response capture, credential handling, troubleshooting, and security boundary.
- [closeout-kit.md](references/closeout-kit.md): planning choices, external-review prompt, Codex review, and clean-session handoff contract.
- [state-model.md](references/state-model.md): allowed states, invariants, and reconciliation rules.
- [recovery.md](references/recovery.md): failure-mode playbook and evidence-preserving recovery order.
- [model-execution-profile.md](references/model-execution-profile.md): requested, invoked, and effective model routing and fallbacks.
- [prompting-gpt-5p6.md](references/prompting-gpt-5p6.md): lean prompt contract used by this skill.
- [progress-template.md](references/progress-template.md): Markdown schema and section contract.
- [latest-model-baseline.md](references/latest-model-baseline.md): dated capability snapshot; verify drift-prone claims.

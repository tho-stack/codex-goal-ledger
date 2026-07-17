# Durable long-running execution

Use this protocol for any command expected to outlive the current tool turn, run
unattended or overnight, own a monitor/child process tree, or take long enough
that recomputation would be material.

## Preflight

Run:

```bash
python3 scripts/execution_profile.py preflight --require-tmux
```

The preflight resolves `tmux` from `PATH`, runs `tmux -V`, and records its path
and version. On macOS or Linux, do not start qualifying long work in a foreground
terminal when this check fails. Install tmux through the available system package
manager when that installation is inside the accepted goal envelope; otherwise
ask once for the missing dependency. On native Windows, use tmux through WSL or
an explicitly recorded durable platform supervisor. Never claim tmux durability
when the check failed.

Tmux protects process continuity across Codex task and terminal boundaries. It
does not make an algorithm resumable and does not replace checkpoints, resource
monitoring, custody, or external-transmission approval.

Freeze two independent hashes before launch:

- **Scientific closure:** contract, algorithm sources, tolerances, dimensions,
  evaluator, and fold or experiment design. This is the only tier a scientific
  review authorizes.
- **Execution environment:** interpreter and toolchain binaries or paths, venvs,
  temporary or scratch paths, host specifics, and PIDs.

An absolute path outside the repository, interpreter or toolchain binary hash,
or machine-specific path makes an artifact environment-tier by definition. Move
it out of the immutable review-bound scientific closure. Environment-only
changes never invalidate scientific review. Ledger reviews do not authorize a
launch count: single-use, per-launch, and "consumed" launch permits are
forbidden. Litmus test: **if the scientific closure hash is unchanged, no new
approval of any kind is needed to retry** an operational failure.

Before a detached or overnight launch, one test must spawn the real entrypoint
as a real subprocess under the real target interpreter through the real
argv-construction path. In-process suites are not launch evidence. A dry-run,
smoke test, or preflight must traverse the same validation and gate path it
claims to test and stop only before the declared side effect. Never print or
return a hardcoded pass; such a gate is worse than no gate.

## Launch

1. Use a deterministic task-scoped session name containing the goal slug and
   work item. Sanitize it to letters, digits, `_`, and `-`.
2. Check `tmux has-session -t <name>` before launch. An existing session must be
   inspected, never overwritten or duplicated silently.
3. Put the exact command in a goal-owned manifest or executable launcher rather
   than assembling complex unreviewed quoting through `send-keys`.
4. Start the outermost supervisor inside a detached session. The supervisor, not
   only its scientific child, must survive the terminal boundary.
5. Redirect durable stdout and stderr to declared paths even when tmux also has a
   pane history.
6. Record the tmux path/version, session name, exact command, separate
   scientific-closure and environment hashes, working directory, start time,
   supervisor PID, expected outputs, monitor path, and checkpoint path in
   Custody or goal-owned evidence.
7. Verify the session exists, the expected supervisor process is live, and the
   first monitor/heartbeat record is valid before describing the work as active.

Example shape, with `<launcher>` already containing the exact reviewed command:

```bash
tmux has-session -t goal-<slug>-<work-item>
tmux new-session -d -s goal-<slug>-<work-item> -c <project-root> <launcher>
tmux list-panes -t goal-<slug>-<work-item> -F '#{pane_pid} #{pane_dead} #{pane_current_command}'
```

Do not use tmux to bypass a denied native approval or to conceal a command from
the execution policy.

## Checkpoints and budgets

For expensive multi-stage work, checkpoint at the smallest dependency-complete
unit. A checkpoint must bind its input/manifest identity, ordered unit identity,
validated numerical output, residual or verification result, resource evidence,
cumulative elapsed budget, and artifact hashes. Write it atomically and verify it
before advancing.

On recovery:

- reuse only validated, hash-matching completed checkpoints;
- retry only the interrupted uncommitted unit;
- carry cumulative time and resource maxima across execution segments;
- preserve every segment's monitor and logs under immutable attempt paths;
- never skip work merely because a monitor saw a `completed` process state;
- never reset a scientific search or retry budget by starting a new tmux session.

If the runner has no admissible checkpoints, say so plainly. Preserve the
interrupted evidence and rerun the smallest dependency-complete unit; do not
pretend process metadata reconstructs lost numerical results.

## Recovery

Use `tmux has-session`, `tmux list-panes`, the process tree, heartbeat, monitor,
and output artifacts together. A missing Codex terminal is not evidence that the
tmux job stopped. A missing tmux session is not evidence that every child stopped.
Do not kill an orphan reflexively: first determine whether the durable supervisor
or a validated checkpoint can recover custody. If continued execution would be
unmonitored or violate a frozen contract, preserve the attempt and stop only the
identified orphan process tree.

When a detached segment finishes, preserve its pane/log output, reconcile the
exit status and artifacts, update `progress.md`, render, validate, and close the
tmux session only after no recovery evidence remains inside it.

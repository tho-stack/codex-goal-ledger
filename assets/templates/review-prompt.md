# Independent completion review: {{TITLE_MD}}

Review the completed work from the repository root. Stay read-only unless the user separately authorizes changes.

## Canonical record

- Goal contract: `{{GOAL_PATH}}`
- Operational truth: `{{PROGRESS_PATH}}`
- Generated dashboard: `{{DASHBOARD_PATH}}`

Read both Markdown records in full before reviewing. Treat the current repository, generated artifacts, and command results as authoritative; do not accept completion claims merely because they appear in the ledger.

## Review contract

1. Derive every explicit requirement, boundary, deliverable, and completion gate from the goal contract.
2. Inspect the implementation and direct evidence that should prove each requirement.
3. Check that `goal.md`, `progress.md`, and `index.html` agree, while remembering that Markdown is canonical.
4. Identify correctness, safety, recovery, usability, portability, and verification gaps. Pay special attention to claims that are broader than their evidence.
5. Confirm the actual repository state without assuming a commit, push, deployment, installation, or external action occurred.

Return findings first, ordered by severity, with precise repository-relative `file:line` references when possible. Then provide a compact requirement-to-evidence matrix, remaining uncertainties, and exactly one final verdict: `READY` or `NOT READY`. If the verdict is `NOT READY`, name the smallest concrete actions required to reach `READY`.

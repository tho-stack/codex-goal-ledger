# Claude Fable scientific rescue

Use this reference when **Claude Fable scientific rescue** is `yes` and a hard scientific goal has stopped reducing a declared uncertainty.

## Qualification

Before abandoning a scientific route, issuing a terminal `no-campaign` or `unresolvable` decision, or rejecting a scientific mechanism because current evidence conflicts with the plan, perform the rescue eligibility checkpoint automatically when rescue is selected. Do not wait for the owner to ask for Fable.

- If a trigger qualifies, create a versioned candidate JSON and immediately run `run_fable_rescue.py --candidate <path> --prepare-transmission`. The runner records `eligibility-NNN.json` before preparing the exact packet. The candidate should name the scientific route and proposed terminal action, and must state a neutral question, empty `operational_blockers`, a declared uncertainty metric, at least two competing hypotheses with their strongest disconfirming evidence, verified facts with evidence paths, SHA-256 values, and verification methods, constraints, non-goals, and the smallest repository-relative evidence allow-list.
- If no trigger qualifies, create an evidence-backed `not_qualified` decision that assesses all five triggers and run `run_fable_rescue.py --record-eligibility <path>`. This durable record is required before the route is terminally closed.
- If an active experiment or analysis is still reducing the declared uncertainty, continue it. Do not manufacture a terminal decision merely to create an eligibility record.

An ad-hoc Fable peer review, pasted Claude answer, or extra planning-review round does not satisfy this checkpoint and does not consume the rescue budget. Once a route qualifies, use the formal runner instead of opening another review lane.

Use one trigger:

- `failed_approaches`: at least two distinct method families with numeric before/after uncertainty and no reduction;
- `contradictory_evidence`: at least two claims backed by distinct current evidence hashes;
- `non_discriminating_experiment`: the recorded experiment cannot separate the competing hypotheses;
- `numerical_ambiguity`: known-answer and implementation checks exist and all pass;
- `answerability_uncertain`: the exact missing identifiability or evidence boundary is named.

Never qualify authentication, permissions, authorization, dependency, network, or environment failure as science. The validator checks structure and provenance; it cannot eliminate scientific judgment at the margins.

Example `not_qualified` decision:

```json
{
  "schema_version": 1,
  "decision": "not_qualified",
  "scientific_route": "model-layer interpretation of the candidate mechanism",
  "proposed_terminal_action": "record no-campaign and abandon this route",
  "rationale": "Current evidence resolves the interpretation without external rescue.",
  "operational_blockers": [],
  "trigger_assessments": {
    "failed_approaches": {"qualified": false, "rationale": "Only one method family was attempted."},
    "contradictory_evidence": {"qualified": false, "rationale": "The current artifacts agree after replay."},
    "non_discriminating_experiment": {"qualified": false, "rationale": "The registered test separates both hypotheses."},
    "numerical_ambiguity": {"qualified": false, "rationale": "No unresolved numerical sign remains."},
    "answerability_uncertain": {"qualified": false, "rationale": "The evidence boundary is known."}
  },
  "evidence": [{
    "evidence_path": "docs/goals/example/evidence/route-review.json",
    "sha256": "<current SHA-256>",
    "verification_method": "Replayed the registered selector against the frozen inputs."
  }]
}
```

## Invocation and durable custody

Preparation prints an exact manifest without contacting Claude. Prefer the same one-time `fable-goal-authorization.json` used by planning reviews. A rescue packet proceeds automatically when its incident number, destination, model, effort, bytes, and every evidence path remain inside that owner-approved envelope. Use `--approve-transmission <digest>` only for a one-off packet outside the standing envelope, or expand the envelope once when a new path is genuinely required.

The runner writes `candidate.json`, `request.json`, and `transmission-manifest.json` before the external call. The shared transport records the single authorized call under `transport/attempt-1/` with `transport.json`, `raw-response.json`, and `stderr.txt`. Output is fsynced and atomically renamed before response parsing. A repeated identical invocation reuses completed output, refuses while a matching PID is live, and cannot mint a second incident from an unfinished matching candidate. A timeout or stale started/running state has an unknown remote outcome and forbids resubmission; `--transport-attempts` must remain `1`. Never replace this path with a raw Claude command.

Transport or schema failures do not count as scientific incidents. Retry operational failures at most twice, then surface durable diagnostics. `INSUFFICIENT_PACKET` permits only one specifically named existing-artifact follow-up; it is not `NEEDS_NEW_DATA` and must remain within the same approval policy.

## Reconciliation and outcome

Fable must return diagnoses, up to three alternative hypotheses, one highest-information experiment, locked expected outcomes, controls, stop conditions, what would change its mind, confidence, unknowns, scope effects, and a verdict. The diagnosis taxonomy includes conceptual, identifiability, data, numerical, metric, contract-impossibility, implementation-defect, and underpowered/confounded-design failures. Multiple diagnoses are allowed when the next experiment must separate them.

Record reconciliation with typed claims:

- `fact_check`: accept or reject against a current evidence hash;
- `diagnostic_judgment`: defer until experiment outcome;
- `recommendation`: accept, reject, or defer with rationale; rejection requires counter-evidence.

The runner stores a hash of the response and expected-outcome table in `reconciliation.json`. After the experiment, record `outcome.json` with the observation, matched prediction index or `none`, hypothesis update, and current evidence hash. Validation blocks another incident when the prior prediction/outcome loop is open. `NEEDS_NEW_DATA` and `UNRESOLVABLE_UNDER_CONTRACT` require an owner-resolution artifact before another incident.

The default budget is two incidents across the full `fable_rescue_lineage`, not per split goal. Incident 2 requires a structured delta naming the prior recommendation attempted, observed outcome, material change, and prior outcome hash. Cosmetic request edits do not satisfy this gate.

Rescue is advisory diagnosis, never implementation or completion evidence. Validation rejects a rescue path in the Verification evidence column and requires every used rescue incident to be reconciled and closed before goal completion.

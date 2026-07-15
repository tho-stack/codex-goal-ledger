# Claude Fable scientific rescue

Use this reference when **Claude Fable scientific rescue** is `yes` and a hard scientific goal has stopped reducing a declared uncertainty.

## Qualification

Create a versioned candidate JSON and run `run_fable_rescue.py --candidate <path> --prepare-transmission`. The candidate must state a neutral question, empty `operational_blockers`, a declared uncertainty metric, at least two competing hypotheses with their strongest disconfirming evidence, verified facts with evidence paths, SHA-256 values, and verification methods, constraints, non-goals, and the smallest repository-relative evidence allow-list.

Use one trigger:

- `failed_approaches`: at least two distinct method families with numeric before/after uncertainty and no reduction;
- `contradictory_evidence`: at least two claims backed by distinct current evidence hashes;
- `non_discriminating_experiment`: the recorded experiment cannot separate the competing hypotheses;
- `numerical_ambiguity`: known-answer and implementation checks exist and all pass;
- `answerability_uncertain`: the exact missing identifiability or evidence boundary is named.

Never qualify authentication, permissions, authorization, dependency, network, or environment failure as science. The validator checks structure and provenance; it cannot eliminate scientific judgment at the margins.

## Invocation and durable custody

Preparation prints an exact manifest without contacting Claude. Submit the matching runner command with `--approve-transmission <digest>` through the native external-transmission layer. The planning choice already authorizes automatic use inside the recorded repository scope; do not create another conversational approval gate. Ask only when scope expands.

The runner writes `candidate.json`, `request.json`, and `transmission-manifest.json` before the external call. The shared transport then records each attempt under `transport/attempt-N/` with `transport.json`, `raw-response.json`, and `stderr.txt`. Output is fsynced and atomically renamed before response parsing. A repeated identical invocation reuses completed output, refuses while a matching PID is live, and cannot mint a second incident from an unfinished matching candidate. Never replace this path with a raw Claude command.

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

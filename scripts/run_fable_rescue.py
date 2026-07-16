#!/usr/bin/env python3
"""Qualify, run, reconcile, and validate bounded Claude Fable scientific rescues."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Mapping, Sequence

from fable_transport import (
    atomic_write,
    atomic_write_json,
    build_transmission_manifest,
    collect_transmission_files,
    context_packet,
    invocation_digest,
    run_claude_durable,
)
from generate_closeout_prompts import FABLE_RESCUE_OPTION, load_closeout_options
from ledger_common import LedgerError, load_document, project_root_for


SCHEMA_VERSION = 1
MAX_INCIDENTS_LIMIT = 10
TRIGGERS = {
    "failed_approaches",
    "contradictory_evidence",
    "non_discriminating_experiment",
    "numerical_ambiguity",
    "answerability_uncertain",
}
DIAGNOSES = {
    "conceptual_error",
    "identifiability_problem",
    "missing_data",
    "numerical_failure",
    "inadequate_metric",
    "impossible_under_contract",
    "implementation_defect",
    "underpowered_or_confounded_design",
}
VERDICTS = {
    "CONTINUE",
    "REDESIGN_TEST",
    "NEEDS_NEW_DATA",
    "UNRESOLVABLE_UNDER_CONTRACT",
    "INSUFFICIENT_PACKET",
}
TERMINAL_OWNER_GATES = {"NEEDS_NEW_DATA", "UNRESOLVABLE_UNDER_CONTRACT"}

FABLE_RESCUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": sorted(VERDICTS)},
        "summary": {"type": "string"},
        "root_diagnoses": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {"type": "string", "enum": sorted(DIAGNOSES)},
        },
        "diagnosis_distinguishable": {"type": "boolean"},
        "alternative_hypotheses": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "hypothesis": {"type": "string"},
                    "rationale": {"type": "string"},
                    "disconfirming_observation": {"type": "string"},
                },
                "required": ["hypothesis", "rationale", "disconfirming_observation"],
            },
        },
        "discriminating_experiment": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "method": {"type": "string"},
                "information_gain_rationale": {"type": "string"},
                "required_evidence": {"type": "array", "items": {"type": "string"}},
                "known_answer_controls": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "title",
                "method",
                "information_gain_rationale",
                "required_evidence",
                "known_answer_controls",
            ],
        },
        "expected_outcomes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "hypothesis": {"type": "string"},
                    "observation": {"type": "string"},
                    "interpretation": {"type": "string"},
                },
                "required": ["hypothesis", "observation", "interpretation"],
            },
        },
        "stop_conditions": {"type": "array", "items": {"type": "string"}},
        "what_would_change_my_mind": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string"},
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "scope_effects": {"type": "array", "items": {"type": "string"}},
        "requested_artifact": {"type": ["string", "null"]},
    },
    "required": [
        "verdict",
        "summary",
        "root_diagnoses",
        "diagnosis_distinguishable",
        "alternative_hypotheses",
        "discriminating_experiment",
        "expected_outcomes",
        "stop_conditions",
        "what_would_change_my_mind",
        "confidence",
        "unknowns",
        "scope_effects",
        "requested_artifact",
    ],
}


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"missing JSON artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"invalid JSON artifact: {path}: {exc}") from exc


def _require_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LedgerError(f"{label} must be a JSON object")
    return dict(value)


def _required_string(value: Mapping[str, Any], field: str, label: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise LedgerError(f"{label}.{field} must be a non-empty string")
    return item.strip()


def _required_list(value: Mapping[str, Any], field: str, label: str) -> list[Any]:
    item = value.get(field)
    if not isinstance(item, list):
        raise LedgerError(f"{label}.{field} must be a list")
    return list(item)


def _validate_evidence_reference(
    reference: Mapping[str, Any], *, project_root: Path, allow_list: set[str], label: str
) -> None:
    path_text = _required_string(reference, "evidence_path", label)
    digest = _required_string(reference, "sha256", label)
    if path_text not in allow_list:
        raise LedgerError(f"{label}.evidence_path must appear in evidence_files: {path_text}")
    path = project_root / path_text
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(project_root)
    except (FileNotFoundError, ValueError) as exc:
        raise LedgerError(f"{label}.evidence_path is missing or escapes the repository") from exc
    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if digest != actual:
        raise LedgerError(f"{label}.sha256 is stale for {path_text}")


def validate_candidate(value: object, *, goal_dir: Path) -> dict[str, Any]:
    candidate = _require_object(value, "candidate")
    if candidate.get("schema_version") != SCHEMA_VERSION:
        raise LedgerError(f"candidate.schema_version must be {SCHEMA_VERSION}")
    trigger = _required_string(candidate, "trigger", "candidate")
    if trigger not in TRIGGERS:
        raise LedgerError("candidate.trigger must be one of: " + ", ".join(sorted(TRIGGERS)))
    question = _required_string(candidate, "question", "candidate")
    if re.search(r"(?i)\b(desired|preferred|prove|confirm)\s+(decision|answer|outcome)\b", question):
        raise LedgerError("candidate.question must be neutral and must not encode a desired decision")
    blockers = _required_list(candidate, "operational_blockers", "candidate")
    if blockers:
        raise LedgerError(
            "scientific rescue excludes operational blockers; resolve auth, permissions, "
            "network, dependency, or authorization failures first"
        )
    evidence_files = _required_list(candidate, "evidence_files", "candidate")
    if not evidence_files or not all(isinstance(item, str) and item for item in evidence_files):
        raise LedgerError("candidate.evidence_files must contain repository-relative paths")
    allow_list = set(evidence_files)
    project_root = project_root_for(goal_dir)

    metric = _require_object(candidate.get("uncertainty_metric"), "candidate.uncertainty_metric")
    _required_string(metric, "name", "candidate.uncertainty_metric")
    if not isinstance(metric.get("lower_is_better"), bool):
        raise LedgerError("candidate.uncertainty_metric.lower_is_better must be boolean")

    hypotheses = _required_list(candidate, "hypotheses", "candidate")
    if len(hypotheses) < 2:
        raise LedgerError("candidate.hypotheses must contain at least two competing hypotheses")
    for index, raw in enumerate(hypotheses, 1):
        hypothesis = _require_object(raw, f"candidate.hypotheses[{index}]")
        _required_string(hypothesis, "name", f"candidate.hypotheses[{index}]")
        _required_string(
            hypothesis,
            "strongest_disconfirming_evidence",
            f"candidate.hypotheses[{index}]",
        )

    facts = _required_list(candidate, "verified_facts", "candidate")
    for index, raw in enumerate(facts, 1):
        fact = _require_object(raw, f"candidate.verified_facts[{index}]")
        _required_string(fact, "fact", f"candidate.verified_facts[{index}]")
        _required_string(
            fact, "verification_method", f"candidate.verified_facts[{index}]"
        )
        _validate_evidence_reference(
            fact,
            project_root=project_root,
            allow_list=allow_list,
            label=f"candidate.verified_facts[{index}]",
        )

    attempts = _required_list(candidate, "attempts", "candidate")
    contradictions = _required_list(candidate, "contradictions", "candidate")
    known_checks = _required_list(candidate, "known_answer_checks", "candidate")
    implementation_checks = _required_list(candidate, "implementation_checks", "candidate")
    for field, items in (
        ("contradictions", contradictions),
        ("known_answer_checks", known_checks),
        ("implementation_checks", implementation_checks),
    ):
        for index, raw in enumerate(items, 1):
            item = _require_object(raw, f"candidate.{field}[{index}]")
            _validate_evidence_reference(
                item,
                project_root=project_root,
                allow_list=allow_list,
                label=f"candidate.{field}[{index}]",
            )

    if trigger == "failed_approaches":
        if len(attempts) < 2:
            raise LedgerError("failed_approaches requires at least two attempts")
        families: set[str] = set()
        lower = bool(metric["lower_is_better"])
        for index, raw in enumerate(attempts, 1):
            attempt = _require_object(raw, f"candidate.attempts[{index}]")
            families.add(_required_string(attempt, "approach_family", f"candidate.attempts[{index}]"))
            _required_string(attempt, "material_change", f"candidate.attempts[{index}]")
            before, after = attempt.get("uncertainty_before"), attempt.get("uncertainty_after")
            if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
                raise LedgerError("attempt uncertainty_before/after must be numeric")
            reduced = after < before if lower else after > before
            if reduced:
                raise LedgerError(
                    f"candidate.attempts[{index}] reduced the declared uncertainty; "
                    "failed_approaches does not qualify"
                )
        if len(families) < 2:
            raise LedgerError("failed_approaches requires distinct approach_family values")
    elif trigger == "contradictory_evidence":
        hashes = {str(item.get("sha256", "")) for item in contradictions if isinstance(item, dict)}
        if len(contradictions) < 2 or len(hashes) < 2:
            raise LedgerError("contradictory_evidence requires two claims with distinct evidence hashes")
    elif trigger == "non_discriminating_experiment":
        experiment = _require_object(
            candidate.get("current_experiment"), "candidate.current_experiment"
        )
        if experiment.get("distinguishes_hypotheses") is not False:
            raise LedgerError(
                "non_discriminating_experiment requires distinguishes_hypotheses: false"
            )
    elif trigger == "numerical_ambiguity":
        if not known_checks or not implementation_checks:
            raise LedgerError(
                "numerical_ambiguity requires known-answer and implementation checks"
            )
        for item in [*known_checks, *implementation_checks]:
            if not isinstance(item, dict) or item.get("passed") is not True:
                raise LedgerError("numerical_ambiguity requires every mechanical check to pass")
    elif trigger == "answerability_uncertain":
        _required_string(candidate, "answerability_gap", "candidate")

    _required_list(candidate, "constraints", "candidate")
    _required_list(candidate, "non_goals", "candidate")
    return candidate


def validate_response(value: object) -> dict[str, Any]:
    response = _require_object(value, "response")
    expected = set(FABLE_RESCUE_SCHEMA["required"])
    if set(response) != expected:
        raise LedgerError(
            "Fable rescue response has an invalid field set; expected: "
            + ", ".join(sorted(expected))
        )
    verdict = _required_string(response, "verdict", "response")
    if verdict not in VERDICTS:
        raise LedgerError("invalid Fable rescue verdict")
    _required_string(response, "summary", "response")
    diagnoses = _required_list(response, "root_diagnoses", "response")
    if not 1 <= len(diagnoses) <= 3 or any(item not in DIAGNOSES for item in diagnoses):
        raise LedgerError("response.root_diagnoses must contain one to three known diagnoses")
    if not isinstance(response.get("diagnosis_distinguishable"), bool):
        raise LedgerError("response.diagnosis_distinguishable must be boolean")
    alternatives = _required_list(response, "alternative_hypotheses", "response")
    if len(alternatives) > 3:
        raise LedgerError("response.alternative_hypotheses may contain at most three items")
    experiment = _require_object(
        response.get("discriminating_experiment"), "response.discriminating_experiment"
    )
    for field in ("title", "method", "information_gain_rationale"):
        _required_string(experiment, field, "response.discriminating_experiment")
    _required_list(experiment, "required_evidence", "response.discriminating_experiment")
    _required_list(experiment, "known_answer_controls", "response.discriminating_experiment")
    outcomes = _required_list(response, "expected_outcomes", "response")
    if not outcomes:
        raise LedgerError("response.expected_outcomes must not be empty")
    for index, raw in enumerate(outcomes, 1):
        outcome = _require_object(raw, f"response.expected_outcomes[{index}]")
        for field in ("hypothesis", "observation", "interpretation"):
            _required_string(outcome, field, f"response.expected_outcomes[{index}]")
    for field in ("stop_conditions", "what_would_change_my_mind", "unknowns", "scope_effects"):
        _required_list(response, field, "response")
    _required_string(response, "confidence", "response")
    requested = response.get("requested_artifact")
    if requested is not None and (not isinstance(requested, str) or not requested.strip()):
        raise LedgerError("response.requested_artifact must be null or a non-empty string")
    if verdict == "INSUFFICIENT_PACKET" and requested is None:
        raise LedgerError("INSUFFICIENT_PACKET requires one named requested_artifact")
    if verdict != "INSUFFICIENT_PACKET" and requested is not None:
        raise LedgerError("requested_artifact is only valid with INSUFFICIENT_PACKET")
    return response


def _extract_response(stdout: str) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise LedgerError("Claude CLI did not return valid JSON") from exc
    candidates: list[object] = [envelope]
    if isinstance(envelope, dict):
        candidates.extend(envelope.get(key) for key in ("structured_output", "result") if key in envelope)
    for candidate in candidates:
        if isinstance(candidate, str):
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError:
                continue
        if isinstance(candidate, dict) and "verdict" in candidate:
            model = str(envelope.get("model", "unconfirmed")) if isinstance(envelope, dict) else "unconfirmed"
            effort = str(envelope.get("effort", "unconfirmed")) if isinstance(envelope, dict) else "unconfirmed"
            return validate_response(candidate), model, effort, envelope if isinstance(envelope, dict) else {}
    raise LedgerError("Claude CLI JSON did not include the requested rescue result")


def _config(goal: object) -> tuple[int, int, str, str]:
    metadata = getattr(goal, "metadata", {})
    try:
        max_incidents = int(metadata.get("fable_rescue_max_incidents", "2"))
        rounds = int(metadata.get("fable_rescue_rounds_per_incident", "1"))
    except ValueError as exc:
        raise LedgerError("Fable rescue incident and round limits must be integers") from exc
    if not 1 <= max_incidents <= MAX_INCIDENTS_LIMIT:
        raise LedgerError(f"fable_rescue_max_incidents must be 1-{MAX_INCIDENTS_LIMIT}")
    if rounds != 1:
        raise LedgerError(
            "fable_rescue_rounds_per_incident must be 1; use a delta-gated second incident"
        )
    effort = metadata.get("fable_rescue_effort", "xhigh").strip()
    if effort not in {"high", "xhigh"}:
        raise LedgerError("fable_rescue_effort must be high or xhigh")
    lineage = metadata.get("fable_rescue_lineage", metadata.get("slug", "")).strip()
    if not lineage:
        raise LedgerError("fable_rescue_lineage must not be empty")
    return max_incidents, rounds, effort, lineage


def incident_dir(goal_dir: Path, number: int) -> Path:
    return goal_dir / "evidence" / "fable-rescue" / f"rescue-{number:03d}"


def _goal_lineage_incidents(goal_dir: Path, lineage: str) -> list[Path]:
    project_root = project_root_for(goal_dir)
    found: list[Path] = []
    goals_root = project_root / "docs" / "goals"
    if not goals_root.is_dir():
        return found
    for goal_path in goals_root.glob("*/goal.md"):
        try:
            document = load_document(goal_path)
        except (LedgerError, OSError):
            continue
        candidate_lineage = document.metadata.get(
            "fable_rescue_lineage", document.metadata.get("slug", "")
        ).strip()
        if candidate_lineage != lineage:
            continue
        base = goal_path.parent / "evidence" / "fable-rescue"
        found.extend(path for path in sorted(base.glob("rescue-[0-9][0-9][0-9]")) if path.is_dir())
    return found


def _next_incident(
    goal_dir: Path,
    lineage: str,
    max_incidents: int,
    candidate_digest: str,
) -> tuple[int, Path | None]:
    lineage_incidents = _goal_lineage_incidents(goal_dir, lineage)
    completed = [path for path in lineage_incidents if (path / "response.json").is_file()]
    if len(completed) >= max_incidents:
        raise LedgerError(
            f"Fable rescue lineage {lineage!r} has consumed its {max_incidents}-incident budget"
        )
    local = sorted((goal_dir / "evidence" / "fable-rescue").glob("rescue-[0-9][0-9][0-9]"))
    if local and not (local[-1] / "response.json").is_file():
        unfinished = local[-1]
        stored_candidate = unfinished / "candidate.json"
        if not stored_candidate.is_file() or _sha256(_read_json(stored_candidate)) != candidate_digest:
            raise LedgerError(
                f"unfinished Fable rescue incident exists at {unfinished}; recover or resolve it "
                "before submitting a different candidate"
            )
        number = int(unfinished.name.rsplit("-", 1)[1])
        previous = local[-2] if len(local) > 1 else None
    else:
        number = 1 if not local else max(int(path.name.rsplit("-", 1)[1]) for path in local) + 1
        previous = local[-1] if local else None
    if previous is not None and (previous / "response.json").is_file():
        response = validate_response(_read_json(previous / "response.json"))
        if response["verdict"] in TERMINAL_OWNER_GATES and not (previous / "owner-resolution.json").is_file():
            raise LedgerError(
                f"prior rescue verdict {response['verdict']} is an owner gate; record "
                "owner-resolution.json before another incident"
            )
        if not (previous / "reconciliation.json").is_file() or not (previous / "outcome.json").is_file():
            raise LedgerError(
                "prior rescue must have valid reconciliation.json and outcome.json before "
                "another incident"
            )
    return number, previous


def _request(
    candidate: Mapping[str, Any],
    *,
    incident_number: int,
    lineage: str,
    files: Sequence[Mapping[str, Any]],
    previous: Path | None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "incident": incident_number,
        "lineage": lineage,
        "candidate_digest": _sha256(candidate),
        "question": candidate["question"],
        "trigger": candidate["trigger"],
        "uncertainty_metric": candidate["uncertainty_metric"],
        "verified_facts": candidate["verified_facts"],
        "hypotheses": candidate["hypotheses"],
        "attempts": candidate["attempts"],
        "contradictions": candidate["contradictions"],
        "known_answer_checks": candidate["known_answer_checks"],
        "implementation_checks": candidate["implementation_checks"],
        "current_experiment": candidate.get("current_experiment"),
        "answerability_gap": candidate.get("answerability_gap"),
        "constraints": candidate["constraints"],
        "non_goals": candidate["non_goals"],
        "delta": candidate.get("delta"),
        "files": [{key: item[key] for key in ("path", "bytes", "sha256")} for item in files],
    }
    if previous is not None:
        delta = candidate.get("delta")
        if not isinstance(delta, dict):
            raise LedgerError("incident 2+ requires a structured candidate.delta")
        for field in ("recommendation_attempted", "observed_outcome", "material_change"):
            _required_string(delta, field, "candidate.delta")
        previous_outcome = _read_json(previous / "outcome.json")
        expected_hash = hashlib.sha256((previous / "outcome.json").read_bytes()).hexdigest()
        if delta.get("prior_outcome_sha256") != expected_hash:
            raise LedgerError("candidate.delta.prior_outcome_sha256 is missing or stale")
        request["prior_outcome"] = previous_outcome
    return request


def _prompt(request: Mapping[str, Any], files: Sequence[Mapping[str, Any]]) -> str:
    return f"""Act as Claude Fable 5, an independent scientific rescue peer. Diagnose a hard scientific impasse without implementing, changing scope, or treating your own output as completion evidence. Treat the original plan and any earlier Fable advice as candidate causes, not authorities.

The request JSON is neutral: do not infer a preferred decision. Challenge every hypothesis using its strongest disconfirming evidence. Select one highest-information discriminating experiment and commit to expected observations and interpretations before results are known. Do not loosen thresholds or reinterpret future failures. If diagnoses cannot yet be distinguished, return multiple root_diagnoses with diagnosis_distinguishable false and design the experiment to separate them. Use INSUFFICIENT_PACKET only to request one specifically named existing artifact; use NEEDS_NEW_DATA only when genuinely new evidence must be produced. Return only the requested structured result.

REQUEST JSON
{json.dumps(dict(request), ensure_ascii=False, indent=2, sort_keys=True)}

ALLOW-LISTED EVIDENCE
{context_packet(files)}
"""


def _render_response(
    response: Mapping[str, Any], *, model: str, effort: str, incident: int
) -> bytes:
    lines = [
        "# Claude Fable scientific rescue",
        "",
        f"- **Incident:** {incident}",
        f"- **Verdict:** **{response['verdict']}**",
        f"- **Invoked profile:** `claude-fable-5 {effort}`",
        f"- **Effective profile:** `{model} {effort if model != 'unconfirmed' else 'unconfirmed'}`",
        f"- **Generated:** {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        "- **Authority:** advisory diagnosis only; never completion evidence",
        "",
        "## Summary",
        "",
        str(response["summary"]),
        "",
        "## Root diagnoses",
        "",
        *(f"- `{item}`" for item in response["root_diagnoses"]),
        "",
        "## Highest-information experiment",
        "",
        f"### {response['discriminating_experiment']['title']}",
        "",
        str(response["discriminating_experiment"]["method"]),
        "",
        "## Locked expected outcomes",
        "",
    ]
    for index, outcome in enumerate(response["expected_outcomes"], 1):
        lines.extend(
            (
                f"{index}. **{outcome['hypothesis']}** — {outcome['observation']}",
                f"   Interpretation: {outcome['interpretation']}",
            )
        )
    lines.extend(
        (
            "",
            "## Structured result",
            "",
            "```json",
            json.dumps(dict(response), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        )
    )
    return "\n".join(lines).encode("utf-8")


def _followup_packet(
    goal_dir: Path,
    *,
    incident_number: int,
    supplement: str,
    model: str,
    effort: str,
) -> tuple[Path, list[dict[str, Any]], dict[str, Any], str, dict[str, Any]]:
    target = incident_dir(goal_dir, incident_number)
    response = validate_response(_read_json(target / "response.json"))
    if response["verdict"] != "INSUFFICIENT_PACKET":
        raise LedgerError("a supplemental artifact is only valid after INSUFFICIENT_PACKET")
    if response["requested_artifact"] != supplement:
        raise LedgerError(
            "--supplement must exactly match Fable's requested_artifact: "
            f"{response['requested_artifact']!r}"
        )
    original = _require_object(_read_json(target / "request.json"), "request")
    project_root = project_root_for(goal_dir)
    original_paths = [project_root / str(item["path"]) for item in original.get("files", [])]
    files = collect_transmission_files(
        goal_dir, [*original_paths, project_root / supplement]
    )
    request = dict(original)
    request["supplemental_artifact"] = supplement
    request["followup_of_response_sha256"] = hashlib.sha256(
        (target / "response.json").read_bytes()
    ).hexdigest()
    request["files"] = [
        {key: item[key] for key in ("path", "bytes", "sha256")} for item in files
    ]
    prompt = _prompt(request, files) + (
        "\nThis is the one permitted existing-artifact supplement. Do not return "
        "INSUFFICIENT_PACKET again.\n"
    )
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    manifest = build_transmission_manifest(
        files=files,
        prompt_sha256=prompt_sha,
        model=model,
        effort=effort,
        purpose="bounded Claude Fable scientific rescue artifact supplement",
        tools=(),
        extra={"incident": incident_number, "followup": 1, "supplement": supplement},
    )
    return target, files, request, prompt, manifest


def _record_reconciliation(incident: Path, source: Path) -> None:
    response = validate_response(_read_json(incident / "response.json"))
    supplied = _require_object(_read_json(source), "reconciliation")
    if supplied.get("schema_version") != SCHEMA_VERSION:
        raise LedgerError(f"reconciliation.schema_version must be {SCHEMA_VERSION}")
    claims = _required_list(supplied, "claims", "reconciliation")
    for index, raw in enumerate(claims, 1):
        claim = _require_object(raw, f"reconciliation.claims[{index}]")
        claim_type = _required_string(claim, "type", f"reconciliation.claims[{index}]")
        if claim_type not in {"fact_check", "diagnostic_judgment", "recommendation"}:
            raise LedgerError("reconciliation claim type is invalid")
        decision = _required_string(claim, "decision", f"reconciliation.claims[{index}]")
        if decision not in {"accepted", "rejected", "deferred"}:
            raise LedgerError("reconciliation claim decision is invalid")
        _required_string(claim, "rationale", f"reconciliation.claims[{index}]")
        if claim_type == "diagnostic_judgment" and decision == "accepted":
            raise LedgerError("diagnostic judgments must remain deferred until outcome evidence")
        if decision == "rejected":
            _required_string(claim, "counter_evidence_sha256", f"reconciliation.claims[{index}]")
    stored = dict(supplied)
    stored["response_sha256"] = hashlib.sha256((incident / "response.json").read_bytes()).hexdigest()
    stored["prediction_sha256"] = _sha256(response["expected_outcomes"])
    atomic_write_json(incident / "reconciliation.json", stored)


def _record_outcome(incident: Path, source: Path) -> None:
    reconciliation = _require_object(_read_json(incident / "reconciliation.json"), "reconciliation")
    response = validate_response(_read_json(incident / "response.json"))
    expected_prediction = _sha256(response["expected_outcomes"])
    if reconciliation.get("prediction_sha256") != expected_prediction:
        raise LedgerError("locked prediction hash no longer matches response.expected_outcomes")
    supplied = _require_object(_read_json(source), "outcome")
    if supplied.get("schema_version") != SCHEMA_VERSION:
        raise LedgerError(f"outcome.schema_version must be {SCHEMA_VERSION}")
    _required_string(supplied, "observed_result", "outcome")
    matched = supplied.get("matched_prediction")
    if matched != "none" and not (
        isinstance(matched, int) and 1 <= matched <= len(response["expected_outcomes"])
    ):
        raise LedgerError("outcome.matched_prediction must be a 1-based index or 'none'")
    _required_string(supplied, "hypothesis_update", "outcome")
    evidence_path = _required_string(supplied, "evidence_path", "outcome")
    goal_dir = incident.parents[2]
    project_root = project_root_for(goal_dir)
    evidence = project_root / evidence_path
    try:
        evidence.resolve(strict=True).relative_to(project_root)
    except (FileNotFoundError, ValueError) as exc:
        raise LedgerError("outcome.evidence_path is missing or escapes the repository") from exc
    actual = hashlib.sha256(evidence.read_bytes()).hexdigest()
    if supplied.get("evidence_sha256") != actual:
        raise LedgerError("outcome.evidence_sha256 is missing or stale")
    stored = dict(supplied)
    stored["prediction_sha256"] = expected_prediction
    atomic_write_json(incident / "outcome.json", stored)


def _record_owner_resolution(incident: Path, source: Path) -> None:
    response = validate_response(_read_json(incident / "response.json"))
    if response["verdict"] not in TERMINAL_OWNER_GATES:
        raise LedgerError("owner resolution is only valid for a terminal rescue owner gate")
    supplied = _require_object(_read_json(source), "owner_resolution")
    if supplied.get("schema_version") != SCHEMA_VERSION:
        raise LedgerError(f"owner_resolution.schema_version must be {SCHEMA_VERSION}")
    owner = _required_string(supplied, "owner", "owner_resolution")
    decision = _required_string(supplied, "decision", "owner_resolution")
    rationale = _required_string(supplied, "rationale", "owner_resolution")
    allowed = (
        {"new_data_authorized", "scope_expanded", "accept_data_gate"}
        if response["verdict"] == "NEEDS_NEW_DATA"
        else {"scope_expanded", "accept_unresolvable", "close_negative_result"}
    )
    if decision not in allowed:
        raise LedgerError(
            f"owner_resolution.decision for {response['verdict']} must be one of: "
            + ", ".join(sorted(allowed))
        )
    atomic_write_json(
        incident / "owner-resolution.json",
        {
            "schema_version": SCHEMA_VERSION,
            "verdict": response["verdict"],
            "response_sha256": hashlib.sha256(
                (incident / "response.json").read_bytes()
            ).hexdigest(),
            "owner": owner,
            "decision": decision,
            "rationale": rationale,
        },
    )


def fable_rescue_problems(goal_dir: Path, *, require_closed: bool = False) -> list[str]:
    goal_dir = goal_dir.resolve()
    try:
        goal, choices = load_closeout_options(goal_dir)
        if FABLE_RESCUE_OPTION not in choices or choices[FABLE_RESCUE_OPTION] != "yes":
            return []
        _config(goal)
    except LedgerError as exc:
        return [str(exc)]
    problems: list[str] = []
    base = goal_dir / "evidence" / "fable-rescue"
    for incident in sorted(base.glob("rescue-[0-9][0-9][0-9]")) if base.is_dir() else ():
        try:
            request = _require_object(_read_json(incident / "request.json"), "request")
            response = validate_response(_read_json(incident / "response.json"))
            if request.get("schema_version") != SCHEMA_VERSION:
                raise LedgerError(f"{incident / 'request.json'} has unsupported schema_version")
            reconciliation_path = incident / "reconciliation.json"
            outcome_path = incident / "outcome.json"
            if reconciliation_path.is_file():
                reconciliation = _require_object(_read_json(reconciliation_path), "reconciliation")
                response_hash = hashlib.sha256((incident / "response.json").read_bytes()).hexdigest()
                if reconciliation.get("response_sha256") != response_hash:
                    raise LedgerError(f"stale response hash in {reconciliation_path}")
                if reconciliation.get("prediction_sha256") != _sha256(response["expected_outcomes"]):
                    raise LedgerError(f"stale prediction hash in {reconciliation_path}")
            elif require_closed:
                raise LedgerError(f"missing rescue reconciliation: {reconciliation_path}")
            if outcome_path.is_file():
                outcome = _require_object(_read_json(outcome_path), "outcome")
                if outcome.get("prediction_sha256") != _sha256(response["expected_outcomes"]):
                    raise LedgerError(f"stale prediction hash in {outcome_path}")
            elif require_closed and response["verdict"] not in TERMINAL_OWNER_GATES:
                raise LedgerError(f"missing rescue outcome: {outcome_path}")
            if require_closed and response["verdict"] in TERMINAL_OWNER_GATES:
                if not (incident / "owner-resolution.json").is_file():
                    raise LedgerError(f"unresolved rescue owner gate: {incident}")
            if (incident / "owner-resolution.json").is_file():
                resolution = _require_object(
                    _read_json(incident / "owner-resolution.json"), "owner_resolution"
                )
                response_hash = hashlib.sha256(
                    (incident / "response.json").read_bytes()
                ).hexdigest()
                if resolution.get("response_sha256") != response_hash:
                    raise LedgerError(f"stale response hash in {incident / 'owner-resolution.json'}")
        except LedgerError as exc:
            problems.append(str(exc))
    return problems


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded Claude Fable scientific rescue.")
    parser.add_argument("goal_dir", type=Path)
    parser.add_argument("--candidate", type=Path, help="Structured incident-candidate JSON.")
    parser.add_argument("--claude-bin", default=os.environ.get("FABLE_CLAUDE_BIN", "claude"))
    parser.add_argument("--model", default=os.environ.get("FABLE_MODEL", "claude-fable-5"))
    parser.add_argument("--effort", choices=("high", "xhigh"), default=None)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument(
        "--transport-attempts",
        type=int,
        default=1,
        help="Compatibility option; must be 1 because automatic resubmission is forbidden.",
    )
    parser.add_argument("--prepare-transmission", action="store_true")
    parser.add_argument("--approve-transmission", metavar="SHA256")
    parser.add_argument(
        "--supplement",
        help="One repository-relative artifact exactly requested by INSUFFICIENT_PACKET.",
    )
    parser.add_argument("--reconcile", type=Path, help="Record typed reconciliation JSON.")
    parser.add_argument("--record-outcome", type=Path, help="Record outcome JSON against locked predictions.")
    parser.add_argument(
        "--record-owner-resolution",
        type=Path,
        help="Record an explicit owner decision for a terminal rescue verdict.",
    )
    parser.add_argument("--incident", type=int, help="Incident number for reconciliation/outcome modes.")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        goal_dir = args.goal_dir.expanduser().resolve()
        project_root = project_root_for(goal_dir)
        goal, choices = load_closeout_options(goal_dir)
        if choices.get(FABLE_RESCUE_OPTION) != "yes":
            print("Claude Fable scientific rescue is not selected.")
            return 0
        max_incidents, _, configured_effort, lineage = _config(goal)
        if args.check:
            problems = fable_rescue_problems(
                goal_dir, require_closed=goal.metadata.get("status") == "complete"
            )
            if problems:
                for problem in problems:
                    print(f"error: {problem}", file=sys.stderr)
                return 1
            print("Fable scientific rescue artifacts are valid.")
            return 0
        if args.reconcile or args.record_outcome or args.record_owner_resolution:
            if args.incident is None or args.incident < 1:
                raise LedgerError("--incident is required for reconciliation and outcome modes")
            target = incident_dir(goal_dir, args.incident)
            if args.reconcile:
                _record_reconciliation(target, args.reconcile.expanduser().resolve())
                print(f"Wrote: {(target / 'reconciliation.json').relative_to(project_root)}")
            if args.record_outcome:
                _record_outcome(target, args.record_outcome.expanduser().resolve())
                print(f"Wrote: {(target / 'outcome.json').relative_to(project_root)}")
            if args.record_owner_resolution:
                _record_owner_resolution(
                    target, args.record_owner_resolution.expanduser().resolve()
                )
                print(
                    f"Wrote: {(target / 'owner-resolution.json').relative_to(project_root)}"
                )
            return 0
        if args.supplement is not None:
            if args.incident is None or args.incident < 1:
                raise LedgerError("--incident is required with --supplement")
            supplement_path = Path(args.supplement)
            if supplement_path.is_absolute() or ".." in supplement_path.parts:
                raise LedgerError("--supplement must be a repository-relative path")
            effort = args.effort or configured_effort
            target, _, request, prompt, manifest = _followup_packet(
                goal_dir,
                incident_number=args.incident,
                supplement=supplement_path.as_posix(),
                model=args.model,
                effort=effort,
            )
            if args.prepare_transmission:
                print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
                return 0
            if args.approve_transmission != manifest["approval_digest"]:
                raise LedgerError(
                    "exact Fable rescue supplement approval is missing or stale; prepare "
                    "the transmission and pass its approval_digest"
                )
            claude_bin = shutil.which(args.claude_bin)
            if claude_bin is None:
                raise LedgerError(f"Claude Code executable not found: {args.claude_bin}")
            prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            command = [
                claude_bin,
                "--print",
                "--model",
                args.model,
                "--effort",
                effort,
                "--safe-mode",
                "--tools",
                "",
                "--permission-mode",
                "dontAsk",
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(FABLE_RESCUE_SCHEMA, separators=(",", ":")),
                "--no-session-persistence",
                prompt,
            ]
            environment = os.environ.copy()
            for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "NODE_OPTIONS"):
                environment.pop(key, None)
            atomic_write(
                target / "response-initial.json", (target / "response.json").read_bytes()
            )
            atomic_write(
                target / "response-initial.md", (target / "response.md").read_bytes()
            )
            atomic_write_json(target / "followup-request.json", request)
            atomic_write_json(target / "followup-transmission-manifest.json", manifest)
            result = run_claude_durable(
                command,
                cwd=project_root,
                env=environment,
                transport_dir=target / "transport-followup-1",
                invocation_id=invocation_digest(
                    command=command,
                    prompt_sha256=prompt_sha,
                    approval_digest=str(manifest["approval_digest"]),
                ),
                timeout_seconds=args.timeout_seconds,
                max_attempts=args.transport_attempts,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
                raise LedgerError(
                    f"Claude CLI supplement failed with exit {result.returncode}: {detail}; "
                    f"durable diagnostics: {target / 'transport-followup-1'}"
                )
            response, effective_model, _, envelope = _extract_response(result.stdout)
            if response["verdict"] == "INSUFFICIENT_PACKET":
                raise LedgerError(
                    "Fable requested a second packet supplement; the bounded follow-up limit is one"
                )
            atomic_write_json(target / "response.json", response)
            atomic_write(
                target / "response.md",
                _render_response(
                    response,
                    model=effective_model,
                    effort=effort,
                    incident=args.incident,
                ),
            )
            atomic_write_json(
                target / "usage-followup.json",
                {
                    "schema_version": 1,
                    "duration_ms": envelope.get("duration_ms"),
                    "usage": envelope.get("usage"),
                    "transport_attempt": result.attempt,
                    "recovered_without_resubmission": result.recovered,
                },
            )
            note = " (recovered without resubmission)" if result.recovered else ""
            print(f"Wrote: {(target / 'response.md').relative_to(project_root)}{note}")
            return 0
        if args.candidate is None:
            raise LedgerError("--candidate is required to prepare or run a rescue")
        candidate = validate_candidate(_read_json(args.candidate.expanduser().resolve()), goal_dir=goal_dir)
        candidate_digest = _sha256(candidate)
        number, previous = _next_incident(
            goal_dir, lineage, max_incidents, candidate_digest
        )
        requested_paths = [project_root / path for path in candidate["evidence_files"]]
        files = collect_transmission_files(goal_dir, requested_paths)
        request = _request(
            candidate,
            incident_number=number,
            lineage=lineage,
            files=files,
            previous=previous,
        )
        prompt = _prompt(request, files)
        effort = args.effort or configured_effort
        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        manifest = build_transmission_manifest(
            files=files,
            prompt_sha256=prompt_sha,
            model=args.model,
            effort=effort,
            purpose="read-only Claude Fable scientific rescue",
            tools=(),
            extra={"incident": number, "lineage": lineage, "candidate_digest": candidate_digest},
        )
        if args.prepare_transmission:
            print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.approve_transmission != manifest["approval_digest"]:
            raise LedgerError(
                "exact Fable rescue transmission approval is missing or stale; run with "
                "--prepare-transmission and pass its approval_digest"
            )
        claude_bin = shutil.which(args.claude_bin)
        if claude_bin is None:
            raise LedgerError(f"Claude Code executable not found: {args.claude_bin}")
        target = incident_dir(goal_dir, number)
        target.mkdir(parents=True, exist_ok=True)
        atomic_write_json(target / "candidate.json", candidate)
        atomic_write_json(target / "request.json", request)
        atomic_write_json(target / "transmission-manifest.json", manifest)
        command = [
            claude_bin,
            "--print",
            "--model",
            args.model,
            "--effort",
            effort,
            "--safe-mode",
            "--tools",
            "",
            "--permission-mode",
            "dontAsk",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(FABLE_RESCUE_SCHEMA, separators=(",", ":")),
            "--no-session-persistence",
            prompt,
        ]
        environment = os.environ.copy()
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "NODE_OPTIONS"):
            environment.pop(key, None)
        result = run_claude_durable(
            command,
            cwd=project_root,
            env=environment,
            transport_dir=target / "transport",
            invocation_id=invocation_digest(
                command=command,
                prompt_sha256=prompt_sha,
                approval_digest=str(manifest["approval_digest"]),
            ),
            timeout_seconds=args.timeout_seconds,
            max_attempts=args.transport_attempts,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
            raise LedgerError(
                f"Claude CLI failed with exit {result.returncode}: {detail}; durable diagnostics: "
                f"{target / 'transport'}"
            )
        response, effective_model, _, envelope = _extract_response(result.stdout)
        atomic_write_json(target / "response.json", response)
        atomic_write_json(
            target / "usage.json",
            {
                "schema_version": 1,
                "duration_ms": envelope.get("duration_ms"),
                "duration_api_ms": envelope.get("duration_api_ms"),
                "cost_usd": envelope.get("total_cost_usd"),
                "usage": envelope.get("usage"),
                "transport_attempt": result.attempt,
                "recovered_without_resubmission": result.recovered,
            },
        )
        atomic_write(
            target / "response.md",
            _render_response(
                response, model=effective_model, effort=effort, incident=number
            ),
        )
        note = " (recovered without resubmission)" if result.recovered else ""
        print(f"Wrote: {(target / 'response.md').relative_to(project_root)}{note}")
        return 0
    except (LedgerError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

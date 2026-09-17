from __future__ import annotations

import json
import re

from .models import (
    AdCopyOutput,
    Borough,
    ClassificationOutput,
    DeterministicAnalysis,
    EvidencePacket,
    StrategyOutput,
)
from .normalization import normalize_category


class EvidenceValidationError(ValueError):
    pass


def _check_ids(label: str, referenced: set[str], allowed: set[str]) -> None:
    unknown = referenced - allowed
    if unknown:
        raise EvidenceValidationError(f"{label} references unknown IDs: {sorted(unknown)}")


def validate_classification(
    output: ClassificationOutput,
    packet: EvidencePacket,
    taxonomy: list[str] | None = None,
) -> None:
    expected = {record.record_id for record in packet.competitors}
    classified = {item.record_id for item in output.classifications}
    unclassified = set(output.unclassified_record_ids)
    if classified & unclassified:
        raise EvidenceValidationError("records cannot be both classified and unclassified")
    if classified | unclassified != expected:
        missing = expected - (classified | unclassified)
        extra = (classified | unclassified) - expected
        raise EvidenceValidationError(
            f"classification coverage mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    if len(classified) != len(output.classifications):
        raise EvidenceValidationError("classification output contains duplicate record IDs")
    if taxonomy is not None:
        allowed_categories = {item.casefold() for item in taxonomy}
        unknown_categories = {
            category
            for item in output.classifications
            for category in [item.canonical_category, *item.secondary_categories]
            if category.casefold() not in allowed_categories
        }
        if unknown_categories:
            raise EvidenceValidationError(
                f"classification used categories outside the taxonomy: {sorted(unknown_categories)}"
            )


def _opportunity_evidence(
    deterministic: DeterministicAnalysis,
) -> dict[tuple[Borough, str], set[str]]:
    return {
        (item.borough, normalize_category(item.category)): set(item.evidence_ids)
        for item in deterministic.top_underserved_categories
    }


def _scoped_evidence(
    packet: EvidencePacket,
) -> dict[tuple[Borough, str], dict[str, set[str]]]:
    scoped: dict[tuple[Borough, str], dict[str, set[str]]] = {}

    def bucket(key: tuple[Borough, str]) -> dict[str, set[str]]:
        return scoped.setdefault(
            key,
            {"demand": set(), "supply": set(), "competitor": set()},
        )

    for signal in packet.demand_signals:
        bucket((signal.borough, normalize_category(signal.category)))["demand"].add(signal.signal_id)
    for coverage in packet.supply_coverage:
        bucket((coverage.borough, normalize_category(coverage.category)))["supply"].add(coverage.coverage_id)
    for record in packet.competitors:
        for category in {record.primary_category, *record.secondary_categories}:
            bucket((record.borough, normalize_category(category)))["competitor"].add(record.record_id)
    return scoped


def _validate_typed_claim(
    label: str,
    claim_type: str,
    referenced: set[str],
    evidence: dict[str, set[str]],
) -> None:
    if claim_type == "combined":
        allowed = evidence["demand"] | evidence["supply"] | evidence["competitor"]
        _check_ids(label, referenced, allowed)
        if not (referenced & evidence["demand"] and referenced & evidence["supply"]):
            raise EvidenceValidationError(f"{label} with combined claim type requires both demand and supply evidence")
        return
    _check_ids(label, referenced, evidence[claim_type])


def validate_strategy(
    output: StrategyOutput,
    packet: EvidencePacket,
    deterministic: DeterministicAnalysis,
) -> None:
    if output.top_underserved_categories != deterministic.top_underserved_categories:
        raise EvidenceValidationError("model changed deterministic category findings")
    if output.priority_borough != deterministic.priority_borough:
        raise EvidenceValidationError("model changed deterministic priority borough")
    if output.priority_borough_status != deterministic.priority_borough_status:
        raise EvidenceValidationError("model changed priority-borough evidence status")
    if output.priority_borough_reasoning != deterministic.priority_borough_reasoning:
        raise EvidenceValidationError("model changed priority-borough reasoning")

    record_ids = {record.record_id for record in packet.competitors}
    signal_ids = {signal.signal_id for signal in packet.demand_signals}
    coverage_ids = {item.coverage_id for item in packet.supply_coverage}
    allowed_evidence = record_ids | signal_ids | coverage_ids
    scoped = _opportunity_evidence(deterministic)
    typed_scoped = _scoped_evidence(packet)

    for category in output.top_underserved_categories:
        _check_ids("category opportunity", set(category.evidence_ids), allowed_evidence)
    for angle in output.positioning_angles:
        key = (angle.borough, normalize_category(angle.category))
        if key not in scoped:
            raise EvidenceValidationError("positioning angle is outside supported category/borough findings")
        referenced = set(angle.supporting_evidence_ids)
        _check_ids("positioning angle", referenced, scoped[key])
        _validate_typed_claim(
            "positioning angle",
            angle.claim_type,
            referenced,
            typed_scoped.get(key, {"demand": set(), "supply": set(), "competitor": set()}),
        )
    for practice in output.competitor_practices:
        key = (practice.borough, normalize_category(practice.category))
        if key not in scoped:
            raise EvidenceValidationError("competitor practice is outside supported category/borough findings")
        practice_records = set(practice.competitor_record_ids)
        _check_ids(
            "competitor practice",
            practice_records,
            typed_scoped.get(key, {"competitor": set()})["competitor"],
        )
        if set(practice.evidence_ids) != practice_records:
            raise EvidenceValidationError(
                "competitor practice evidence IDs must exactly match its competitor record IDs"
            )
        observed_values = {
            json.dumps(
                getattr(record, practice.observed_field),
                ensure_ascii=False,
                sort_keys=True,
            )
            for record in packet.competitors
            if record.record_id in practice_records
        }
        if "null" in observed_values:
            raise EvidenceValidationError(f"competitor practice cites missing {practice.observed_field} data")
        if observed_values != {practice.observed_value}:
            raise EvidenceValidationError(
                "competitor practice observed value does not exactly match the cited record field"
            )
    for action in output.next_actions:
        key = (action.borough, normalize_category(action.category))
        if key not in scoped:
            raise EvidenceValidationError("next action is outside supported category/borough findings")
        referenced = set(action.evidence_ids)
        _check_ids("next action", referenced, scoped[key])
        _validate_typed_claim(
            "next action",
            action.claim_type,
            referenced,
            typed_scoped.get(key, {"demand": set(), "supply": set(), "competitor": set()}),
        )


def validate_copy(
    output: AdCopyOutput,
    packet: EvidencePacket,
    deterministic: DeterministicAnalysis,
    *,
    category: str,
    borough: Borough,
) -> None:
    matches = [
        item
        for item in deterministic.top_underserved_categories
        if item.borough == borough and normalize_category(item.category) == normalize_category(category)
    ]
    if len(matches) != 1:
        raise EvidenceValidationError("ad copy requires one supported deterministic category/borough finding")
    approved_facts = {
        fact.fact_id: fact
        for fact in packet.business.approved_copy_facts
        if (fact.borough is None or fact.borough == borough)
        and (fact.category is None or normalize_category(fact.category) == normalize_category(category))
    }
    if not approved_facts:
        raise EvidenceValidationError("ad copy requires approved copy facts for the selected category and borough")
    _check_ids("ad copy", set(output.evidence_ids), set(approved_facts))
    if output.borough != borough:
        raise EvidenceValidationError("ad copy changed the selected borough")
    if normalize_category(output.category) != normalize_category(category):
        raise EvidenceValidationError("ad copy changed the selected category")
    combined = " ".join(
        [*output.headlines, *output.descriptions, output.landing_page_intro, output.cta_line]
    ).casefold()
    violations = [claim for claim in packet.business.prohibited_claims if claim.casefold() in combined]
    if violations:
        raise EvidenceValidationError(f"ad copy contains prohibited claims: {sorted(violations)}")
    missing_fact_text = [
        fact_id for fact_id in output.evidence_ids if approved_facts[fact_id].text.casefold() not in combined
    ]
    if missing_fact_text:
        raise EvidenceValidationError(
            "ad copy cited approved facts without using their exact text: " + ", ".join(sorted(missing_fact_text))
        )
    unapproved_text = combined
    for fact_id in output.evidence_ids:
        unapproved_text = unapproved_text.replace(approved_facts[fact_id].text.casefold(), " ")
    unsupported_patterns = {
        "guaranteed": r"\bguarantee(?:d|s)?\b",
        "best": r"\bbest\b",
        "number one": r"(?:#\s*1|\bnumber\s+one\b)",
        "free": r"\bfree\b",
        "same-day": r"\bsame[ -]?day\b",
        "popularity or quality": r"\b(?:popular|trusted|premium|quality|leading|favorite)\b",
        "speed or availability": r"\b(?:fast|quick|instant|in[ -]?stock|available now)\b",
        "numeric claim": r"(?:\$|\b\d+(?:\.\d+)?%?\b)",
    }
    unsupported = [label for label, pattern in unsupported_patterns.items() if re.search(pattern, unapproved_text)]
    if unsupported:
        raise EvidenceValidationError(
            "ad copy contains claims that require separate offer evidence: " + ", ".join(unsupported)
        )

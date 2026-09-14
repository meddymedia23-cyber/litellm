from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import Field

from .analysis import OpportunityAnalyzer
from .config import AnalysisSettings
from .models import (
    Borough,
    BusinessProfile,
    CompetitorRecord,
    DecisionStatus,
    DemandSignal,
    EvidencePacket,
    EvidenceSource,
    EvidenceStatus,
    EvidenceUse,
    SourceType,
    StrictModel,
    SupplyCoverage,
)
from .normalization import normalize_borough, normalize_category, stable_id


class EvalExpectation(StrictModel):
    supported: list[str] = Field(default_factory=list)
    insufficient: list[str] = Field(default_factory=list)
    top: str | None = None
    top_count: int | None = Field(default=None, ge=0, le=5)
    priority_borough: Borough | None = None
    priority_status: DecisionStatus


class EvalObservation(StrictModel):
    category: str
    borough: Borough
    demand: float | None = Field(default=None, ge=0)
    demand_metric: str = "monthly_searches"
    demand_confidence: float = Field(default=1.0, ge=0, le=1)
    demand_age_days: int = Field(default=1, ge=0)
    demand_source_status: EvidenceStatus = EvidenceStatus.VERIFIED
    additional_demand_metric: str | None = None
    supply: int | None = Field(default=None, ge=0)
    supply_age_days: int = Field(default=1, ge=0)
    supply_source_status: EvidenceStatus = EvidenceStatus.VERIFIED
    query_completed: bool = True
    ratings: list[float] = Field(default_factory=list)


class EvalCase(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    description: str
    now: datetime
    settings: dict[str, Any] = Field(default_factory=dict)
    excluded_categories: list[str] = Field(default_factory=list)
    observations: list[EvalObservation] = Field(min_length=1)
    expected: EvalExpectation


class CaseResult(StrictModel):
    case_id: str
    passed: bool
    failures: list[str]
    supported: list[str]
    insufficient: list[str]
    top: str | None
    top_count: int
    priority_borough: Borough | None
    priority_status: DecisionStatus


class EvalReport(StrictModel):
    suite: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    cases: list[CaseResult]


def _selector(borough: Borough, category: str) -> str:
    return f"{borough.value}|{normalize_category(category)}"


def _build_packet(case: EvalCase) -> EvidencePacket:
    sources: list[EvidenceSource] = []
    signals: list[DemandSignal] = []
    coverage: list[SupplyCoverage] = []
    competitors: list[CompetitorRecord] = []
    candidates = sorted({normalize_category(item.category) for item in case.observations})

    for index, observation in enumerate(case.observations):
        category = normalize_category(observation.category)
        borough = normalize_borough(observation.borough)
        if observation.demand is not None:
            demand_source_id = f"eval-demand:{case.case_id}:{index}"
            sources.append(
                EvidenceSource(
                    source_id=demand_source_id,
                    source_type=SourceType.USER_SUPPLIED,
                    title=f"Evaluation demand source {index}",
                    url=f"https://example.test/{case.case_id}/demand/{index}",
                    retrieved_at=case.now,
                    status=observation.demand_source_status,
                    evidence_use=EvidenceUse.EVALUATION,
                    decision_eligible=False,
                )
            )
            end = case.now - timedelta(days=observation.demand_age_days)
            signals.append(
                DemandSignal(
                    signal_id=f"signal:{case.case_id}:{index}",
                    category=category,
                    borough=borough,
                    metric=observation.demand_metric,
                    value=observation.demand,
                    period_start=end - timedelta(days=30),
                    period_end=end,
                    source_id=demand_source_id,
                    confidence=observation.demand_confidence,
                )
            )
            if observation.additional_demand_metric:
                signals.append(
                    DemandSignal(
                        signal_id=f"signal:{case.case_id}:{index}:additional",
                        category=category,
                        borough=borough,
                        metric=observation.additional_demand_metric,
                        value=observation.demand,
                        period_start=end - timedelta(days=30),
                        period_end=end,
                        source_id=demand_source_id,
                        confidence=observation.demand_confidence,
                    )
                )
        if observation.supply is not None:
            supply_source_id = f"eval-supply:{case.case_id}:{index}"
            sources.append(
                EvidenceSource(
                    source_id=supply_source_id,
                    source_type=SourceType.USER_SUPPLIED,
                    title=f"Evaluation supply source {index}",
                    url=f"https://example.test/{case.case_id}/supply/{index}",
                    retrieved_at=case.now,
                    status=observation.supply_source_status,
                    evidence_use=EvidenceUse.EVALUATION,
                    decision_eligible=False,
                )
            )
            observed_at = case.now - timedelta(days=observation.supply_age_days)
            coverage.append(
                SupplyCoverage(
                    coverage_id=f"coverage:{case.case_id}:{index}",
                    category=category,
                    borough=borough,
                    query_completed=observation.query_completed,
                    result_count=observation.supply,
                    source_id=supply_source_id,
                    observed_at=observed_at,
                    query=f"Evaluation query for {category} in {borough.value}",
                )
            )
            for rating_index, rating in enumerate(observation.ratings):
                competitors.append(
                    CompetitorRecord(
                        record_id=f"competitor:{case.case_id}:{index}:{rating_index}",
                        competitor_name=f"Evaluation Competitor {rating_index}",
                        borough=borough,
                        primary_category=category,
                        rating=rating,
                        source_id=supply_source_id,
                        source_url=f"https://example.test/{case.case_id}/competitor/{index}/{rating_index}",
                        observed_at=observed_at,
                    )
                )

    return EvidencePacket(
        run_id=stable_id("eval-run", case.case_id),
        created_at=case.now,
        business=BusinessProfile(
            product_service="Category discovery evaluation",
            excluded_categories=case.excluded_categories,
        ),
        sources=sources,
        competitors=competitors,
        demand_signals=signals,
        supply_coverage=coverage,
        candidate_categories=candidates,
    )


def evaluate_case(case: EvalCase) -> CaseResult:
    settings = AnalysisSettings.model_validate(case.settings)
    result = OpportunityAnalyzer(settings).analyze(_build_packet(case), now=case.now, allow_evaluation=True)
    supported = sorted(
        _selector(item.borough, item.category)
        for item in result.opportunities
        if item.status == DecisionStatus.SUPPORTED
    )
    insufficient = sorted(
        _selector(item.borough, item.category)
        for item in result.opportunities
        if item.status == DecisionStatus.INSUFFICIENT_DATA
    )
    top = (
        _selector(
            result.top_underserved_categories[0].borough,
            result.top_underserved_categories[0].category,
        )
        if result.top_underserved_categories
        else None
    )
    failures: list[str] = []
    for selector in case.expected.supported:
        if selector not in supported:
            failures.append(f"expected supported result missing: {selector}")
    for selector in case.expected.insufficient:
        if selector not in insufficient:
            failures.append(f"expected insufficient result missing: {selector}")
    if case.expected.top != top:
        failures.append(f"expected top={case.expected.top!r}, received {top!r}")
    if case.expected.top_count is not None and case.expected.top_count != len(result.top_underserved_categories):
        failures.append(
            f"expected top_count={case.expected.top_count}, received {len(result.top_underserved_categories)}"
        )
    if case.expected.priority_borough != result.priority_borough:
        failures.append(
            f"expected priority_borough={case.expected.priority_borough}, received {result.priority_borough}"
        )
    if case.expected.priority_status != result.priority_borough_status:
        failures.append(
            f"expected priority_status={case.expected.priority_status}, received {result.priority_borough_status}"
        )
    return CaseResult(
        case_id=case.case_id,
        passed=not failures,
        failures=failures,
        supported=supported,
        insufficient=insufficient,
        top=top,
        top_count=len(result.top_underserved_categories),
        priority_borough=result.priority_borough,
        priority_status=result.priority_borough_status,
    )


def run_eval_suite(path: str | Path) -> EvalReport:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"evaluation suite not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid evaluation JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise TypeError("evaluation suite must contain a cases array")
    cases = [EvalCase.model_validate(item) for item in payload["cases"]]
    if len(cases) != 20:
        raise ValueError(f"evaluation suite must contain exactly 20 cases; found {len(cases)}")
    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("evaluation case IDs must be unique")
    results = [evaluate_case(case) for case in cases]
    passed = sum(result.passed for result in results)
    total = len(results)
    return EvalReport(
        suite=str(payload.get("suite") or source.stem),
        total=total,
        passed=passed,
        failed=total - passed,
        pass_rate=round(passed / total, 4),
        cases=results,
    )

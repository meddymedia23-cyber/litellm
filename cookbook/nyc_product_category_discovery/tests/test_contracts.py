from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypeVar

import pytest
from market_intel.analysis import OpportunityAnalyzer
from market_intel.cli import execute_args
from market_intel.config import AnalysisSettings, AppConfig
from market_intel.llm_client import ModelStageError, StageResult, StructuredModelClient
from market_intel.models import (
    AdCopyOutput,
    ApprovedCopyFact,
    Borough,
    BusinessProfile,
    CompetitorPractice,
    CompetitorRecord,
    ConsensusVote,
    DecisionStatus,
    DemandSignal,
    EvidencePacket,
    EvidenceSource,
    EvidenceStatus,
    EvidenceUse,
    RecommendedAction,
    SourceType,
    StrategyOutput,
    SupplyCoverage,
)
from market_intel.sources import (
    CsvImporter,
    _apply_overture_category_mapping,
    _overture_coverage_counts,
    verify_http_sources,
)
from market_intel.validation import EvidenceValidationError, validate_copy, validate_strategy
from market_intel.workflow import MarketIntelligenceWorkflow, WorkflowError, build_evidence_packet
from pydantic import BaseModel, ValidationError

NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Observation:
    borough: Borough
    category: str
    metric: str = "monthly_searches"
    demand: float = 100
    supply: int = 1


def _source(source_id: str, title: str) -> EvidenceSource:
    return EvidenceSource(
        source_id=source_id,
        source_type=SourceType.USER_SUPPLIED,
        title=title,
        url="https://example.com/evidence",
        retrieved_at=NOW,
        status=EvidenceStatus.VERIFIED,
        evidence_use=EvidenceUse.PRODUCTION,
        decision_eligible=True,
        provider_sharing_allowed=False,
    )


def _packet(
    observations: tuple[Observation, ...],
    *,
    competitors: tuple[CompetitorRecord, ...] = (),
    approved_copy_facts: tuple[ApprovedCopyFact, ...] = (),
) -> EvidencePacket:
    sources = [
        source
        for index, _ in enumerate(observations)
        for source in (
            _source(f"demand:{index}", f"Demand source {index}"),
            _source(f"supply:{index}", f"Supply source {index}"),
        )
    ]
    signals = [
        DemandSignal(
            signal_id=f"signal:{index}",
            category=item.category,
            borough=item.borough,
            metric=item.metric,
            value=item.demand,
            period_start=NOW - timedelta(days=30),
            period_end=NOW,
            source_id=f"demand:{index}",
        )
        for index, item in enumerate(observations)
    ]
    coverage = [
        SupplyCoverage(
            coverage_id=f"coverage:{index}",
            category=item.category,
            borough=item.borough,
            query_completed=True,
            result_count=item.supply,
            source_id=f"supply:{index}",
            observed_at=NOW,
            query=f"Complete {item.category} query in {item.borough.value}",
        )
        for index, item in enumerate(observations)
    ]
    return EvidencePacket(
        run_id="run:contract-tests",
        created_at=NOW,
        business=BusinessProfile(
            product_service="Contract test business",
            primary_boroughs=list(dict.fromkeys(item.borough for item in observations)),
            approved_copy_facts=list(approved_copy_facts),
        ),
        sources=sources,
        competitors=list(competitors),
        demand_signals=signals,
        supply_coverage=coverage,
        candidate_categories=sorted({item.category for item in observations}),
    )


def _analysis(packet: EvidencePacket):
    return OpportunityAnalyzer(AnalysisSettings()).analyze(packet, now=NOW)


def test_synthetic_csv_sidecars_fail_closed() -> None:
    demand_source, _ = CsvImporter.demand(EXAMPLES / "demand.csv")
    assert demand_source.evidence_use == EvidenceUse.SYNTHETIC
    assert demand_source.decision_eligible is False

    packet = asyncio.run(
        build_evidence_packet(
            config=AppConfig(),
            business=BusinessProfile(product_service="Synthetic example"),
            competitor_csvs=[str(EXAMPLES / "competitors.csv")],
            demand_csvs=[str(EXAMPLES / "demand.csv")],
            coverage_csvs=[str(EXAMPLES / "coverage.csv")],
        )
    )
    result = _analysis(packet)
    assert result.top_underserved_categories == []
    assert all(item.status == DecisionStatus.INSUFFICIENT_DATA for item in result.opportunities)


def test_cross_borough_mixed_metrics_emit_no_scores() -> None:
    packet = _packet(
        (
            Observation(Borough.BRONX, "Alpha", "monthly_searches", 120, 1),
            Observation(Borough.BRONX, "Beta", "monthly_searches", 80, 2),
            Observation(Borough.QUEENS, "Alpha", "orders", 20, 1),
            Observation(Borough.QUEENS, "Beta", "orders", 10, 2),
        )
    )
    result = _analysis(packet)
    assert result.top_underserved_categories == []
    assert result.priority_borough is None
    assert all(item.status == DecisionStatus.INSUFFICIENT_DATA for item in result.opportunities)
    assert all(item.opportunity_score is None for item in result.opportunities)


def test_overture_multi_category_membership_counts_each_match_once() -> None:
    record = CompetitorRecord(
        record_id="place:one",
        competitor_name="Mapped place",
        borough=Borough.BRONX,
        primary_category="Label One",
        secondary_categories=["Label Two"],
        source_id="source:overture",
        source_url="https://example.com/overture",
        observed_at=NOW,
    )
    mapped = _apply_overture_category_mapping(
        [record],
        {"Category A": {"Label One"}, "Category B": {"Label Two"}},
    )
    assert len(mapped) == 1
    assert mapped[0].primary_category == "Category A"
    assert mapped[0].secondary_categories == ["Category B"]
    assert _overture_coverage_counts(mapped, {"Category A", "Category B"}) == {
        (Borough.BRONX, "Category A"): 1,
        (Borough.BRONX, "Category B"): 1,
    }


def test_source_verifier_rejects_private_addresses() -> None:
    source = EvidenceSource(
        source_id="web:private",
        source_type=SourceType.WEB_RESEARCH,
        title="Private source",
        url="http://127.0.0.1",
        retrieved_at=NOW,
    )
    result = asyncio.run(verify_http_sources([source], timeout_seconds=1))
    assert result[0].status == EvidenceStatus.FAILED


class WrongBoroughVoteClient(StructuredModelClient):
    def __init__(self, evidence_id: str):
        super().__init__(AppConfig().runtime)
        self.evidence_id = evidence_id

    async def call(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_model: type[T],
        prompt_version: str,
        web_search: bool = False,
    ) -> StageResult:
        del messages, response_model, prompt_version, web_search
        vote = ConsensusVote(
            model=model,
            selected_option="Alpha",
            evidence_ids=[self.evidence_id],
            reasoning="This vote deliberately cites another borough.",
            evidence_coverage=1,
            logical_consistency=1,
            constraint_compliance=1,
            confidence=1,
        )
        return StageResult(vote, model, "consensus.v1", 0, None, None)


def test_consensus_rejects_evidence_from_another_borough() -> None:
    packet = _packet(
        (
            Observation(Borough.BRONX, "Alpha", demand=200, supply=1),
            Observation(Borough.BRONX, "Beta", demand=150, supply=2),
            Observation(Borough.QUEENS, "Alpha", demand=100, supply=1),
            Observation(Borough.QUEENS, "Beta", demand=80, supply=2),
        )
    )
    deterministic = _analysis(packet)
    queens_evidence = next(
        item.evidence_ids[0]
        for item in deterministic.top_underserved_categories
        if item.borough == Borough.QUEENS and item.category == "Alpha"
    )
    workflow = MarketIntelligenceWorkflow(
        AppConfig(),
        client=WrongBoroughVoteClient(queens_evidence),
    )
    with pytest.raises(WorkflowError, match="outside its selected option"):
        asyncio.run(
            workflow.consensus(
                packet,
                deterministic,
                borough=Borough.BRONX,
                question="Choose a category",
                options=["Alpha", "Beta"],
            )
        )


def test_competitor_practice_requires_exact_observed_value() -> None:
    observations = (
        Observation(Borough.BRONX, "Alpha", demand=120, supply=1),
        Observation(Borough.BRONX, "Beta", demand=80, supply=2),
    )
    competitors = tuple(
        CompetitorRecord(
            record_id=f"competitor:{index}",
            competitor_name=f"Competitor {index}",
            borough=Borough.BRONX,
            primary_category="Alpha",
            rating=3 + index,
            delivery=False,
            source_id="supply:0",
            source_url="https://example.com/competitor",
            observed_at=NOW,
        )
        for index in range(2)
    )
    packet = _packet(observations, competitors=competitors)
    deterministic = _analysis(packet)
    practice = CompetitorPractice(
        category="Alpha",
        borough=Borough.BRONX,
        observed_field="delivery",
        observed_value="false",
        practice="Test offering delivery as a controlled experiment.",
        action="copy",
        competitor_record_ids=[record.record_id for record in competitors],
        evidence_ids=[record.record_id for record in competitors],
        reasoning="This is an unvalidated proposal based on the exact observed field.",
    )
    strategy = StrategyOutput(
        top_underserved_categories=deterministic.top_underserved_categories,
        positioning_angles=[],
        priority_borough=deterministic.priority_borough,
        priority_borough_status=deterministic.priority_borough_status,
        priority_borough_reasoning=deterministic.priority_borough_reasoning,
        competitor_practices=[practice],
        next_actions=[],
    )
    validate_strategy(strategy, packet, deterministic)

    invalid = strategy.model_copy(
        update={
            "competitor_practices": [practice.model_copy(update={"observed_value": "true"})],
        }
    )
    with pytest.raises(EvidenceValidationError, match="does not exactly match"):
        validate_strategy(invalid, packet, deterministic)


def test_strategy_actions_cannot_claim_measured_impact() -> None:
    with pytest.raises(ValidationError):
        RecommendedAction(
            rank=1,
            category="Alpha",
            borough=Borough.BRONX,
            claim_type="demand",
            action="Run a controlled validation campaign.",
            expected_impact="overnight demand growth",
            evidence_ids=["signal:0"],
        )


def test_copy_requires_exact_operator_approved_fact() -> None:
    fact = ApprovedCopyFact(
        fact_id="fact:pickup",
        text="Appointment pickup is offered.",
        category="Alpha",
        borough=Borough.BRONX,
    )
    packet = _packet(
        (
            Observation(Borough.BRONX, "Alpha", demand=120, supply=1),
            Observation(Borough.BRONX, "Beta", demand=80, supply=2),
        ),
        approved_copy_facts=(fact,),
    )
    deterministic = _analysis(packet)
    output = AdCopyOutput(
        category="Alpha",
        borough=Borough.BRONX,
        headlines=["Alpha Pickup", "Explore Alpha", "Bronx Alpha", "Choose Alpha", "Order Alpha"],
        descriptions=[
            "Appointment pickup is offered.",
            "Explore Alpha options for your plans.",
            "Request details for Alpha in the Bronx.",
        ],
        landing_page_intro="Explore Alpha in the Bronx. Appointment pickup is offered.",
        cta_line="Request details",
        evidence_ids=[fact.fact_id],
    )
    validate_copy(output, packet, deterministic, category="Alpha", borough=Borough.BRONX)

    unsupported = output.model_copy(update={"descriptions": ["Guaranteed results.", *output.descriptions[1:]]})
    with pytest.raises(EvidenceValidationError, match="require separate offer evidence"):
        validate_copy(unsupported, packet, deterministic, category="Alpha", borough=Borough.BRONX)


def test_cli_maps_model_stage_failure_to_exit_code_one() -> None:
    async def failing_handler(args: argparse.Namespace, config: AppConfig) -> None:
        del args, config
        raise ModelStageError("provider failure")

    args = argparse.Namespace(
        verbose=0,
        json_logs=False,
        config=None,
        handler=failing_handler,
    )
    assert asyncio.run(execute_args(args)) == 1

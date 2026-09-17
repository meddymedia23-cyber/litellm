from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from .analysis import OpportunityAnalyzer
from .config import AppConfig
from .io_utils import read_json, read_models
from .llm_client import StageResult, StructuredModelClient
from .models import (
    AdCopyOutput,
    Borough,
    BusinessProfile,
    ClassificationOutput,
    CompetitorRecord,
    ConsensusOutput,
    ConsensusVote,
    DecisionStatus,
    DemandSignal,
    DeterministicAnalysis,
    EvidencePacket,
    EvidenceSource,
    ResearchOutput,
    StrategyOutput,
    SupplyCoverage,
)
from .normalization import stable_id
from .prompts import (
    classification_messages,
    consensus_messages,
    copy_messages,
    research_messages,
    strategy_messages,
    synthesis_messages,
)
from .sources import CsvImporter, DcwpIssuedLicensesSource, verify_http_sources
from .validation import validate_classification, validate_copy, validate_strategy


class WorkflowError(RuntimeError):
    pass


def _unique_by_id(items: Iterable, attribute: str) -> list:
    indexed = {}
    for item in items:
        key = getattr(item, attribute)
        if key in indexed and indexed[key] != item:
            raise WorkflowError(f"conflicting duplicate {attribute}: {key}")
        indexed[key] = item
    return list(indexed.values())


def create_evidence_packet(
    *,
    business: BusinessProfile,
    sources: list[EvidenceSource],
    competitors: list[CompetitorRecord],
    demand_signals: list[DemandSignal],
    coverage: list[SupplyCoverage],
) -> EvidencePacket:
    sources = _unique_by_id(sources, "source_id")
    competitors = _unique_by_id(competitors, "record_id")
    demand_signals = _unique_by_id(demand_signals, "signal_id")
    coverage = _unique_by_id(coverage, "coverage_id")
    candidates = sorted(
        {
            *(item.primary_category for item in competitors),
            *(item.category for item in demand_signals),
            *(item.category for item in coverage),
        }
    )
    if not sources:
        raise WorkflowError("at least one data source is required")
    if not candidates:
        raise WorkflowError("no candidate categories were found in the supplied data")
    now = datetime.now(timezone.utc)
    return EvidencePacket(
        run_id=stable_id("run", now.isoformat(), *(source.source_id for source in sources)),
        created_at=now,
        business=business,
        sources=sources,
        competitors=competitors,
        demand_signals=demand_signals,
        supply_coverage=coverage,
        candidate_categories=candidates,
    )


def apply_classifications(packet: EvidencePacket, outputs: list[ClassificationOutput]) -> EvidencePacket:
    classifications = {item.record_id: item for output in outputs for item in output.classifications}
    records = [
        record.model_copy(
            update={
                "primary_category": classifications[record.record_id].canonical_category,
                "secondary_categories": classifications[record.record_id].secondary_categories,
            }
        )
        if record.record_id in classifications
        else record
        for record in packet.competitors
    ]
    candidates = sorted(
        {
            *(record.primary_category for record in records),
            *(signal.category for signal in packet.demand_signals),
            *(item.category for item in packet.supply_coverage),
        }
    )
    return packet.model_copy(update={"competitors": records, "candidate_categories": candidates})


async def build_evidence_packet(
    *,
    config: AppConfig,
    business: BusinessProfile,
    competitor_csvs: list[str] | None = None,
    demand_csvs: list[str] | None = None,
    coverage_csvs: list[str] | None = None,
    dcwp_dirs: list[str] | None = None,
    include_dcwp: bool = False,
) -> EvidencePacket:
    sources: list[EvidenceSource] = []
    competitors = []
    demand_signals = []
    coverage = []

    if include_dcwp:
        source, records, coverage_items = await DcwpIssuedLicensesSource(config.collection).collect()
        sources.append(source)
        competitors.extend(records)
        coverage.extend(coverage_items)

    for directory in dcwp_dirs or []:
        root = Path(directory)
        source = EvidenceSource.model_validate(read_json(root / "source.json"))
        records = read_models(root / "competitors.jsonl", CompetitorRecord)
        coverage_items = read_models(root / "coverage.jsonl", SupplyCoverage)
        sources.append(source)
        competitors.extend(records)
        coverage.extend(coverage_items)

    for path in competitor_csvs or []:
        source, records = CsvImporter.competitors(path)
        sources.append(source)
        competitors.extend(records)
    for path in demand_csvs or []:
        source, signals = CsvImporter.demand(path)
        sources.append(source)
        demand_signals.extend(signals)
    for path in coverage_csvs or []:
        source, items = CsvImporter.coverage(path)
        sources.append(source)
        coverage.extend(items)

    return create_evidence_packet(
        business=business,
        sources=sources,
        competitors=competitors,
        demand_signals=demand_signals,
        coverage=coverage,
    )


class MarketIntelligenceWorkflow:
    def __init__(
        self,
        config: AppConfig,
        *,
        client: StructuredModelClient | None = None,
        analyzer: OpportunityAnalyzer | None = None,
    ):
        self.config = config
        self.client = client or StructuredModelClient(config.runtime)
        self.analyzer = analyzer or OpportunityAnalyzer(config.analysis)

    async def research(self, business: BusinessProfile, question: str) -> StageResult:
        result = await self.client.call(
            model=self.config.models.research,
            messages=research_messages(business, question),
            response_model=ResearchOutput,
            prompt_version="research.v1",
            web_search=True,
        )
        raw = result.value
        unverified = [
            source.model_copy(
                update={
                    "status": "unverified",
                    "evidence_use": "unknown",
                    "decision_eligible": False,
                    "content_hash": None,
                    "provider_sharing_allowed": False,
                }
            )
            for source in raw.sources
        ]
        verified = await verify_http_sources(
            unverified,
            timeout_seconds=self.config.collection.timeout_seconds,
            concurrency=self.config.runtime.concurrency,
        )
        verified_ids = {source.source_id for source in verified if source.status.value == "verified"}
        retained_candidates = [
            candidate for candidate in raw.candidate_categories if set(candidate.evidence_ids) <= verified_ids
        ]
        limitations = list(raw.limitations)
        removed_count = len(raw.candidate_categories) - len(retained_candidates)
        if removed_count:
            limitations.append(
                f"Removed {removed_count} candidate category result(s) because their cited sources failed verification."
            )
        value = raw.model_copy(
            update={
                "sources": verified,
                "candidate_categories": retained_candidates,
                "limitations": limitations,
            }
        )
        return StageResult(
            value=value,
            model=result.model,
            prompt_version=result.prompt_version,
            latency_seconds=result.latency_seconds,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

    async def classify(
        self,
        packet: EvidencePacket,
        *,
        taxonomy: list[str],
        batch_size: int = 50,
    ) -> list[StageResult]:
        if batch_size < 1 or batch_size > 200:
            raise WorkflowError("classification batch size must be between 1 and 200")
        semaphore = asyncio.Semaphore(self.config.runtime.concurrency)

        async def classify_batch(records: list) -> StageResult:
            async with semaphore:
                result = await self.client.call(
                    model=self.config.models.classification,
                    messages=classification_messages([record.model_dump(mode="json") for record in records], taxonomy),
                    response_model=ClassificationOutput,
                    prompt_version="classification.v1",
                )
                mini_packet = packet.model_copy(update={"competitors": records})
                validate_classification(result.value, mini_packet, taxonomy)
                return result

        shareable_source_ids = {source.source_id for source in packet.sources if source.provider_sharing_allowed}
        shareable_records = [record for record in packet.competitors if record.source_id in shareable_source_ids]
        if not shareable_records:
            raise WorkflowError("no competitor records permit provider sharing for classification")
        batches = [
            shareable_records[index : index + batch_size] for index in range(0, len(shareable_records), batch_size)
        ]
        return await asyncio.gather(*(classify_batch(batch) for batch in batches))

    def deterministic_analysis(self, packet: EvidencePacket) -> DeterministicAnalysis:
        return self.analyzer.analyze(packet)

    async def preliminary_strategy(self, packet: EvidencePacket, deterministic: DeterministicAnalysis) -> StageResult:
        result = await self.client.call(
            model=self.config.models.analysis,
            messages=strategy_messages(packet.model_view(), deterministic),
            response_model=StrategyOutput,
            prompt_version="strategy.v1",
        )
        validate_strategy(result.value, packet, deterministic)
        return result

    async def synthesize_strategy(
        self,
        packet: EvidencePacket,
        deterministic: DeterministicAnalysis,
        preliminary: StrategyOutput,
    ) -> StageResult:
        result = await self.client.call(
            model=self.config.models.synthesis,
            messages=synthesis_messages(packet.model_view(), deterministic, preliminary),
            response_model=StrategyOutput,
            prompt_version="strategy.v1",
        )
        validate_strategy(result.value, packet, deterministic)
        return result

    async def write_copy(
        self,
        packet: EvidencePacket,
        deterministic: DeterministicAnalysis,
        strategy: StrategyOutput,
        *,
        category: str,
        borough: str,
    ) -> StageResult:
        result = await self.client.call(
            model=self.config.models.copy_model,
            messages=copy_messages(packet.model_view(), strategy, category, borough),
            response_model=AdCopyOutput,
            prompt_version="copy.v1",
        )
        validate_copy(
            result.value,
            packet,
            deterministic,
            category=category,
            borough=Borough(borough),
        )
        return result

    async def consensus(
        self,
        packet: EvidencePacket,
        deterministic: DeterministicAnalysis,
        *,
        borough: Borough,
        question: str,
        options: list[str],
    ) -> ConsensusOutput:
        if deterministic.packet_digest != packet.digest():
            raise WorkflowError("consensus analysis does not match the evidence packet")
        if len(set(options)) < 2:
            raise WorkflowError("consensus requires at least two unique options")
        option_evidence = {
            option: {
                evidence_id
                for item in deterministic.top_underserved_categories
                if item.borough == borough and item.category == option
                for evidence_id in item.evidence_ids
            }
            for option in options
        }
        if any(not evidence_ids for evidence_ids in option_evidence.values()):
            raise WorkflowError("every consensus option requires deterministic evidence")
        aggregates = [
            item.model_dump(mode="json")
            for item in deterministic.top_underserved_categories
            if item.borough == borough and item.category in options
        ]
        messages = consensus_messages(packet.model_view(), aggregates, borough.value, question, options)
        semaphore = asyncio.Semaphore(self.config.runtime.concurrency)

        async def vote(model: str) -> ConsensusVote:
            async with semaphore:
                result = await self.client.call(
                    model=model,
                    messages=messages,
                    response_model=ConsensusVote,
                    prompt_version="consensus.v1",
                )
                value = result.value.model_copy(update={"model": model})
                if value.selected_option not in options:
                    raise WorkflowError(f"consensus model {model} selected an unknown option")
                unknown = set(value.evidence_ids) - option_evidence[value.selected_option]
                if unknown:
                    raise WorkflowError(
                        f"consensus model {model} cited evidence outside its selected option: {sorted(unknown)}"
                    )
                return value

        votes = await asyncio.gather(*(vote(model) for model in self.config.models.consensus))
        totals: dict[str, float] = defaultdict(float)
        for vote_item in votes:
            allowed_count = len(option_evidence[vote_item.selected_option])
            evidence_weight = len(set(vote_item.evidence_ids)) / allowed_count
            totals[vote_item.selected_option] += evidence_weight
        ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        tied = len(ordered) > 1 and abs(ordered[0][1] - ordered[1][1]) < 1e-9
        decision = None if tied else ordered[0][0]
        status = DecisionStatus.INSUFFICIENT_DATA if tied else DecisionStatus.SUPPORTED
        dissent = [
            f"{vote_item.model} selected {vote_item.selected_option}"
            for vote_item in votes
            if decision is None or vote_item.selected_option != decision
        ]
        reasoning = (
            "insufficient data: evidence-weighted consensus is tied."
            if tied
            else f"{decision} received the highest evidence-weighted score."
        )
        return ConsensusOutput(
            decision=decision,
            status=status,
            votes=votes,
            dissent=dissent,
            reasoning=reasoning,
        )

    async def run_strategy(self, packet: EvidencePacket) -> dict:
        deterministic = self.deterministic_analysis(packet)
        if not deterministic.top_underserved_categories:
            return {
                "packet_digest": packet.digest(),
                "deterministic": deterministic.model_dump(mode="json"),
                "status": "insufficient_data",
                "message": "insufficient data",
                "model_stages": [],
            }
        preliminary = await self.preliminary_strategy(packet, deterministic)
        final = await self.synthesize_strategy(packet, deterministic, preliminary.value)
        return {
            "packet_digest": packet.digest(),
            "deterministic": deterministic.model_dump(mode="json"),
            "strategy": final.value.model_dump(mode="json"),
            "status": "supported_with_unvalidated_proposals",
            "model_stages": [
                preliminary.public_metadata(),
                final.public_metadata(),
            ],
        }

    async def run_full(self, packet: EvidencePacket) -> dict:
        strategy_run = await self.run_strategy(packet)
        if strategy_run["status"] != "supported_with_unvalidated_proposals":
            return strategy_run
        deterministic = DeterministicAnalysis.model_validate(strategy_run["deterministic"])
        strategy = StrategyOutput.model_validate(strategy_run["strategy"])
        selected_borough = deterministic.priority_borough
        borough_options = (
            list(
                dict.fromkeys(
                    item.category
                    for item in deterministic.top_underserved_categories
                    if item.borough == selected_borough
                )
            )
            if selected_borough is not None
            else []
        )
        options = borough_options
        consensus = None
        selected_category = options[0] if len(options) == 1 else None
        if len(options) > 1:
            consensus = await self.consensus(
                packet,
                deterministic,
                borough=selected_borough,
                question="Which supported category should this business validate first?",
                options=options,
            )
            if consensus.status == DecisionStatus.SUPPORTED and consensus.decision:
                selected_category = consensus.decision
        copy_result = None
        limitations: list[str] = []
        approved_copy_facts = [
            fact
            for fact in packet.business.approved_copy_facts
            if selected_borough is not None
            and (fact.borough is None or fact.borough == selected_borough)
            and (
                selected_category is not None
                and (fact.category is None or fact.category.casefold() == selected_category.casefold())
            )
        ]
        if selected_category is None:
            limitations.append("insufficient data: ad copy was not generated because category consensus is tied.")
        if selected_borough is None:
            limitations.append("insufficient data: ad copy was not generated because borough priority is unsupported.")
        if selected_category is not None and selected_borough is not None and not approved_copy_facts:
            limitations.append(
                "insufficient data: ad copy was not generated because no approved copy facts exist "
                "for the selected category and borough."
            )
        if selected_category is not None and selected_borough is not None and approved_copy_facts:
            copy_result = await self.write_copy(
                packet,
                deterministic,
                strategy,
                category=selected_category,
                borough=selected_borough.value,
            )
        result = dict(strategy_run)
        result.update(
            {
                "selected_category": selected_category,
                "selected_borough": selected_borough.value if selected_borough else None,
                "consensus": consensus.model_dump(mode="json") if consensus else None,
                "copy": copy_result.value.model_dump(mode="json") if copy_result else None,
                "limitations": limitations,
            }
        )
        if copy_result:
            result["model_stages"].append(copy_result.public_metadata())
        if limitations:
            result["status"] = "insufficient_data"
        return result

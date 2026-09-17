from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


class Borough(str, Enum):
    BRONX = "Bronx"
    QUEENS = "Queens"
    MANHATTAN = "Manhattan"
    BROOKLYN = "Brooklyn"
    STATEN_ISLAND = "Staten Island"


class EvidenceStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class EvidenceUse(str, Enum):
    UNKNOWN = "unknown"
    PRODUCTION = "production"
    SYNTHETIC = "synthetic"
    EVALUATION = "evaluation"


class DecisionStatus(str, Enum):
    SUPPORTED = "supported"
    INSUFFICIENT_DATA = "insufficient_data"


class SourceType(str, Enum):
    NYC_OPEN_DATA = "nyc_open_data"
    CENSUS = "census"
    GOOGLE_ADS_EXPORT = "google_ads_export"
    GOOGLE_ADS_API = "google_ads_api"
    COMPETITOR_EXPORT = "competitor_export"
    USER_SUPPLIED = "user_supplied"
    WEB_RESEARCH = "web_research"


class CsvSourceProvenance(StrictModel):
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_use: EvidenceUse
    decision_eligible: StrictBool
    license_name: str | None = Field(default=None, max_length=200)
    attribution: str | None = Field(default=None, max_length=500)
    retention_allowed: StrictBool = False
    provider_sharing_allowed: StrictBool = False
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_decision_eligibility(self) -> CsvSourceProvenance:
        if self.decision_eligible and self.evidence_use != EvidenceUse.PRODUCTION:
            raise ValueError("only production evidence can be decision eligible")
        return self


class EvidenceSource(StrictModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
    source_type: SourceType
    title: str = Field(min_length=3, max_length=300)
    url: str
    retrieved_at: datetime
    published_at: datetime | None = None
    status: EvidenceStatus = EvidenceStatus.UNVERIFIED
    evidence_use: EvidenceUse = EvidenceUse.UNKNOWN
    decision_eligible: StrictBool = False
    content_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    license_name: str | None = Field(default=None, max_length=200)
    attribution: str | None = Field(default=None, max_length=500)
    retention_allowed: StrictBool = False
    provider_sharing_allowed: StrictBool = False
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https", "file"}:
            raise ValueError("source URL must use http, https, or file")
        if parsed.scheme in {"http", "https"} and not parsed.netloc:
            raise ValueError("source URL must include a host")
        return value

    @model_validator(mode="after")
    def validate_decision_eligibility(self) -> EvidenceSource:
        if self.decision_eligible and self.evidence_use != EvidenceUse.PRODUCTION:
            raise ValueError("decision-eligible sources must have production evidence use")
        return self


class CompetitorRecord(StrictModel):
    record_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
    competitor_name: str = Field(min_length=1, max_length=300)
    borough: Borough
    neighborhood: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    primary_category: str = Field(min_length=1, max_length=160)
    secondary_categories: list[str] = Field(default_factory=list, max_length=20)
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    currency: Literal["USD"] = "USD"
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: StrictInt | None = Field(default=None, ge=0)
    pickup: StrictBool | None = None
    delivery: StrictBool | None = None
    delivery_fee: float | None = Field(default=None, ge=0)
    delivery_radius_miles: float | None = Field(default=None, ge=0)
    main_offer: str | None = Field(default=None, max_length=1000)
    ad_message: str | None = Field(default=None, max_length=2000)
    source_id: str
    source_url: str
    observed_at: datetime
    external_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_price_range(self) -> CompetitorRecord:
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("price_min cannot exceed price_max")
        return self


class DemandSignal(StrictModel):
    signal_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
    category: str = Field(min_length=1, max_length=160)
    borough: Borough
    metric: Literal[
        "monthly_searches",
        "qualified_leads",
        "orders",
        "revenue_usd",
        "service_requests",
        "survey_intent",
    ]
    value: float = Field(ge=0)
    period_start: datetime
    period_end: datetime
    source_id: str
    confidence: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_period(self) -> DemandSignal:
        if self.period_start > self.period_end:
            raise ValueError("period_start cannot be after period_end")
        return self


class SupplyCoverage(StrictModel):
    coverage_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
    category: str = Field(min_length=1, max_length=160)
    borough: Borough
    query_completed: StrictBool
    result_count: StrictInt = Field(ge=0)
    source_id: str
    observed_at: datetime
    query: str = Field(min_length=1, max_length=500)


class ApprovedCopyFact(StrictModel):
    fact_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
    text: str = Field(min_length=2, max_length=300)
    category: str | None = Field(default=None, max_length=160)
    borough: Borough | None = None


class BusinessProfile(StrictModel):
    product_service: str = Field(min_length=2, max_length=300)
    primary_boroughs: list[Borough] = Field(default_factory=lambda: [Borough.BRONX, Borough.QUEENS], min_length=1)
    secondary_boroughs: list[Borough] = Field(default_factory=lambda: [Borough.MANHATTAN, Borough.BROOKLYN])
    pickup: StrictBool = True
    delivery: StrictBool = True
    no_storefront: StrictBool = True
    pickup_borough: Borough | None = None
    maximum_delivery_radius_miles: float | None = Field(default=None, gt=0)
    minimum_gross_margin_percent: float | None = Field(default=None, ge=0, le=100)
    maximum_unit_cost_usd: float | None = Field(default=None, ge=0)
    excluded_categories: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    approved_copy_facts: list[ApprovedCopyFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_copy_facts(self) -> BusinessProfile:
        fact_ids = [fact.fact_id for fact in self.approved_copy_facts]
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("approved copy fact IDs must be unique")
        return self


class CandidateCategory(StrictModel):
    category: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=10, max_length=1200)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class ResearchOutput(StrictModel):
    prompt_version: Literal["research.v1"] = "research.v1"
    sources: list[EvidenceSource]
    candidate_categories: list[CandidateCategory]
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_candidate_evidence(self) -> ResearchOutput:
        source_ids = {source.source_id for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("research source IDs must be unique")
        unknown = {
            evidence_id
            for candidate in self.candidate_categories
            for evidence_id in candidate.evidence_ids
            if evidence_id not in source_ids
        }
        if unknown:
            raise ValueError(f"candidate categories reference unknown sources: {sorted(unknown)}")
        return self


class ListingClassification(StrictModel):
    record_id: str
    canonical_category: str = Field(min_length=1, max_length=160)
    secondary_categories: list[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0, le=1)
    evidence_text: str = Field(min_length=1, max_length=1000)


class ClassificationOutput(StrictModel):
    prompt_version: Literal["classification.v1"] = "classification.v1"
    classifications: list[ListingClassification]
    unclassified_record_ids: list[str] = Field(default_factory=list)


class CategoryOpportunity(StrictModel):
    category: str
    borough: Borough
    status: DecisionStatus
    demand_metric: str | None = Field(default=None, max_length=80)
    period_start: datetime | None = None
    period_end: datetime | None = None
    demand_score: float | None = Field(default=None, ge=0, le=100)
    supply_gap_score: float | None = Field(default=None, ge=0, le=100)
    competitor_weakness_score: float | None = Field(default=None, ge=0, le=100)
    business_fit_score: float | None = Field(default=None, ge=0, le=100)
    opportunity_score: float | None = Field(default=None, ge=0, le=100)
    demand_value: float | None = Field(default=None, ge=0)
    supply_count: int | None = Field(default=None, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    reasoning: str
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_status_consistency(self) -> CategoryOpportunity:
        required = (
            self.demand_metric,
            self.period_start,
            self.period_end,
            self.demand_score,
            self.supply_gap_score,
            self.opportunity_score,
        )
        if self.status == DecisionStatus.SUPPORTED and any(v is None for v in required):
            raise ValueError(
                "supported opportunities require demand metric/window, demand score, "
                "supply-gap score, and opportunity score"
            )
        if self.status == DecisionStatus.INSUFFICIENT_DATA and self.opportunity_score is not None:
            raise ValueError("insufficient-data opportunities cannot have an opportunity score")
        return self


class DeterministicAnalysis(StrictModel):
    generated_at: datetime
    packet_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    opportunities: list[CategoryOpportunity]
    top_underserved_categories: list[CategoryOpportunity] = Field(max_length=5)
    priority_borough: Borough | None
    priority_borough_status: DecisionStatus
    priority_borough_reasoning: str
    limitations: list[str] = Field(default_factory=list)


class PositioningAngle(StrictModel):
    proposal_status: Literal["proposal_requires_validation"] = "proposal_requires_validation"
    category: str = Field(min_length=1, max_length=160)
    borough: Borough
    claim_type: Literal["demand", "supply", "competitor", "combined"]
    angle: str = Field(min_length=3, max_length=160)
    supporting_evidence_ids: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=10, max_length=1200)
    confidence: float = Field(ge=0, le=1)


class CompetitorPractice(StrictModel):
    proposal_status: Literal["proposal_requires_validation"] = "proposal_requires_validation"
    category: str = Field(min_length=1, max_length=160)
    borough: Borough
    observed_field: Literal[
        "pickup",
        "delivery",
        "price_min",
        "price_max",
        "rating",
        "review_count",
        "main_offer",
        "ad_message",
    ]
    observed_value: str = Field(min_length=1, max_length=2000)
    practice: str = Field(min_length=3, max_length=500)
    action: Literal["copy", "avoid"]
    competitor_record_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=10, max_length=1200)


class RecommendedAction(StrictModel):
    proposal_status: Literal["proposal_requires_validation"] = "proposal_requires_validation"
    rank: Annotated[int, Field(ge=1, le=3)]
    category: str = Field(min_length=1, max_length=160)
    borough: Borough
    claim_type: Literal["demand", "supply", "competitor", "combined"]
    action: str = Field(min_length=3, max_length=500)
    expected_impact: Literal["unknown until measured"] = "unknown until measured"
    evidence_ids: list[str] = Field(min_length=1)


class StrategyOutput(StrictModel):
    prompt_version: Literal["strategy.v1"] = "strategy.v1"
    narrative_status: Literal["proposals_require_validation"] = "proposals_require_validation"
    top_underserved_categories: list[CategoryOpportunity] = Field(max_length=5)
    positioning_angles: list[PositioningAngle] = Field(max_length=3)
    priority_borough: Borough | None
    priority_borough_status: DecisionStatus
    priority_borough_reasoning: str
    competitor_practices: list[CompetitorPractice]
    next_actions: list[RecommendedAction] = Field(max_length=3)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_strategy(self) -> StrategyOutput:
        ranks = [item.rank for item in self.next_actions]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("next action ranks must be sequential starting at 1")
        if self.priority_borough_status == DecisionStatus.INSUFFICIENT_DATA:
            if self.priority_borough is not None:
                raise ValueError("priority borough must be null when data is insufficient")
        elif self.priority_borough is None:
            raise ValueError("supported priority borough cannot be null")
        return self


class AdCopyOutput(StrictModel):
    prompt_version: Literal["copy.v1"] = "copy.v1"
    review_status: Literal["draft_requires_human_review"] = "draft_requires_human_review"
    category: str = Field(min_length=1, max_length=160)
    borough: Borough
    headlines: list[str] = Field(min_length=5, max_length=5)
    descriptions: list[str] = Field(min_length=3, max_length=3)
    landing_page_intro: str
    cta_line: str = Field(min_length=2, max_length=120)
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("headlines")
    @classmethod
    def validate_headlines(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("headlines cannot be empty")
        if len({value.casefold() for value in values}) != len(values):
            raise ValueError("headlines must be unique")
        too_long = [value for value in values if len(value) >= 30]
        if too_long:
            raise ValueError("headlines must contain fewer than 30 characters")
        return values

    @field_validator("descriptions")
    @classmethod
    def validate_descriptions(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("descriptions cannot be empty")
        if len({value.casefold() for value in values}) != len(values):
            raise ValueError("descriptions must be unique")
        too_long = [value for value in values if len(value) >= 90]
        if too_long:
            raise ValueError("descriptions must contain fewer than 90 characters")
        return values

    @field_validator("landing_page_intro")
    @classmethod
    def validate_intro(cls, value: str) -> str:
        if len(re.findall(r"\b\w+[’'-]?\w*\b", value)) > 150:
            raise ValueError("landing page intro must be 150 words or fewer")
        return value


class ConsensusVote(StrictModel):
    model: str = Field(min_length=1, max_length=160)
    selected_option: str = Field(min_length=1, max_length=300)
    evidence_ids: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=10, max_length=1200)
    evidence_coverage: float = Field(ge=0, le=1)
    logical_consistency: float = Field(ge=0, le=1)
    constraint_compliance: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class ConsensusOutput(StrictModel):
    prompt_version: Literal["consensus.v1"] = "consensus.v1"
    decision: str | None
    status: DecisionStatus
    votes: list[ConsensusVote] = Field(min_length=2)
    dissent: list[str] = Field(default_factory=list)
    reasoning: str


class EvidencePacket(StrictModel):
    run_id: str
    created_at: datetime
    business: BusinessProfile
    sources: list[EvidenceSource]
    competitors: list[CompetitorRecord]
    demand_signals: list[DemandSignal]
    supply_coverage: list[SupplyCoverage]
    candidate_categories: list[str]

    @model_validator(mode="after")
    def validate_references(self) -> EvidencePacket:
        source_ids = {source.source_id for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("source IDs must be unique")
        record_ids = {record.record_id for record in self.competitors}
        if len(record_ids) != len(self.competitors):
            raise ValueError("competitor record IDs must be unique")
        signal_ids = {signal.signal_id for signal in self.demand_signals}
        if len(signal_ids) != len(self.demand_signals):
            raise ValueError("demand signal IDs must be unique")
        coverage_ids = {coverage.coverage_id for coverage in self.supply_coverage}
        if len(coverage_ids) != len(self.supply_coverage):
            raise ValueError("supply coverage IDs must be unique")
        referenced = {
            *(record.source_id for record in self.competitors),
            *(signal.source_id for signal in self.demand_signals),
            *(coverage.source_id for coverage in self.supply_coverage),
        }
        missing = referenced - source_ids
        if missing:
            raise ValueError(f"unknown source IDs referenced: {sorted(missing)}")
        return self

    def digest(self) -> str:
        payload = self.model_dump_json(exclude_none=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def model_view(self) -> dict:
        shareable = {source.source_id for source in self.sources if source.provider_sharing_allowed}
        return {
            "run_id": self.run_id,
            "business": self.business.model_dump(mode="json"),
            "sources": [source.model_dump(mode="json", exclude={"notes"}) for source in self.sources],
            "competitors": [
                record.model_dump(mode="json") for record in self.competitors if record.source_id in shareable
            ],
            "demand_signals": [
                signal.model_dump(mode="json") for signal in self.demand_signals if signal.source_id in shareable
            ],
            "supply_coverage": [
                item.model_dump(mode="json") for item in self.supply_coverage if item.source_id in shareable
            ],
            "candidate_categories": self.candidate_categories,
            "disclosure_note": (
                "Raw records are included only when their source permits provider sharing. "
                "Immutable deterministic aggregates may cite observation IDs whose raw records are withheld."
            ),
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

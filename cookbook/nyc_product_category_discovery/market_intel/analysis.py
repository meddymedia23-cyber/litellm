from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import fmean

from .config import AnalysisSettings
from .models import (
    Borough,
    CategoryOpportunity,
    DecisionStatus,
    DeterministicAnalysis,
    EvidencePacket,
    EvidenceStatus,
    EvidenceUse,
)
from .normalization import normalize_category


def _scaled(values: dict[str, float], *, inverse: bool = False) -> dict[str, float]:
    if not values:
        return {}
    minimum = min(values.values())
    maximum = max(values.values())
    if maximum == minimum:
        return {key: 50.0 for key in values}
    output = {key: ((value - minimum) / (maximum - minimum)) * 100 for key, value in values.items()}
    if inverse:
        output = {key: 100 - value for key, value in output.items()}
    return {key: round(value, 4) for key, value in output.items()}


class OpportunityAnalyzer:
    """Deterministic opportunity scorer that never manufactures missing evidence."""

    def __init__(self, settings: AnalysisSettings):
        self.settings = settings

    def analyze(
        self,
        packet: EvidencePacket,
        *,
        now: datetime | None = None,
        allow_evaluation: bool = False,
    ) -> DeterministicAnalysis:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        sources = {source.source_id: source for source in packet.sources}

        def eligible(source_id: str) -> bool:
            source = sources[source_id]
            return source.decision_eligible or (allow_evaluation and source.evidence_use == EvidenceUse.EVALUATION)

        candidates = sorted(
            {
                normalize_category(category)
                for category in (
                    packet.candidate_categories
                    + [signal.category for signal in packet.demand_signals]
                    + [coverage.category for coverage in packet.supply_coverage]
                )
            }
        )
        target_boroughs = list(dict.fromkeys(packet.business.primary_boroughs))

        demand_by_key = defaultdict(list)
        for signal in packet.demand_signals:
            demand_by_key[(signal.borough, normalize_category(signal.category))].append(signal)
        coverage_by_key = defaultdict(list)
        for coverage in packet.supply_coverage:
            coverage_by_key[(coverage.borough, normalize_category(coverage.category))].append(coverage)
        competitors_by_key = defaultdict(list)
        for competitor in packet.competitors:
            categories = {competitor.primary_category, *competitor.secondary_categories}
            for category in categories:
                competitors_by_key[(competitor.borough, normalize_category(category))].append(competitor)

        valid_components: dict[tuple[Borough, str], dict] = {}
        insufficient: dict[tuple[Borough, str], list[str]] = defaultdict(list)

        excluded = {normalize_category(item) for item in packet.business.excluded_categories}
        max_age_seconds = self.settings.maximum_data_age_days * 86400

        for borough in target_boroughs:
            for category in candidates:
                key = (borough, category)
                if category in excluded:
                    insufficient[key].append("Category is excluded by the business profile.")
                    continue

                signals = [
                    signal
                    for signal in demand_by_key[key]
                    if signal.confidence >= self.settings.minimum_demand_confidence
                    and signal.value >= self.settings.minimum_demand_value
                    and signal.period_end <= now
                    and (now - signal.period_end).total_seconds() <= max_age_seconds
                    and sources[signal.source_id].status == EvidenceStatus.VERIFIED
                    and eligible(signal.source_id)
                ]
                if not signals:
                    insufficient[key].append(
                        "No fresh, verified, decision-eligible category-level demand signal meets the confidence threshold."
                    )

                coverage_items = [
                    item
                    for item in coverage_by_key[key]
                    if item.query_completed
                    and item.observed_at <= now
                    and (now - item.observed_at).total_seconds() <= max_age_seconds
                    and sources[item.source_id].status == EvidenceStatus.VERIFIED
                    and eligible(item.source_id)
                ]
                if not coverage_items:
                    insufficient[key].append(
                        "No fresh, verified, decision-eligible, completed supply query exists for this category and borough."
                    )

                if not signals or not coverage_items:
                    continue

                metrics = {signal.metric for signal in signals}
                if len(metrics) > 1:
                    insufficient[key].append(
                        "Demand signals use mixed units for the same category; aggregate them before scoring."
                    )
                    continue
                if len(signals) > 1:
                    insufficient[key].append(
                        "Multiple demand observations exist for the same category and borough; "
                        "deduplicate or pre-aggregate them before scoring."
                    )
                    continue
                if len(coverage_items) > 1:
                    insufficient[key].append(
                        "Multiple completed supply counts exist for the same category and borough; "
                        "select one documented query scope before scoring."
                    )
                    continue
                demand_value = signals[0].value
                supply_count = coverage_items[0].result_count
                valid_components[key] = {
                    "signals": signals,
                    "coverage": coverage_items,
                    "demand_value": demand_value,
                    "supply_count": supply_count,
                    "competitors": competitors_by_key[key],
                }

        for borough in target_boroughs:
            borough_keys = [key for key in valid_components if key[0] == borough]
            borough_metrics = {valid_components[key]["signals"][0].metric for key in borough_keys}
            borough_periods = {
                (
                    valid_components[key]["signals"][0].period_start,
                    valid_components[key]["signals"][0].period_end,
                )
                for key in borough_keys
            }
            if len(borough_metrics) > 1:
                for key in borough_keys:
                    insufficient[key].append(
                        "Candidate categories use different demand units within the borough; "
                        "normalize them to one metric before comparison."
                    )
            if len(borough_periods) > 1:
                for key in borough_keys:
                    insufficient[key].append(
                        "Candidate categories use different demand periods within the borough; "
                        "normalize them to one observation window before comparison."
                    )

        comparable_by_borough = {
            borough: [
                (borough, category)
                for category in candidates
                if (borough, category) in valid_components and not insufficient[(borough, category)]
            ]
            for borough in target_boroughs
        }
        score_keys = [
            key
            for borough, keys in comparable_by_borough.items()
            if len(keys) >= self.settings.minimum_supported_categories
            for key in keys
        ]
        comparison_signatures = {
            (
                valid_components[key]["signals"][0].metric,
                valid_components[key]["signals"][0].period_start,
                valid_components[key]["signals"][0].period_end,
            )
            for key in score_keys
        }
        participating_boroughs = {key[0] for key in score_keys}
        cross_borough_compatible = len(participating_boroughs) < 2 or len(comparison_signatures) == 1
        if not cross_borough_compatible:
            for key in score_keys:
                insufficient[key].append(
                    "Primary boroughs use different demand metrics or observation windows; "
                    "cross-borough scores are not comparable."
                )
            score_keys = []
        key_names = {key: f"{key[0].value}\u0000{key[1]}" for key in score_keys}
        demand_global = _scaled({key_names[key]: float(valid_components[key]["demand_value"]) for key in score_keys})
        supply_global = _scaled(
            {key_names[key]: float(valid_components[key]["supply_count"]) for key in score_keys},
            inverse=True,
        )

        opportunities: list[CategoryOpportunity] = []
        supported_by_borough: dict[Borough, list[CategoryOpportunity]] = defaultdict(list)
        for borough in target_boroughs:
            comparable_count = len(comparable_by_borough[borough])
            for category in candidates:
                key = (borough, category)
                reasons = list(insufficient[key])
                if key in valid_components and comparable_count < self.settings.minimum_supported_categories:
                    reasons.append(
                        f"Only {comparable_count} comparable category is available; "
                        f"at least {self.settings.minimum_supported_categories} are required."
                    )

                components = valid_components.get(key)
                if not components or reasons:
                    opportunities.append(
                        CategoryOpportunity(
                            category=category,
                            borough=borough,
                            status=DecisionStatus.INSUFFICIENT_DATA,
                            demand_metric=(components["signals"][0].metric if components else None),
                            period_start=(components["signals"][0].period_start if components else None),
                            period_end=(components["signals"][0].period_end if components else None),
                            demand_value=(components or {}).get("demand_value"),
                            supply_count=(components or {}).get("supply_count"),
                            evidence_ids=[],
                            reasoning="insufficient data",
                            limitations=reasons or ["insufficient data"],
                        )
                    )
                    continue

                weakness = self._competitor_weakness(components["competitors"])
                fit_score = None
                missing_weighted: list[str] = []
                if self.settings.competitor_weakness_weight > 0 and weakness is None:
                    missing_weighted.append("competitor quality")
                if self.settings.business_fit_weight > 0 and fit_score is None:
                    missing_weighted.append("category-specific business fit")
                if missing_weighted:
                    opportunities.append(
                        CategoryOpportunity(
                            category=category,
                            borough=borough,
                            status=DecisionStatus.INSUFFICIENT_DATA,
                            demand_metric=components["signals"][0].metric,
                            period_start=components["signals"][0].period_start,
                            period_end=components["signals"][0].period_end,
                            demand_value=components["demand_value"],
                            supply_count=components["supply_count"],
                            evidence_ids=[],
                            reasoning="insufficient data",
                            limitations=["Missing weighted component(s): " + ", ".join(missing_weighted)],
                        )
                    )
                    continue

                score_key = key_names[key]
                demand_score = demand_global[score_key]
                supply_gap_score = supply_global[score_key]
                opportunity_score = (
                    demand_score * self.settings.demand_weight
                    + supply_gap_score * self.settings.supply_gap_weight
                    + (weakness or 0) * self.settings.competitor_weakness_weight
                    + (fit_score or 0) * self.settings.business_fit_weight
                )
                evidence_ids = sorted(
                    {
                        *(signal.signal_id for signal in components["signals"]),
                        *(item.coverage_id for item in components["coverage"]),
                        *(item.record_id for item in components["competitors"] if weakness is not None),
                    }
                )
                result = CategoryOpportunity(
                    category=category,
                    borough=borough,
                    status=DecisionStatus.SUPPORTED,
                    demand_metric=components["signals"][0].metric,
                    period_start=components["signals"][0].period_start,
                    period_end=components["signals"][0].period_end,
                    demand_score=round(demand_score, 4),
                    supply_gap_score=round(supply_gap_score, 4),
                    competitor_weakness_score=weakness,
                    business_fit_score=fit_score,
                    opportunity_score=round(opportunity_score, 4),
                    demand_value=round(components["demand_value"], 4),
                    supply_count=components["supply_count"],
                    evidence_ids=evidence_ids,
                    reasoning=(
                        f"Supported by verified demand and completed supply coverage for {category} in {borough.value}."
                    ),
                    limitations=(
                        []
                        if weakness is not None
                        else ["Competitor quality was not scored because rating data is incomplete."]
                    ),
                )
                opportunities.append(result)
                supported_by_borough[borough].append(result)

        ranked = sorted(
            (
                item
                for item in opportunities
                if item.status == DecisionStatus.SUPPORTED and item.opportunity_score is not None
            ),
            key=lambda item: (-float(item.opportunity_score), item.borough.value, item.category),
        )
        limitations: list[str] = []
        if cross_borough_compatible:
            top = ranked[:5]
            priority, priority_status, priority_reason = self._priority_borough(supported_by_borough)
        else:
            top = []
            priority = None
            priority_status = DecisionStatus.INSUFFICIENT_DATA
            priority_reason = "insufficient data: primary boroughs use different demand metrics or observation windows."
            limitations.append(
                "Cross-borough ranking is unavailable because demand metrics or observation windows differ."
            )
        if not top:
            limitations.append(
                "No category met the cross-borough evidence requirements; the correct result is insufficient data."
            )
        return DeterministicAnalysis(
            generated_at=now,
            packet_digest=packet.digest(),
            opportunities=opportunities,
            top_underserved_categories=top,
            priority_borough=priority,
            priority_borough_status=priority_status,
            priority_borough_reasoning=priority_reason,
            limitations=limitations,
        )

    @staticmethod
    def _competitor_weakness(competitors: list) -> float | None:
        rated = [item for item in competitors if item.rating is not None]
        if len(rated) < 2:
            return None
        average_rating = fmean(float(item.rating) for item in rated)
        return round(max(0.0, min(100.0, (5.0 - average_rating) / 5.0 * 100)), 4)

    @staticmethod
    def _priority_borough(
        supported: dict[Borough, list[CategoryOpportunity]],
    ) -> tuple[Borough | None, DecisionStatus, str]:
        scores = {
            borough: fmean(
                float(item.opportunity_score)
                for item in sorted(
                    items,
                    key=lambda item: float(item.opportunity_score or 0),
                    reverse=True,
                )[:5]
            )
            for borough, items in supported.items()
            if items
        }
        if len(scores) < 2:
            return (
                None,
                DecisionStatus.INSUFFICIENT_DATA,
                "insufficient data: both primary boroughs need supported category scores.",
            )
        category_sets = [{item.category for item in items} for items in supported.values() if items]
        if any(categories != category_sets[0] for categories in category_sets[1:]):
            return (
                None,
                DecisionStatus.INSUFFICIENT_DATA,
                "insufficient data: primary boroughs do not share the same supported category set.",
            )
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0].value))
        if abs(ordered[0][1] - ordered[1][1]) < 1e-9:
            return (
                None,
                DecisionStatus.INSUFFICIENT_DATA,
                "insufficient data: borough opportunity scores are tied.",
            )
        winner, score = ordered[0]
        return (
            winner,
            DecisionStatus.SUPPORTED,
            f"{winner.value} has the higher mean supported opportunity score ({score:.2f}).",
        )

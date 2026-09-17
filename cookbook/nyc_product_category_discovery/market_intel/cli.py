from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from .analysis import OpportunityAnalyzer
from .config import AppConfig
from .evaluator import run_eval_suite
from .io_utils import read_json, write_json_atomic, write_jsonl_atomic
from .llm_client import ModelStageError
from .models import BusinessProfile, EvidencePacket
from .normalization import normalize_category
from .sources import (
    CollectionError,
    DcwpIssuedLicensesSource,
    GoogleAdsKeywordDemandSource,
    OverturePlacesSource,
)
from .workflow import (
    MarketIntelligenceWorkflow,
    WorkflowError,
    apply_classifications,
    build_evidence_packet,
    create_evidence_packet,
)

LOGGER = logging.getLogger("nyc_market_intel")
DEFAULT_EVAL_SUITE = Path(__file__).resolve().parent.parent / "fixtures" / "eval_cases.json"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, default=str) + "\n")


def configure_logging(verbose: int, json_logs: bool) -> None:
    level = logging.DEBUG if verbose > 1 else logging.INFO if verbose else logging.WARNING
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter("%(levelname)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def load_business(path: str) -> BusinessProfile:
    return BusinessProfile.model_validate(read_json(path))


def load_packet(path: str) -> EvidencePacket:
    return EvidencePacket.model_validate(read_json(path))


def load_category_seeds(path: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    payload = read_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("category seeds must be a non-empty JSON object")
    keywords: dict[str, list[str]] = {}
    taxonomy: dict[str, list[str]] = {}
    for category, settings in payload.items():
        if not isinstance(category, str) or not category.strip() or not isinstance(settings, dict):
            raise TypeError("each category seed must map a category name to an object")
        keyword_values = settings.get("keywords")
        taxonomy_values = settings.get("overture_categories")
        if (
            not isinstance(keyword_values, list)
            or not keyword_values
            or not all(isinstance(item, str) and item.strip() for item in keyword_values)
        ):
            raise TypeError(f"{category}.keywords must be a non-empty string array")
        if (
            not isinstance(taxonomy_values, list)
            or not taxonomy_values
            or not all(isinstance(item, str) and item.strip() for item in taxonomy_values)
        ):
            raise TypeError(f"{category}.overture_categories must be a non-empty string array")
        keywords[category] = keyword_values
        taxonomy[category] = taxonomy_values
    owners: dict[str, str] = {}
    for category, labels in taxonomy.items():
        for label in labels:
            normalized_label = normalize_category(label.replace("_", " "))
            existing = owners.get(normalized_label)
            if existing and existing != category:
                raise ValueError(f"Overture category {label!r} is assigned to both {existing!r} and {category!r}")
            owners[normalized_label] = category
    return keywords, taxonomy


async def command_collect_dcwp(args: argparse.Namespace, config: AppConfig) -> None:
    source, competitors, coverage = await DcwpIssuedLicensesSource(config.collection).collect()
    output = Path(args.output_dir)
    write_json_atomic(output / "source.json", source)
    write_jsonl_atomic(output / "competitors.jsonl", competitors)
    write_jsonl_atomic(output / "coverage.jsonl", coverage)
    write_json_atomic(
        output / "manifest.json",
        {
            "source_id": source.source_id,
            "competitor_count": len(competitors),
            "coverage_count": len(coverage),
            "limitations": [source.notes],
        },
    )
    emit({"status": "ok", "output_dir": str(output), "records": len(competitors)})


async def command_collect_market(args: argparse.Namespace, config: AppConfig) -> None:
    keywords, taxonomy = load_category_seeds(args.categories)
    boroughs = config.collection.boroughs
    overture_result, demand_result = await asyncio.gather(
        OverturePlacesSource(config.overture, boroughs).collect(taxonomy),
        GoogleAdsKeywordDemandSource(config.google_ads).collect(keywords, boroughs),
    )
    overture_source, competitors, coverage = overture_result
    demand_source, demand_signals = demand_result
    packet = create_evidence_packet(
        business=load_business(args.business),
        sources=[overture_source, demand_source],
        competitors=competitors,
        demand_signals=demand_signals,
        coverage=coverage,
    )
    output = Path(args.output_dir)
    write_json_atomic(output / "sources.json", packet.sources)
    write_jsonl_atomic(output / "competitors.jsonl", packet.competitors)
    write_jsonl_atomic(output / "demand.jsonl", packet.demand_signals)
    write_jsonl_atomic(output / "coverage.jsonl", packet.supply_coverage)
    write_json_atomic(output / "evidence-packet.json", packet)
    write_json_atomic(
        output / "collection-plan.json",
        {"keywords": keywords, "overture_taxonomy": taxonomy},
    )
    write_json_atomic(
        output / "manifest.json",
        {
            "packet_digest": packet.digest(),
            "competitor_count": len(packet.competitors),
            "multi_category_competitor_count": sum(bool(record.secondary_categories) for record in packet.competitors),
            "demand_count": len(packet.demand_signals),
            "coverage_count": len(packet.supply_coverage),
            "sources": [source.model_dump(mode="json") for source in packet.sources],
            "limitations": [source.notes for source in packet.sources if source.notes],
        },
    )
    emit(
        {
            "status": "ok",
            "output_dir": str(output),
            "packet": str(output / "evidence-packet.json"),
            "competitors": len(packet.competitors),
            "demand_signals": len(packet.demand_signals),
            "coverage": len(packet.supply_coverage),
        }
    )


async def command_build_packet(args: argparse.Namespace, config: AppConfig) -> None:
    packet = await build_evidence_packet(
        config=config,
        business=load_business(args.business),
        competitor_csvs=args.competitor_csv,
        demand_csvs=args.demand_csv,
        coverage_csvs=args.coverage_csv,
        dcwp_dirs=args.dcwp_dir,
        include_dcwp=args.include_dcwp,
    )
    write_json_atomic(args.output, packet)
    emit({"status": "ok", "packet": args.output, "digest": packet.digest()})


async def command_research(args: argparse.Namespace, config: AppConfig) -> None:
    result = await MarketIntelligenceWorkflow(config).research(load_business(args.business), args.question)
    write_json_atomic(
        args.output,
        {
            "result": result.value.model_dump(mode="json"),
            "metadata": result.public_metadata(),
        },
    )
    emit({"status": "ok", "output": args.output})


async def command_analyze(args: argparse.Namespace, config: AppConfig) -> None:
    packet = load_packet(args.packet)
    result = OpportunityAnalyzer(config.analysis).analyze(packet)
    write_json_atomic(args.output, result)
    emit(
        {
            "status": "ok",
            "output": args.output,
            "supported": len(result.top_underserved_categories),
            "priority_borough": result.priority_borough,
        }
    )


async def command_classify(args: argparse.Namespace, config: AppConfig) -> None:
    packet = load_packet(args.packet)
    taxonomy_payload = read_json(args.taxonomy)
    if not isinstance(taxonomy_payload, list) or not all(
        isinstance(item, str) and item.strip() for item in taxonomy_payload
    ):
        raise ValueError("taxonomy must be a JSON array of non-empty category strings")
    results = await MarketIntelligenceWorkflow(config).classify(
        packet, taxonomy=taxonomy_payload, batch_size=args.batch_size
    )
    if args.updated_packet:
        updated = apply_classifications(packet, [result.value for result in results])
        write_json_atomic(args.updated_packet, updated)
    write_json_atomic(
        args.output,
        {
            "batches": [result.value.model_dump(mode="json") for result in results],
            "metadata": [result.public_metadata() for result in results],
        },
    )
    emit({"status": "ok", "output": args.output, "batches": len(results)})


async def command_strategy(args: argparse.Namespace, config: AppConfig) -> None:
    packet = load_packet(args.packet)
    workflow = MarketIntelligenceWorkflow(config)
    result = await workflow.run_full(packet) if args.full else await workflow.run_strategy(packet)
    write_json_atomic(args.output, result)
    emit({"status": result["status"], "output": args.output})


async def command_evaluate(args: argparse.Namespace, config: AppConfig) -> None:
    del config
    report = run_eval_suite(args.suite)
    write_json_atomic(args.output, report)
    emit(
        {
            "status": "passed" if report.failed == 0 else "failed",
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "pass_rate": report.pass_rate,
            "output": args.output,
        }
    )
    if report.failed:
        raise WorkflowError(f"{report.failed} evaluation case(s) failed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nyc-market-intel",
        description="Evidence-based NYC product-category discovery using LiteLLM.",
    )
    parser.add_argument("--config", help="JSON configuration file")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--json-logs", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect-dcwp", help="Pull active DCWP licenses")
    collect.add_argument("--output-dir", required=True)
    collect.set_defaults(handler=command_collect_dcwp)

    collect_market = subparsers.add_parser(
        "collect-market",
        help="Pull Overture competitors/coverage and Google Ads demand",
    )
    collect_market.add_argument("--business", required=True)
    collect_market.add_argument("--categories", required=True)
    collect_market.add_argument("--output-dir", required=True)
    collect_market.set_defaults(handler=command_collect_market)

    build = subparsers.add_parser("build-packet", help="Build a validated evidence packet")
    build.add_argument("--business", required=True)
    build.add_argument("--competitor-csv", action="append", default=[])
    build.add_argument("--demand-csv", action="append", default=[])
    build.add_argument("--coverage-csv", action="append", default=[])
    build.add_argument(
        "--dcwp-dir",
        action="append",
        default=[],
        help="Previously collected directory containing source.json and JSONL files",
    )
    build.add_argument("--include-dcwp", action="store_true")
    build.add_argument("--output", required=True)
    build.set_defaults(handler=command_build_packet)

    research = subparsers.add_parser("research", help="Run sourced candidate research")
    research.add_argument("--business", required=True)
    research.add_argument("--question", required=True)
    research.add_argument("--output", required=True)
    research.set_defaults(handler=command_research)

    analyze = subparsers.add_parser("analyze", help="Run deterministic opportunity scoring")
    analyze.add_argument("--packet", required=True)
    analyze.add_argument("--output", required=True)
    analyze.set_defaults(handler=command_analyze)

    classify = subparsers.add_parser("classify", help="Bulk classify competitor records")
    classify.add_argument("--packet", required=True)
    classify.add_argument("--taxonomy", required=True)
    classify.add_argument("--batch-size", type=int, default=50)
    classify.add_argument(
        "--updated-packet",
        help="Write a packet with validated classifications applied",
    )
    classify.add_argument("--output", required=True)
    classify.set_defaults(handler=command_classify)

    strategy = subparsers.add_parser("strategy", help="Run model strategy stages")
    strategy.add_argument("--packet", required=True)
    strategy.add_argument("--full", action="store_true", help="Add consensus and ad copy")
    strategy.add_argument("--output", required=True)
    strategy.set_defaults(handler=command_strategy)

    evaluate = subparsers.add_parser("evaluate", help="Run the 20-case offline evaluation")
    evaluate.add_argument("--suite", default=str(DEFAULT_EVAL_SUITE))
    evaluate.add_argument("--output", required=True)
    evaluate.set_defaults(handler=command_evaluate)
    return parser


async def execute_args(args: argparse.Namespace) -> int:
    configure_logging(args.verbose, args.json_logs)
    try:
        config = AppConfig.from_file(args.config)
        await args.handler(args, config)
        return 0
    except (
        CollectionError,
        ModelStageError,
        WorkflowError,
        ValidationError,
        ValueError,
        TypeError,
        OSError,
    ) as exc:
        LOGGER.error("%s", exc)
        return 1


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return await execute_args(args)


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(async_main(argv))
    except KeyboardInterrupt:
        LOGGER.error("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())

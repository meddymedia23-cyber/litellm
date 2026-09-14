from __future__ import annotations

import asyncio
import csv
import hashlib
import http.client
import ipaddress
import json
import logging
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx

from .config import CollectionSettings, GoogleAdsSettings, OvertureSettings
from .models import (
    Borough,
    CompetitorRecord,
    CsvSourceProvenance,
    DemandSignal,
    EvidenceSource,
    EvidenceStatus,
    EvidenceUse,
    SourceType,
    SupplyCoverage,
)
from .normalization import (
    file_sha256,
    normalize_borough,
    normalize_category,
    optional_bool,
    optional_float,
    optional_int,
    optional_text,
    parse_datetime,
    stable_id,
)

LOGGER = logging.getLogger(__name__)


class CollectionError(RuntimeError):
    pass


class DcwpIssuedLicensesSource:
    """Collect active DCWP license records from NYC Open Data.

    This source measures supply only for categories that require a DCWP license. It
    must never be presented as a complete census of all NYC businesses.
    """

    FIELDS = (
        "license_nbr,business_name,business_category,license_type,license_status,"
        "address_building,address_street_name,address_city,address_state,address_zip,"
        "address_borough,latitude,longitude"
    )

    def __init__(self, settings: CollectionSettings, app_token: str | None = None):
        self.settings = settings
        self.app_token = app_token or os.getenv("SOCRATA_APP_TOKEN")

    async def collect(
        self,
    ) -> tuple[EvidenceSource, list[CompetitorRecord], list[SupplyCoverage]]:
        retrieved_at = datetime.now(timezone.utc)
        base = self.settings.socrata_base_url.rstrip("/")
        endpoint = f"{base}/resource/{self.settings.dcwp_dataset_id}.json"
        source_url = f"{base}/d/{self.settings.dcwp_dataset_id}"
        source = EvidenceSource(
            source_id=f"nyc-open-data:{self.settings.dcwp_dataset_id}",
            source_type=SourceType.NYC_OPEN_DATA,
            title="NYC DCWP Issued Licenses",
            url=source_url,
            retrieved_at=retrieved_at,
            status=EvidenceStatus.VERIFIED,
            evidence_use=EvidenceUse.PRODUCTION,
            decision_eligible=True,
            license_name="NYC Open Data Terms of Use",
            attribution="NYC Department of Consumer and Worker Protection",
            retention_allowed=True,
            provider_sharing_allowed=True,
            notes=(
                "Supply coverage is limited to business activities requiring a DCWP "
                "license; it is not a complete business census."
            ),
        )
        borough_values = [borough.value for borough in self.settings.boroughs]
        quoted = ",".join(f"'{value.replace(chr(39), chr(39) * 2)}'" for value in borough_values)
        where = f"license_status='Active' AND address_borough IN ({quoted})"
        headers = {"Accept": "application/json"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token

        rows: list[dict[str, Any]] = []
        offset = 0
        collection_complete = False
        async with httpx.AsyncClient(
            timeout=self.settings.timeout_seconds,
            follow_redirects=False,
            headers=headers,
        ) as client:
            while len(rows) < self.settings.maximum_records:
                limit = min(
                    self.settings.page_size,
                    self.settings.maximum_records - len(rows),
                )
                params = {
                    "$select": self.FIELDS,
                    "$where": where,
                    "$order": "license_nbr ASC",
                    "$limit": str(limit),
                    "$offset": str(offset),
                }
                url = f"{endpoint}?{urlencode(params)}"
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    page = response.json()
                except (httpx.HTTPError, json.JSONDecodeError) as exc:
                    raise CollectionError(f"NYC Open Data request failed: {exc}") from exc
                if not isinstance(page, list):
                    raise CollectionError("NYC Open Data returned a non-list response")
                rows.extend(page)
                if len(page) < limit:
                    collection_complete = True
                    break
                offset += len(page)

        if not collection_complete:
            source = source.model_copy(
                update={
                    "notes": (
                        f"{source.notes} Collection stopped at maximum_records="
                        f"{self.settings.maximum_records}; coverage is incomplete."
                    )
                }
            )
        competitors = [self._to_competitor(row, source, retrieved_at) for row in rows]
        counts = Counter((item.borough, item.primary_category) for item in competitors)
        coverage = [
            SupplyCoverage(
                coverage_id=stable_id("coverage", source.source_id, borough.value, category),
                category=category,
                borough=borough,
                query_completed=collection_complete,
                result_count=count,
                source_id=source.source_id,
                observed_at=retrieved_at,
                query=f"Active DCWP licenses in {borough.value} for {category}",
            )
            for (borough, category), count in sorted(counts.items(), key=lambda item: (item[0][0].value, item[0][1]))
        ]
        LOGGER.info("collected %d active DCWP license records", len(competitors))
        return source, competitors, coverage

    @staticmethod
    def _to_competitor(row: dict[str, Any], source: EvidenceSource, observed_at: datetime) -> CompetitorRecord:
        building = optional_text(row.get("address_building"))
        street = optional_text(row.get("address_street_name"))
        city = optional_text(row.get("address_city"))
        state = optional_text(row.get("address_state"))
        zip_code = optional_text(row.get("address_zip"))
        line_one = " ".join(part for part in (building, street) if part)
        line_two = ", ".join(part for part in (city, state, zip_code) if part)
        address = ", ".join(part for part in (line_one, line_two) if part) or None
        license_number = str(row.get("license_nbr") or "").strip()
        category = normalize_category(row.get("business_category"))
        borough = normalize_borough(row.get("address_borough"))
        return CompetitorRecord(
            record_id=stable_id("dcwp", license_number, row.get("business_name")),
            competitor_name=str(row.get("business_name") or "Unknown license holder").strip(),
            borough=borough,
            address=address,
            latitude=optional_float(row.get("latitude")),
            longitude=optional_float(row.get("longitude")),
            primary_category=category,
            source_id=source.source_id,
            source_url=source.url,
            observed_at=observed_at,
            external_id=license_number or None,
        )


def _apply_overture_category_mapping(
    records: list[CompetitorRecord],
    normalized_taxonomy: dict[str, set[str]],
) -> list[CompetitorRecord]:
    return [
        record.model_copy(
            update={
                "primary_category": matches[0],
                "secondary_categories": matches[1:],
            }
        )
        for record in records
        if (
            matches := sorted(
                category
                for category, taxonomy_labels in normalized_taxonomy.items()
                if {record.primary_category, *record.secondary_categories} & taxonomy_labels
            )
        )
    ]


def _overture_coverage_counts(
    records: list[CompetitorRecord],
    requested: set[str],
) -> Counter[tuple[Borough, str]]:
    return Counter(
        (record.borough, category)
        for record in records
        for category in {record.primary_category, *record.secondary_categories} & requested
    )


class OverturePlacesSource:
    """Collect open place records and complete category coverage from Overture Maps."""

    BOUNDARY_URL = "https://data.cityofnewyork.us/resource/{dataset}.json?$limit=10"

    def __init__(
        self,
        settings: OvertureSettings,
        boroughs: list[Borough],
    ):
        self.settings = settings
        self.boroughs = boroughs

    async def collect(
        self, category_taxonomy: dict[str, list[str]] | None = None
    ) -> tuple[EvidenceSource, list[CompetitorRecord], list[SupplyCoverage]]:
        executable = shutil.which(self.settings.executable)
        if executable is None:
            raise CollectionError("overturemaps executable not found; install the optional overturemaps dependency")
        retrieved_at = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory(prefix="nyc-overture-") as temp_dir:
            output = Path(temp_dir) / "places.geojsonseq"
            bbox = ",".join(str(value) for value in self.settings.bbox)
            command = [
                executable,
                "download",
                f"--bbox={bbox}",
                "-f",
                "geojsonseq",
                "--type=place",
                "-o",
                str(output),
            ]
            try:
                await asyncio.to_thread(
                    subprocess.run,
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.settings.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise CollectionError("Overture download timed out") from exc
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "unknown error")[-1000:]
                raise CollectionError(f"Overture download failed: {detail}") from exc
            if not output.is_file():
                raise CollectionError("Overture download did not create its output file")
            boundaries = await self._load_boundaries()
            records = self._parse_places(output, boundaries, retrieved_at)
            normalized_taxonomy = {
                normalize_category(category): {normalize_category(label.replace("_", " ")) for label in labels}
                for category, labels in (category_taxonomy or {}).items()
            }
            if normalized_taxonomy:
                records = _apply_overture_category_mapping(records, normalized_taxonomy)
            content_hash = file_sha256(output)

        source = EvidenceSource(
            source_id=stable_id("overture", content_hash),
            source_type=SourceType.COMPETITOR_EXPORT,
            title="Overture Maps Places",
            url="https://docs.overturemaps.org/guides/places/",
            retrieved_at=retrieved_at,
            status=EvidenceStatus.VERIFIED,
            evidence_use=EvidenceUse.PRODUCTION,
            decision_eligible=True,
            content_hash=content_hash,
            license_name="CDLA Permissive 2.0 and Apache 2.0 by source",
            attribution="Overture Maps Foundation",
            retention_allowed=True,
            provider_sharing_allowed=True,
            notes=(
                "Open POI supply source. Overture documents possible duplicates, junk, and "
                "incomplete properties; home-based and non-public competitors may be absent."
            ),
        )
        records = [
            record.model_copy(update={"source_id": source.source_id, "source_url": source.url}) for record in records
        ]
        requested = (
            sorted(normalized_taxonomy)
            if normalized_taxonomy
            else sorted({record.primary_category for record in records})
        )
        counts = _overture_coverage_counts(records, set(requested))
        coverage = [
            SupplyCoverage(
                coverage_id=stable_id("coverage", source.source_id, borough.value, category),
                category=category,
                borough=borough,
                query_completed=True,
                result_count=counts[(borough, category)],
                source_id=source.source_id,
                observed_at=retrieved_at,
                query=(
                    f"Overture place taxonomy category {category} inside the official "
                    f"NYC {borough.value} boundary; minimum confidence "
                    f"{self.settings.minimum_confidence}"
                ),
            )
            for borough in self.boroughs
            for category in requested
        ]
        LOGGER.info(
            "collected %d Overture places and %d coverage rows",
            len(records),
            len(coverage),
        )
        return source, records, coverage

    async def _load_boundaries(self) -> dict[Borough, list]:
        url = self.BOUNDARY_URL.format(dataset=self.settings.boundary_dataset_id)
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
                response = await client.get(url)
                response.raise_for_status()
                rows = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise CollectionError(f"NYC borough boundary request failed: {exc}") from exc
        output: dict[Borough, list] = {}
        for row in rows:
            try:
                borough = normalize_borough(row["boroname"])
                geometry = row["the_geom"]
                if geometry["type"] != "MultiPolygon":
                    raise ValueError("expected MultiPolygon boundary")
                output[borough] = geometry["coordinates"]
            except (KeyError, TypeError, ValueError) as exc:
                raise CollectionError(f"invalid NYC borough boundary row: {exc}") from exc
        missing = set(self.boroughs) - set(output)
        if missing:
            raise CollectionError(f"NYC boundary data omitted boroughs: {sorted(item.value for item in missing)}")
        return output

    def _parse_places(
        self,
        path: Path,
        boundaries: dict[Borough, list],
        observed_at: datetime,
    ) -> list[CompetitorRecord]:
        records: list[CompetitorRecord] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    feature = json.loads(line)
                    properties = feature.get("properties") or {}
                    geometry = feature.get("geometry") or {}
                    coordinates = geometry.get("coordinates") or []
                    if geometry.get("type") != "Point" or len(coordinates) < 2:
                        continue
                    longitude, latitude = float(coordinates[0]), float(coordinates[1])
                    borough = self._borough_for_point(longitude, latitude, boundaries)
                    if borough is None:
                        continue
                    confidence = properties.get("confidence")
                    if confidence is None or float(confidence) < self.settings.minimum_confidence:
                        continue
                    if properties.get("operating_status") == "permanently_closed":
                        continue
                    taxonomy = properties.get("taxonomy") or {}
                    category_value = (
                        taxonomy.get("primary")
                        or properties.get("basic_category")
                        or (properties.get("categories") or {}).get("primary")
                    )
                    names = properties.get("names") or {}
                    name = names.get("primary")
                    external_id = str(feature.get("id") or properties.get("id") or "").strip()
                    if not category_value or not name or not external_id:
                        continue
                    addresses = properties.get("addresses") or []
                    address_data = addresses[0] if addresses else {}
                    address = optional_text(address_data.get("freeform"))
                    locality = optional_text(address_data.get("locality"))
                    postcode = optional_text(address_data.get("postcode"))
                    formatted_address = ", ".join(item for item in (address, locality, postcode) if item) or None
                    category = normalize_category(str(category_value).replace("_", " "))
                    alternate = taxonomy.get("alternate") or []
                    records.append(
                        CompetitorRecord(
                            record_id=stable_id("overture-place", external_id),
                            competitor_name=str(name),
                            borough=borough,
                            neighborhood=locality,
                            address=formatted_address,
                            latitude=latitude,
                            longitude=longitude,
                            primary_category=category,
                            secondary_categories=[
                                normalize_category(str(item).replace("_", " ")) for item in alternate[:20]
                            ],
                            source_id="overture:pending",
                            source_url="https://docs.overturemaps.org/guides/places/",
                            observed_at=observed_at,
                            external_id=external_id,
                        )
                    )
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise CollectionError(f"invalid Overture GeoJSON sequence line {line_number}: {exc}") from exc
        return records

    def _borough_for_point(self, longitude: float, latitude: float, boundaries: dict[Borough, list]) -> Borough | None:
        for borough in self.boroughs:
            if self._inside_multipolygon(longitude, latitude, boundaries.get(borough, [])):
                return borough
        return None

    @classmethod
    def _inside_multipolygon(cls, longitude: float, latitude: float, multipolygon: list) -> bool:
        for polygon in multipolygon:
            if not polygon or not cls._inside_ring(longitude, latitude, polygon[0]):
                continue
            if any(cls._inside_ring(longitude, latitude, hole) for hole in polygon[1:]):
                continue
            return True
        return False

    @staticmethod
    def _inside_ring(longitude: float, latitude: float, ring: list) -> bool:
        inside = False
        previous = ring[-1]
        for current in ring:
            x1, y1 = previous[:2]
            x2, y2 = current[:2]
            crosses = (y1 > latitude) != (y2 > latitude)
            if crosses:
                intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
                if longitude < intersection:
                    inside = not inside
            previous = current
        return inside


class GoogleAdsKeywordDemandSource:
    """Pull borough-targeted keyword demand through the official Google Ads API."""

    def __init__(self, settings: GoogleAdsSettings):
        self.settings = settings

    async def collect(
        self,
        category_keywords: dict[str, list[str]],
        boroughs: list[Borough],
    ) -> tuple[EvidenceSource, list[DemandSignal]]:
        if not self.settings.customer_id:
            raise CollectionError("GOOGLE_ADS_CUSTOMER_ID is required for Google Ads demand collection")
        normalized = {
            normalize_category(category): list(
                dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip())
            )[: self.settings.maximum_keywords_per_category]
            for category, keywords in category_keywords.items()
        }
        if not normalized or any(not keywords for keywords in normalized.values()):
            raise CollectionError("every category requires at least one non-empty Google Ads seed keyword")
        return await asyncio.to_thread(self._collect_sync, normalized, boroughs)

    def _collect_sync(
        self,
        category_keywords: dict[str, list[str]],
        boroughs: list[Borough],
    ) -> tuple[EvidenceSource, list[DemandSignal]]:
        try:
            from google.ads.googleads.client import GoogleAdsClient
            from google.ads.googleads.errors import GoogleAdsException
        except ImportError as exc:
            raise CollectionError("google-ads package is required for live demand collection") from exc

        try:
            client = GoogleAdsClient.load_from_env()
            geo_resources = {borough: self._resolve_geo_target(client, borough) for borough in boroughs}
            service = client.get_service("KeywordPlanIdeaService")
            google_ads_service = client.get_service("GoogleAdsService")
            retrieved_at = datetime.now(timezone.utc)
            period_end = retrieved_at
            period_start = retrieved_at - timedelta(days=365)
            query_fingerprint = json.dumps(
                {
                    "categories": category_keywords,
                    "boroughs": [borough.value for borough in boroughs],
                    "language_id": self.settings.language_id,
                },
                sort_keys=True,
            )
            source_id = stable_id("google-ads", query_fingerprint, retrieved_at.date())
            signals: list[DemandSignal] = []
            for borough in boroughs:
                for category, keywords in category_keywords.items():
                    request = client.get_type("GenerateKeywordIdeasRequest")
                    request.customer_id = self.settings.customer_id
                    request.language = google_ads_service.language_constant_path(self.settings.language_id)
                    request.geo_target_constants.append(geo_resources[borough])
                    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
                    request.keyword_seed.keywords.extend(keywords)
                    response = service.generate_keyword_ideas(request=request)
                    unique: dict[str, int] = {}
                    for result in response:
                        text = str(result.text).strip().casefold()
                        metrics = result.keyword_idea_metrics
                        searches = int(metrics.avg_monthly_searches or 0)
                        if text:
                            unique[text] = max(unique.get(text, 0), searches)
                    signals.append(
                        DemandSignal(
                            signal_id=stable_id(
                                "google-ads-demand",
                                source_id,
                                borough.value,
                                category,
                            ),
                            category=category,
                            borough=borough,
                            metric="monthly_searches",
                            value=float(sum(unique.values())),
                            period_start=period_start,
                            period_end=period_end,
                            source_id=source_id,
                            confidence=1.0,
                        )
                    )
        except GoogleAdsException as exc:
            request_id = getattr(exc, "request_id", "unknown")
            raise CollectionError(f"Google Ads demand request failed; request_id={request_id}") from exc
        except (AttributeError, TypeError, ValueError) as exc:
            raise CollectionError(f"Google Ads response could not be normalized: {exc}") from exc

        source = EvidenceSource(
            source_id=source_id,
            source_type=SourceType.GOOGLE_ADS_API,
            title="Google Ads KeywordPlanIdeaService",
            url="https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas",
            retrieved_at=retrieved_at,
            status=EvidenceStatus.VERIFIED,
            evidence_use=EvidenceUse.PRODUCTION,
            decision_eligible=True,
            license_name="Google Ads API Terms",
            attribution="Google Ads",
            retention_allowed=True,
            provider_sharing_allowed=False,
            notes=(
                "Category demand is the sum of unique keyword ideas returned for each "
                "category seed and borough geo target. Overlapping intent between different "
                "category requests may remain."
            ),
        )
        return source, signals

    @staticmethod
    def _resolve_geo_target(client: Any, borough: Borough) -> str:
        service = client.get_service("GeoTargetConstantService")
        request = client.get_type("SuggestGeoTargetConstantsRequest")
        request.locale = "en"
        request.country_code = "US"
        request.location_names.names.append(f"{borough.value}, New York")
        response = service.suggest_geo_target_constants(request=request)
        suggestions = list(response.geo_target_constant_suggestions)
        if not suggestions:
            raise CollectionError(f"Google Ads returned no geo target for {borough.value}")
        preferred_names = {
            borough.value.casefold(),
            f"{borough.value} county".casefold(),
        }
        ranked = sorted(
            suggestions,
            key=lambda item: (
                str(item.geo_target_constant.name).casefold() not in preferred_names,
                "new york" not in str(item.geo_target_constant.canonical_name).casefold(),
            ),
        )
        target = ranked[0].geo_target_constant
        if "new york" not in str(target.canonical_name).casefold():
            raise CollectionError(f"Google Ads geo target for {borough.value} was ambiguous: {target.canonical_name}")
        return str(target.resource_name)


class CsvImporter:
    """Import user-controlled competitor, demand, and coverage exports."""

    @staticmethod
    def source_for_file(path: str | Path, source_type: SourceType, title: str) -> EvidenceSource:
        file_path = Path(path).resolve()
        stat = file_path.stat()
        observed = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        content_hash = file_sha256(file_path)
        provenance_path = Path(f"{file_path}.source.json")
        provenance: CsvSourceProvenance | None = None
        if provenance_path.is_file():
            try:
                provenance = CsvSourceProvenance.model_validate(json.loads(provenance_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise CollectionError(f"invalid CSV provenance file {provenance_path}: {exc}") from exc
            if provenance.content_hash != content_hash:
                raise CollectionError(
                    f"CSV provenance hash mismatch for {file_path}; expected "
                    f"{provenance.content_hash}, received {content_hash}"
                )
        return EvidenceSource(
            source_id=stable_id("file", file_path, content_hash),
            source_type=source_type,
            title=title,
            url=file_path.as_uri(),
            retrieved_at=observed,
            status=EvidenceStatus.VERIFIED,
            evidence_use=provenance.evidence_use if provenance else EvidenceUse.UNKNOWN,
            decision_eligible=provenance.decision_eligible if provenance else False,
            content_hash=content_hash,
            license_name=provenance.license_name if provenance else None,
            attribution=provenance.attribution if provenance else None,
            retention_allowed=provenance.retention_allowed if provenance else False,
            provider_sharing_allowed=provenance.provider_sharing_allowed if provenance else False,
            notes=(
                provenance.notes
                if provenance
                else "No hash-bound .source.json provenance file was supplied; this CSV is not decision eligible."
            ),
        )

    @staticmethod
    def _rows(path: str | Path) -> list[dict[str, str]]:
        file_path = Path(path)
        try:
            with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except FileNotFoundError as exc:
            raise CollectionError(f"CSV file not found: {file_path}") from exc
        if not rows:
            raise CollectionError(f"CSV file has no data rows: {file_path}")
        return rows

    @classmethod
    def competitors(cls, path: str | Path) -> tuple[EvidenceSource, list[CompetitorRecord]]:
        source = cls.source_for_file(path, SourceType.COMPETITOR_EXPORT, "Competitor listing export")
        records: list[CompetitorRecord] = []
        for index, row in enumerate(cls._rows(path), start=2):
            try:
                name = row.get("competitor_name") or row.get("business_name")
                category = row.get("primary_category") or row.get("category")
                external_id = optional_text(row.get("external_id"))
                record_id = optional_text(row.get("record_id")) or stable_id(
                    "competitor", source.source_id, index, name
                )
                secondary = [
                    normalize_category(item)
                    for item in str(row.get("secondary_categories") or "").split("|")
                    if item.strip()
                ]
                records.append(
                    CompetitorRecord(
                        record_id=record_id,
                        competitor_name=str(name or "").strip(),
                        borough=normalize_borough(row.get("borough")),
                        neighborhood=optional_text(row.get("neighborhood")),
                        address=optional_text(row.get("address")),
                        latitude=optional_float(row.get("latitude")),
                        longitude=optional_float(row.get("longitude")),
                        primary_category=normalize_category(category),
                        secondary_categories=secondary,
                        price_min=optional_float(row.get("price_min")),
                        price_max=optional_float(row.get("price_max")),
                        rating=optional_float(row.get("rating")),
                        review_count=optional_int(row.get("review_count")),
                        pickup=optional_bool(row.get("pickup")),
                        delivery=optional_bool(row.get("delivery")),
                        delivery_fee=optional_float(row.get("delivery_fee")),
                        delivery_radius_miles=optional_float(row.get("delivery_radius_miles")),
                        main_offer=optional_text(row.get("main_offer")),
                        ad_message=optional_text(row.get("ad_message")),
                        source_id=source.source_id,
                        source_url=optional_text(row.get("source_url")) or source.url,
                        observed_at=parse_datetime(row.get("observed_at"), default=source.retrieved_at),
                        external_id=external_id,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise CollectionError(f"invalid competitor CSV row {index}: {exc}") from exc
        return source, records

    @classmethod
    def demand(cls, path: str | Path) -> tuple[EvidenceSource, list[DemandSignal]]:
        source = cls.source_for_file(path, SourceType.GOOGLE_ADS_EXPORT, "Category demand export")
        signals: list[DemandSignal] = []
        for index, row in enumerate(cls._rows(path), start=2):
            try:
                category = normalize_category(row.get("category"))
                borough = normalize_borough(row.get("borough"))
                metric = str(row.get("metric") or "monthly_searches").strip()
                value = optional_float(row.get("value"))
                if value is None:
                    raise ValueError("value is required")
                confidence = optional_float(row.get("confidence"))
                signals.append(
                    DemandSignal(
                        signal_id=optional_text(row.get("signal_id"))
                        or stable_id("demand", source.source_id, index, category, borough),
                        category=category,
                        borough=borough,
                        metric=metric,
                        value=value,
                        period_start=parse_datetime(row.get("period_start")),
                        period_end=parse_datetime(row.get("period_end")),
                        source_id=source.source_id,
                        confidence=1.0 if confidence is None else confidence,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise CollectionError(f"invalid demand CSV row {index}: {exc}") from exc
        return source, signals

    @classmethod
    def coverage(cls, path: str | Path) -> tuple[EvidenceSource, list[SupplyCoverage]]:
        source = cls.source_for_file(path, SourceType.COMPETITOR_EXPORT, "Supply coverage export")
        items: list[SupplyCoverage] = []
        for index, row in enumerate(cls._rows(path), start=2):
            try:
                category = normalize_category(row.get("category"))
                borough = normalize_borough(row.get("borough"))
                completed = optional_bool(row.get("query_completed"))
                if completed is None:
                    raise ValueError("query_completed is required")
                count = optional_int(row.get("result_count"))
                if count is None:
                    raise ValueError("result_count is required")
                items.append(
                    SupplyCoverage(
                        coverage_id=optional_text(row.get("coverage_id"))
                        or stable_id("coverage", source.source_id, index, category, borough),
                        category=category,
                        borough=borough,
                        query_completed=completed,
                        result_count=count,
                        source_id=source.source_id,
                        observed_at=parse_datetime(row.get("observed_at"), default=source.retrieved_at),
                        query=str(row.get("query") or f"{category} in {borough.value}"),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise CollectionError(f"invalid coverage CSV row {index}: {exc}") from exc
        return source, items


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, pinned_ip: str, *, port: int, timeout: float):
        super().__init__(host, port=port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port),
            timeout=self.timeout,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, pinned_ip: str, *, port: int, timeout: float):
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._pinned_ip, self.port),
            timeout=self.timeout,
        )
        try:
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except Exception:
            raw_socket.close()
            raise


def _fetch_public_http_source(
    url: str,
    *,
    timeout_seconds: float,
    maximum_bytes: int,
) -> str:
    current_url = url
    redirect_statuses = {301, 302, 303, 307, 308}
    for _ in range(4):
        parsed = urlparse(current_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("verification URL must be public HTTP(S)")
        if parsed.username or parsed.password:
            raise ValueError("verification URL cannot contain credentials")
        if parsed.port not in {None, 80, 443}:
            raise ValueError("verification URL uses a disallowed port")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        if not addresses:
            raise ValueError("verification host did not resolve")
        resolved_ips = sorted({address[4][0] for address in addresses})
        for resolved_ip in resolved_ips:
            ip = ipaddress.ip_address(resolved_ip)
            if not ip.is_global:
                raise ValueError(f"verification host resolved to non-public address {ip}")
        pinned_ip = resolved_ips[0]
        connection_type = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
        connection = connection_type(
            parsed.hostname,
            pinned_ip,
            port=port,
            timeout=timeout_seconds,
        )
        path = parsed.path or "/"
        if parsed.params:
            path += f";{parsed.params}"
        if parsed.query:
            path += f"?{parsed.query}"
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Accept": "*/*",
                    "User-Agent": "LiteLLM-NYC-Market-Intelligence/1.0",
                },
            )
            response = connection.getresponse()
            if response.status in redirect_statuses:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("redirect response omitted Location")
                current_url = urljoin(current_url, location)
                continue
            if response.status >= 400:
                raise ValueError(f"source returned HTTP {response.status}")
            digest = hashlib.sha256()
            received = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                received += len(chunk)
                if received > maximum_bytes:
                    raise ValueError(f"source exceeds verification limit of {maximum_bytes} bytes")
                digest.update(chunk)
            return digest.hexdigest()
        finally:
            connection.close()
    raise ValueError("source exceeded three redirects")


async def verify_http_sources(
    sources: list[EvidenceSource],
    timeout_seconds: float = 15.0,
    concurrency: int = 5,
    maximum_bytes: int = 2_000_000,
) -> list[EvidenceSource]:
    semaphore = asyncio.Semaphore(concurrency)

    async def verify(source: EvidenceSource) -> EvidenceSource:
        async with semaphore:
            try:
                digest = await asyncio.to_thread(
                    _fetch_public_http_source,
                    source.url,
                    timeout_seconds=timeout_seconds,
                    maximum_bytes=maximum_bytes,
                )
                return source.model_copy(
                    update={
                        "status": EvidenceStatus.VERIFIED,
                        "content_hash": digest,
                    }
                )
            except (http.client.HTTPException, OSError, ValueError) as exc:
                LOGGER.warning("source verification failed for %s: %s", source.url, type(exc).__name__)
                return source.model_copy(update={"status": EvidenceStatus.FAILED})

    return await asyncio.gather(*(verify(source) for source in sources))

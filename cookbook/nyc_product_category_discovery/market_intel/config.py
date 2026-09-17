from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator

from .models import Borough, StrictModel


class ModelSettings(StrictModel):
    research: str = "perplexity/sonar-pro"
    classification: str = "deepseek/deepseek-v4-pro"
    analysis: str = "gemini/gemini-3.1-pro-preview"
    copy_model: str = Field(default="anthropic/claude-sonnet-5", alias="copy")
    synthesis: str = "openai/gpt-6-astra"
    consensus: list[str] = Field(
        default_factory=lambda: [
            "perplexity/sonar-pro",
            "deepseek/deepseek-v4-pro",
            "gemini/gemini-3.1-pro-preview",
            "anthropic/claude-sonnet-5",
        ],
        min_length=2,
    )

    @model_validator(mode="after")
    def validate_consensus_models(self) -> ModelSettings:
        if len(set(self.consensus)) != len(self.consensus):
            raise ValueError("consensus model identifiers must be unique")
        return self


class CollectionSettings(StrictModel):
    socrata_base_url: str = "https://data.cityofnewyork.us"
    dcwp_dataset_id: str = Field(default="w7w3-xahh", pattern=r"^[a-z0-9]{4}-[a-z0-9]{4}$")
    page_size: int = Field(default=1000, ge=1, le=50000)
    maximum_records: int = Field(default=100000, ge=1, le=1000000)
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    boroughs: list[Borough] = Field(default_factory=lambda: [Borough.BRONX, Borough.QUEENS], min_length=1)

    @model_validator(mode="after")
    def validate_socrata_endpoint(self) -> CollectionSettings:
        parsed = urlparse(self.socrata_base_url)
        if parsed.scheme != "https" or parsed.hostname != "data.cityofnewyork.us":
            raise ValueError("socrata_base_url must be https://data.cityofnewyork.us")
        return self


class OvertureSettings(StrictModel):
    executable: str = "overturemaps"
    bbox: tuple[float, float, float, float] = (-74.05, 40.49, -73.68, 40.93)
    boundary_dataset_id: str = Field(default="gthc-hcne", pattern=r"^[a-z0-9]{4}-[a-z0-9]{4}$")
    minimum_confidence: float = Field(default=0.6, ge=0.2, le=1)
    timeout_seconds: int = Field(default=900, ge=30, le=3600)

    @model_validator(mode="after")
    def validate_bbox(self) -> OvertureSettings:
        west, south, east, north = self.bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("overture bbox must be west,south,east,north")
        return self


class GoogleAdsSettings(StrictModel):
    customer_id: str | None = Field(default=None, pattern=r"^\d{10}$")
    language_id: str = Field(default="1000", pattern=r"^\d+$")
    maximum_keywords_per_category: int = Field(default=20, ge=1, le=200)


class AnalysisSettings(StrictModel):
    minimum_demand_confidence: float = Field(default=0.6, ge=0, le=1)
    minimum_demand_value: float = Field(default=1.0, ge=0)
    maximum_data_age_days: int = Field(default=400, ge=1, le=3650)
    demand_weight: float = Field(default=0.55, ge=0, le=1)
    supply_gap_weight: float = Field(default=0.45, ge=0, le=1)
    competitor_weakness_weight: float = Field(default=0.0, ge=0, le=1)
    business_fit_weight: float = Field(default=0.0, ge=0, le=1)
    minimum_supported_categories: int = Field(default=2, ge=1, le=100)

    @model_validator(mode="after")
    def validate_weights(self) -> AnalysisSettings:
        total = self.demand_weight + self.supply_gap_weight + self.competitor_weakness_weight + self.business_fit_weight
        if abs(total - 1.0) > 1e-9:
            raise ValueError("analysis weights must sum to 1.0")
        return self


class RuntimeSettings(StrictModel):
    concurrency: int = Field(default=4, ge=1, le=32)
    timeout_seconds: float = Field(default=120.0, gt=0, le=900)
    retries: int = Field(default=2, ge=0, le=10)
    temperature: float | None = Field(default=None, ge=0, le=2)
    proxy_url: str | None = None
    proxy_key: SecretStr | None = None


class AppConfig(StrictModel):
    models: ModelSettings = Field(default_factory=ModelSettings)
    collection: CollectionSettings = Field(default_factory=CollectionSettings)
    overture: OvertureSettings = Field(default_factory=OvertureSettings)
    google_ads: GoogleAdsSettings = Field(default_factory=GoogleAdsSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> AppConfig:
        config_path = Path(path) if path else None
        payload: dict = {}
        if config_path:
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise ValueError(f"configuration file not found: {config_path}") from exc
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON configuration: {exc}") from exc

        runtime = payload.setdefault("runtime", {})
        google_ads = payload.setdefault("google_ads", {})
        if os.getenv("GOOGLE_ADS_CUSTOMER_ID"):
            google_ads["customer_id"] = os.environ["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "")
        if os.getenv("LITELLM_PROXY_URL"):
            runtime["proxy_url"] = os.environ["LITELLM_PROXY_URL"]
        if os.getenv("LITELLM_PROXY_API_KEY"):
            runtime["proxy_key"] = os.environ["LITELLM_PROXY_API_KEY"]
        return cls.model_validate(payload)

    def public_snapshot(self) -> dict:
        snapshot = self.model_dump(mode="json", exclude={"runtime": {"proxy_key"}})
        snapshot.setdefault("runtime", {})["proxy_key_configured"] = bool(self.runtime.proxy_key)
        return snapshot

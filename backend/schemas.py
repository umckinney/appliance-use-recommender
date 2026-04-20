"""Pydantic request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class AppliancePreset(BaseModel):
    name: str
    slug: str
    cycle_kwh: float
    cycle_minutes: int


class ApplianceIn(BaseModel):
    name: str
    slug: str
    cycle_kwh: float = Field(gt=0)
    cycle_minutes: int = Field(gt=0)
    notes: str | None = None


class ApplianceOut(ApplianceIn):
    id: int
    model_config = ConfigDict(from_attributes=True)


class OnboardRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=255)
    address: str = Field(..., max_length=500)
    postal_code: str | None = Field(
        None, max_length=20
    )  # extracted by frontend; used as geocode fallback
    utility_id: str = Field(..., max_length=100)
    # Tier 2 utility metadata (populated from /utilities/search for eia_* utility_ids)
    utility_name: str | None = Field(None, max_length=256)
    utility_eia_id: int | None = None
    utility_rate_avg: float | None = None
    utility_tier: int | None = None
    rate_plan: str = "tou_residential"
    net_metering: bool = False
    has_solar: bool = False
    solar_capacity_kw: float | None = None
    solar_tilt_deg: float | None = None
    solar_azimuth_deg: float | None = None
    solaredge_site_id: str | None = None
    solaredge_api_key: str | None = None
    optimization_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    appliances: list[ApplianceIn] = []


class OnboardResponse(BaseModel):
    api_key: str
    message: str
    location_precise: bool = True  # False when ZIP centroid was used as fallback
    location_warning: str | None = None  # human-readable explanation of fallback


class RecommendWindow(BaseModel):
    hour_utc: str  # ISO8601 hour start
    hour_local: str  # human-readable local time
    rate_usd_kwh: float
    carbon_g_kwh: float
    solar_kw: float  # current/forecasted solar generation at that hour
    net_cost_usd: float  # cost after net metering credit
    carbon_kg: float  # carbon impact for the appliance cycle
    score: float  # combined score (lower = better)


class RecommendResponse(BaseModel):
    appliance: str
    text: str  # natural-language recommendation (for Siri)
    best_windows: list[RecommendWindow]
    current_window: RecommendWindow
    cost_now_usd: float
    cost_best_usd: float
    carbon_now_kg: float
    carbon_best_kg: float
    data_sources: list[str]


class AllRecommendResponse(BaseModel):
    text: str
    best_shared_start: str
    per_appliance: list[RecommendResponse]


class PreferencesUpdate(BaseModel):
    optimization_weight: float = Field(..., ge=0.0, le=1.0)


class ModelSearchResult(BaseModel):
    brand: str
    model: str
    cycle_kwh: float
    cycle_minutes: int | None  # None = user must confirm (dishwasher/washer)


class StatusResponse(BaseModel):
    grid_zone: str
    carbon_intensity_g_kwh: float
    carbon_label: str  # "very clean" / "clean" / "moderate" / "dirty" / "very dirty"
    current_rate_usd_kwh: float
    rate_period: str  # "off-peak" / "mid-peak" / "peak"
    solar_kw: float | None  # None if no solar
    timestamp: str


class ForecastHour(BaseModel):
    hour_local: str
    carbon_g_kwh: float
    rate_usd_kwh: float
    rate_period: str
    solar_kw: float | None


class ForecastResponse(BaseModel):
    hours: list[ForecastHour]  # 24h ahead
    best_window_start: str
    utility_id: str


class UtilitySearchResult(BaseModel):
    eia_id: int
    utility_name: str
    state: str | None
    ownership_type: str | None
    residential_rate_avg: float | None
    source_year: int | None
    is_primary: bool
    utility_id: str  # "eia_{eia_id}" — use as utility_id when onboarding


class UtilitySearchResponse(BaseModel):
    zipcode: str
    utilities: list[UtilitySearchResult]
    warning: str | None  # Texas retail choice / CA CCA advisory


class DataSourceInfo(BaseModel):
    source: str
    tier: int | None = None  # 1 = YAML/URDB TOU, 2 = flat CSV avg
    detail: str | None = None
    freshness: str | None = None  # ISO8601 timestamp of last update


class DataSourcesResponse(BaseModel):
    utility: DataSourceInfo
    carbon: DataSourceInfo
    solar: DataSourceInfo
    rates: DataSourceInfo


# Common presets shown during onboarding
APPLIANCE_PRESETS: list[AppliancePreset] = [
    AppliancePreset(name="Dishwasher", slug="dishwasher", cycle_kwh=1.5, cycle_minutes=90),
    AppliancePreset(name="Clothes Washer", slug="washer", cycle_kwh=0.5, cycle_minutes=45),
    AppliancePreset(name="Electric Dryer", slug="dryer", cycle_kwh=5.0, cycle_minutes=60),
    AppliancePreset(
        name="EV Charger (Level 2)", slug="ev_charger", cycle_kwh=25.0, cycle_minutes=240
    ),
    AppliancePreset(name="Pool Pump", slug="pool_pump", cycle_kwh=1.5, cycle_minutes=60),
    AppliancePreset(name="HVAC (1 hour)", slug="hvac", cycle_kwh=3.5, cycle_minutes=60),
]

"""SQLAlchemy models for FlowShift."""

import secrets
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(256), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Location
    address: Mapped[str | None] = mapped_column(Text)  # full street address
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str | None] = mapped_column(String(64))

    # Utility — Tier 1 (YAML / URDB) uses utility_id; Tier 2 uses utility_eia_id + utility_rate_avg
    utility_id: Mapped[str | None] = mapped_column(
        String(64)
    )  # e.g. "seattle_city_light" or "eia_123"
    utility_name: Mapped[str | None] = mapped_column(String(256))
    utility_eia_id: Mapped[int | None] = mapped_column(Integer)
    utility_rate_avg: Mapped[float | None] = mapped_column(Float)  # $/kWh flat avg (Tier 2 only)
    utility_tier: Mapped[int | None] = mapped_column(Integer)  # 1 = TOU YAML/URDB, 2 = flat avg CSV
    rate_plan: Mapped[str | None] = mapped_column(String(64))  # e.g. "tou_residential"
    net_metering: Mapped[bool] = mapped_column(default=False)

    # Solar
    has_solar: Mapped[bool] = mapped_column(default=False)
    solar_capacity_kw: Mapped[float | None] = mapped_column(Float)
    solar_tilt_deg: Mapped[float | None] = mapped_column(Float)
    solar_azimuth_deg: Mapped[float | None] = mapped_column(Float)
    solaredge_site_id: Mapped[str | None] = mapped_column(String(64))
    solaredge_api_key: Mapped[str | None] = mapped_column(String(128))

    # Preferences: 0 = minimize cost only, 1 = minimize carbon only
    optimization_weight: Mapped[float] = mapped_column(Float, default=0.5)

    appliances: Mapped[list["Appliance"]] = relationship(
        "Appliance", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )
    magic_link_tokens: Mapped[list["MagicLinkToken"]] = relationship(
        "MagicLinkToken", back_populates="user", cascade="all, delete-orphan"
    )

    @staticmethod
    def generate_api_key() -> str:
        return secrets.token_urlsafe(32)


class Appliance(Base):
    __tablename__ = "appliances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(128))  # e.g. "Dishwasher"
    slug: Mapped[str] = mapped_column(String(64))  # e.g. "dishwasher"
    cycle_kwh: Mapped[float] = mapped_column(Float)  # energy per full cycle
    cycle_minutes: Mapped[int] = mapped_column(Integer)  # typical cycle length
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship("User", back_populates="appliances")


class UtilityRecord(Base):
    """EIA utility registry — one row per EIA utility ID."""

    __tablename__ = "utility"

    eia_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    state: Mapped[str | None] = mapped_column(String(2))
    ownership_type: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    zipcode_utilities: Mapped[list["ZipcodeUtility"]] = relationship(
        "ZipcodeUtility", back_populates="utility"
    )


class ZipcodeUtility(Base):
    """Maps US ZIP codes to EIA utilities (many-to-many with primary flag)."""

    __tablename__ = "zipcode_utility"

    zipcode: Mapped[str] = mapped_column(String(10), primary_key=True)
    eia_id: Mapped[int] = mapped_column(ForeignKey("utility.eia_id"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    residential_rate_avg: Mapped[float | None] = mapped_column(Float)  # $/kWh
    source_year: Mapped[int | None] = mapped_column(Integer)

    utility: Mapped["UtilityRecord"] = relationship(
        "UtilityRecord", back_populates="zipcode_utilities"
    )


class UserSession(Base):
    """Browser session for dashboard access (created after OAuth or magic link auth)."""

    __tablename__ = "user_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # random token
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(String(256))

    user: Mapped["User"] = relationship("User", back_populates="sessions")


class OAuthAccount(Base):
    """Links a User to an external OAuth identity (Google, GitHub, Apple)."""

    __tablename__ = "oauth_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(32))  # "google" | "github" | "apple"
    provider_user_id: Mapped[str] = mapped_column(String(256))
    provider_email: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")


class MagicLinkToken(Base):
    """Single-use signed token for passwordless email login."""

    __tablename__ = "magic_link_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship("User", back_populates="magic_link_tokens")


class ZipCentroid(Base):
    """US ZIP code geographic centroid (from Census ZCTA gazetteer). One row per ZIP."""

    __tablename__ = "zip_centroid"

    zipcode: Mapped[str] = mapped_column(String(10), primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)


class UrdbRate(Base):
    """NREL Utility Rate Database rate structures (populated in Phase 2)."""

    __tablename__ = "urdb_rate"

    urdb_label: Mapped[str] = mapped_column(String(64), primary_key=True)
    eia_id: Mapped[int | None] = mapped_column(ForeignKey("utility.eia_id"))
    name: Mapped[str | None] = mapped_column(String(256))
    sector: Mapped[str | None] = mapped_column(String(64))
    effective_date: Mapped[str | None] = mapped_column(String(32))
    end_date: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    urdb_last_modified: Mapped[datetime | None] = mapped_column(DateTime)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RateIngestionRun(Base):
    """Audit log for rate data ingestion runs."""

    __tablename__ = "rate_ingestion_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64))  # e.g. "openei_iou_csv", "openei_noniu_csv"
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32))  # "success", "failed", "skipped"
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    source_version: Mapped[str | None] = mapped_column(String(128))  # SHA256 of source file
    error_log: Mapped[str | None] = mapped_column(Text)

"""SQLAlchemy models for FlowShift."""

import secrets
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
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

    # Utility
    utility_id: Mapped[str | None] = mapped_column(String(64))  # e.g. "seattle_city_light"
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

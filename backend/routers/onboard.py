"""POST /onboard — create or update a user profile."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.integrations.geocoding import geocode_with_fallback
from backend.limiter import limiter
from backend.models import Appliance, User
from backend.schemas import APPLIANCE_PRESETS, OnboardRequest, OnboardResponse

router = APIRouter(prefix="/onboard", tags=["onboard"])


@router.post("", response_model=OnboardResponse)
@limiter.limit("5/hour")
async def onboard(request: Request, req: OnboardRequest, db: AsyncSession = Depends(get_db)):
    # Geocode — ZIP centroid used as fallback if Nominatim is unavailable
    geo = await geocode_with_fallback(req.address, postal_code=req.postal_code or "", session=db)
    if geo["lat"] is None:
        raise HTTPException(
            status_code=422,
            detail=geo.get("fallback_reason")
            or f"Could not determine location for: {req.address!r}",
        )

    # Check for existing user by email
    user = None
    if req.email:
        result = await db.execute(select(User).where(User.email == req.email))
        user = result.scalar_one_or_none()

    if user is None:
        user = User(api_key=User.generate_api_key())
        db.add(user)

    user.name = req.name
    user.email = req.email
    user.address = req.address
    user.lat = geo["lat"]
    user.lon = geo["lon"]
    user.utility_id = req.utility_id
    user.utility_name = req.utility_name
    user.utility_eia_id = req.utility_eia_id
    user.utility_rate_avg = req.utility_rate_avg
    user.utility_tier = req.utility_tier or (2 if req.utility_id.startswith("eia_") else 1)
    user.rate_plan = req.rate_plan
    user.net_metering = req.net_metering
    user.has_solar = req.has_solar
    user.solar_capacity_kw = req.solar_capacity_kw
    user.solar_tilt_deg = req.solar_tilt_deg or 20.0
    user.solar_azimuth_deg = req.solar_azimuth_deg or 180.0
    user.solaredge_site_id = req.solaredge_site_id
    user.solaredge_api_key = req.solaredge_api_key
    user.optimization_weight = req.optimization_weight

    # Replace appliances — use bulk delete to avoid lazy-loading the relationship
    if user.id:
        await db.execute(delete(Appliance).where(Appliance.user_id == user.id))

    appliance_list = (
        req.appliances
        if req.appliances
        else [
            APPLIANCE_PRESETS[0],  # Dishwasher as default
        ]
    )
    for a in appliance_list:
        db.add(
            Appliance(
                user=user,
                name=a.name,
                slug=a.slug,
                cycle_kwh=a.cycle_kwh,
                cycle_minutes=a.cycle_minutes,
                notes=getattr(a, "notes", None),
            )
        )

    await db.commit()
    await db.refresh(user)

    location_precise = geo.get("precise", True)
    return OnboardResponse(
        api_key=user.api_key,
        message=(
            f"Welcome{' ' + user.name if user.name else ''}! "
            f"FlowShift is ready. Use your API key to query recommendations."
        ),
        location_precise=location_precise,
        location_warning=geo.get("fallback_reason") if not location_precise else None,
    )

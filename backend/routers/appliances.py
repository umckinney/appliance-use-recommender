"""POST /appliances — add or update an appliance for the authenticated user."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.integrations import energystar
from backend.models import Appliance, User
from backend.schemas import APPLIANCE_PRESETS, ApplianceIn, ApplianceOut, ModelSearchResult

router = APIRouter(prefix="/appliances", tags=["appliances"])


async def _get_user(api_key: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


@router.get("", response_model=list[ApplianceOut])
async def list_appliances(api_key: str, db: AsyncSession = Depends(get_db)):
    user = await _get_user(api_key, db)
    result = await db.execute(select(Appliance).where(Appliance.user_id == user.id))
    return result.scalars().all()


@router.post("", response_model=ApplianceOut, status_code=201)
async def add_appliance(
    req: ApplianceIn,
    api_key: str,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(api_key, db)

    # Upsert: if slug already exists for this user, update it
    result = await db.execute(
        select(Appliance).where(Appliance.user_id == user.id, Appliance.slug == req.slug)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.name = req.name
        existing.cycle_kwh = req.cycle_kwh
        existing.cycle_minutes = req.cycle_minutes
        existing.notes = req.notes
        appliance = existing
    else:
        appliance = Appliance(
            user=user,
            name=req.name,
            slug=req.slug,
            cycle_kwh=req.cycle_kwh,
            cycle_minutes=req.cycle_minutes,
            notes=req.notes,
        )
        db.add(appliance)

    await db.commit()
    await db.refresh(appliance)
    return appliance


@router.delete("/{slug}", status_code=204)
async def delete_appliance(
    slug: str,
    api_key: str,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user(api_key, db)
    result = await db.execute(
        select(Appliance).where(Appliance.user_id == user.id, Appliance.slug == slug)
    )
    appliance = result.scalar_one_or_none()
    if not appliance:
        raise HTTPException(status_code=404, detail=f"Appliance {slug!r} not found")
    await db.delete(appliance)
    await db.commit()


@router.get("/search", response_model=list[ModelSearchResult])
async def search_appliances(category: str, q: str = "", limit: int = 20):
    """Search ENERGY STAR certified products. No auth required — public data.

    category: one of dishwasher | washer | dryer
    Returns: [{"brand", "model", "cycle_kwh", "cycle_minutes"}]
    cycle_minutes is populated for dryers only; None for dishwashers/washers.
    """
    try:
        results = await energystar.search_models(category, q, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return results


@router.get("/presets", response_model=list[ApplianceOut])
async def list_presets():
    """Return the built-in appliance presets (no auth required)."""
    return [
        ApplianceOut(
            id=i,
            name=p.name,
            slug=p.slug,
            cycle_kwh=p.cycle_kwh,
            cycle_minutes=p.cycle_minutes,
        )
        for i, p in enumerate(APPLIANCE_PRESETS, start=1)
    ]

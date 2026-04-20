from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_api_key
from backend.models import User
from backend.schemas import PreferencesUpdate

router = APIRouter(prefix="/account", tags=["account"])


class PreferencesResponse(BaseModel):
    optimization_weight: float


@router.patch("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    req: PreferencesUpdate,
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    user.optimization_weight = req.optimization_weight
    await db.commit()
    await db.refresh(user)
    return PreferencesResponse(optimization_weight=user.optimization_weight)

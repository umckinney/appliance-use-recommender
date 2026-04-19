"""POST /account/lookup — retrieve an existing API key by email.

Low-risk for personal-use deployment: email is the only verification factor.
For multi-tenant/public deployment, upgrade to email-confirmation flow.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import User

router = APIRouter(prefix="/account", tags=["account"])


class LookupRequest(BaseModel):
    email: str


class LookupResponse(BaseModel):
    api_key: str


@router.post("/lookup", response_model=LookupResponse)
async def lookup_account(req: LookupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="No account found for that email.")
    return LookupResponse(api_key=user.api_key)

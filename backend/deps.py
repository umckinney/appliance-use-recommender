"""Shared FastAPI dependencies."""

from fastapi import Header, HTTPException, Query, Request


async def get_api_key(
    request: Request,
    api_key: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> str:
    """Extract API key from ?api_key= query param or Authorization: Bearer header."""
    if api_key:
        return api_key
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    raise HTTPException(
        status_code=401,
        detail="API key required. Pass ?api_key=<key> or Authorization: Bearer <key>",
    )

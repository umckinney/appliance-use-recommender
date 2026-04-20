"""GET /shortcuts/{slug} — download a pre-built Apple Shortcuts workflow file."""

import plistlib
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import get_api_key
from backend.limiter import limiter
from backend.models import Appliance, User

router = APIRouter(prefix="/shortcuts", tags=["shortcuts"])

_ICON_GLYPH = 59511  # lightning bolt
_ICON_COLOR = 4251333119  # blue


def _build_shortcut_plist(name: str, url: str) -> bytes:
    workflow = {
        "WFWorkflowActions": [
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.geturl",
                "WFWorkflowActionParameters": {
                    "WFHTTPMethod": "GET",
                    "WFURL": url,
                },
            },
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.getdictionaryfromjson",
                "WFWorkflowActionParameters": {},
            },
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
                "WFWorkflowActionParameters": {
                    "WFDictionaryKey": "text",
                },
            },
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.speaktext",
                "WFWorkflowActionParameters": {},
            },
        ],
        "WFWorkflowClientVersion": "2600.0.55.3",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": _ICON_GLYPH,
            "WFWorkflowIconStartColor": _ICON_COLOR,
        },
        "WFWorkflowImportQuestions": [],
        "WFWorkflowInputContentItemClasses": [],
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowName": name,
        "WFWorkflowNoInputBehavior": {
            "Name": "RunImmediately",
            "Parameters": {},
        },
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": ["WFSiriType"],
    }
    return plistlib.dumps(workflow, fmt=plistlib.FMT_BINARY)


@router.get("/{slug}")
@limiter.limit("10/hour")
async def download_shortcut(
    request: Request,
    slug: str,
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if slug == "all":
        name = "FlowShift - All Appliances"
        endpoint = f"/recommend/all?api_key={quote(api_key)}"
    else:
        appliance_result = await db.execute(
            select(Appliance).where(Appliance.user_id == user.id, Appliance.slug == slug)
        )
        appliance = appliance_result.scalar_one_or_none()
        if not appliance:
            raise HTTPException(status_code=404, detail=f"Appliance {slug!r} not found.")
        name = f"FlowShift - {appliance.name}"
        endpoint = f"/recommend/{quote(slug)}?api_key={quote(api_key)}"

    # Build the absolute API URL embedded in the shortcut
    base = str(request.base_url).rstrip("/")
    siri_url = f"{base}{endpoint}"

    plist_bytes = _build_shortcut_plist(name, siri_url)
    safe_name = name.replace(" ", "_").replace("/", "-")
    return Response(
        content=plist_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.shortcut"'},
    )

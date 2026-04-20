"""
Authentication routes — OAuth (Google, GitHub, Apple) and magic link.

Flow:
  Browser login:
    GET /auth/{provider}/login  → redirect to provider
    GET /auth/{provider}/callback → exchange code, create/find User, set session cookie
  Magic link:
    POST /auth/magic-link/send  → send email with signed link
    GET  /auth/magic-link/verify?token=… → verify, create session, redirect to dashboard
  Session:
    GET  /auth/me → return current user info (requires session cookie)
    POST /auth/logout → clear session cookie

Session is stored in a signed HttpOnly cookie ("session_id") pointing to the
user_session table. The FlowShift api_key is NOT used for browser auth — it
remains a separate bearer token for the Siri / API integration.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import resend
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.limiter import limiter
from backend.models import MagicLinkToken, OAuthAccount, User, UserSession

router = APIRouter(prefix="/auth", tags=["auth"])

# ── OAuth provider configs ─────────────────────────────────────────────────

_PROVIDERS: dict[str, dict] = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
        "client_id": lambda: settings.google_client_id,
        "client_secret": lambda: settings.google_client_secret,
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
        "client_id": lambda: settings.github_client_id,
        "client_secret": lambda: settings.github_client_secret,
    },
    "apple": {
        "authorize_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        "userinfo_url": None,  # Apple returns user info in the ID token only
        "scope": "name email",
        "client_id": lambda: settings.apple_client_id,
        "client_secret": lambda: _apple_client_secret(),
    },
}

SESSION_COOKIE = "fs_session"
_SESSION_MAX_AGE = timedelta(days=settings.session_max_age_days)
_MAGIC_LINK_TTL = timedelta(minutes=15)


# ── Helpers ────────────────────────────────────────────────────────────────


def _callback_url(provider: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/api/auth/{provider}/callback"


def _apple_client_secret() -> str:
    """Generate a short-lived JWT client secret for Apple Sign In."""
    import jwt  # PyJWT — not a hard dep yet; raise early if missing

    now = datetime.now(UTC)
    payload = {
        "iss": settings.apple_team_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "aud": "https://appleid.apple.com",
        "sub": settings.apple_client_id,
    }
    return jwt.encode(
        payload,
        settings.apple_private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _create_session(user: User, db: AsyncSession, request: Request) -> str:
    session_id = secrets.token_urlsafe(32)
    ua = request.headers.get("user-agent", "")[:256]
    db.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + _SESSION_MAX_AGE,
            user_agent=ua,
        )
    )
    await db.commit()
    return session_id


async def _get_session_user(session_id: str | None, db: AsyncSession) -> User | None:
    if not session_id:
        return None
    now = datetime.now(UTC).replace(tzinfo=None)
    result = await db.execute(
        select(UserSession).where(UserSession.id == session_id, UserSession.expires_at > now)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    user_result = await db.execute(select(User).where(User.id == session.user_id))
    return user_result.scalar_one_or_none()


async def _find_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str | None,
    name: str | None,
) -> User:
    """Return existing user linked to this OAuth account, or create one."""
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == str(provider_user_id),
        )
    )
    oauth_acct = result.scalar_one_or_none()

    if oauth_acct:
        user_result = await db.execute(select(User).where(User.id == oauth_acct.user_id))
        return user_result.scalar_one()

    # Try to match by email
    user = None
    if email:
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()

    if user is None:
        user = User(api_key=User.generate_api_key(), name=name, email=email)
        db.add(user)
        await db.flush()

    db.add(
        OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=str(provider_user_id),
            provider_email=email,
        )
    )
    await db.commit()
    await db.refresh(user)
    return user


# ── OAuth routes ───────────────────────────────────────────────────────────


@router.get("/{provider}/login")
async def oauth_login(provider: str, request: Request) -> RedirectResponse:
    cfg = _PROVIDERS.get(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider!r}")
    if not cfg["client_id"]():
        raise HTTPException(
            status_code=503, detail=f"{provider.capitalize()} OAuth is not configured."
        )

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": cfg["client_id"](),
        "redirect_uri": _callback_url(provider),
        "scope": cfg["scope"],
        "response_type": "code",
        "state": state,
    }
    if provider == "apple":
        params["response_mode"] = "form_post"

    from urllib.parse import urlencode

    url = f"{cfg['authorize_url']}?{urlencode(params)}"
    response = RedirectResponse(url)
    response.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax")
    return response


@router.get("/{provider}/callback")
@router.post("/{provider}/callback")  # Apple uses form_post
async def oauth_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    oauth_state: str | None = Cookie(default=None),
) -> RedirectResponse:
    cfg = _PROVIDERS.get(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider!r}")

    params = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        params.update(dict(form))

    # CSRF: verify state
    returned_state = params.get("state", "")
    if not oauth_state or not secrets.compare_digest(oauth_state, returned_state):
        raise HTTPException(status_code=400, detail="OAuth state mismatch — possible CSRF.")

    code = params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code returned.")

    # Exchange code for token
    async with AsyncOAuth2Client(
        client_id=cfg["client_id"](),
        client_secret=cfg["client_secret"](),
        redirect_uri=_callback_url(provider),
    ) as client:
        token = await client.fetch_token(cfg["token_url"], code=code)

        # Fetch user info
        if cfg["userinfo_url"]:
            headers = {"Authorization": f"Bearer {token['access_token']}"}
            if provider == "github":
                headers["Accept"] = "application/vnd.github+json"
            resp = await client.get(cfg["userinfo_url"], headers=headers)
            user_info = resp.json()

            # GitHub: email may be None if private; fetch from /user/emails
            if provider == "github" and not user_info.get("email"):
                email_resp = await client.get("https://api.github.com/user/emails", headers=headers)
                emails = email_resp.json()
                primary = next((e for e in emails if e.get("primary")), None)
                user_info["email"] = primary["email"] if primary else None
        else:
            # Apple: decode id_token claims
            import base64
            import json  # noqa: E401

            id_token = token.get("id_token", "")
            payload_b64 = id_token.split(".")[1] + "=="
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))
            user_info = {
                "sub": claims.get("sub"),
                "email": claims.get("email"),
                "name": params.get("user", {}).get("name", {}).get("firstName"),
            }

    provider_uid = str(user_info.get("sub") or user_info.get("id") or user_info.get("login") or "")
    email = user_info.get("email")
    name = user_info.get("name") or user_info.get("login")

    if not provider_uid:
        raise HTTPException(status_code=502, detail="Could not get user ID from provider.")

    user = await _find_or_create_user(db, provider, provider_uid, email, name)
    session_id = await _create_session(user, db, request)

    dashboard_url = f"{settings.frontend_url}/dashboard?api_key={user.api_key}"
    response = RedirectResponse(dashboard_url)
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=int(_SESSION_MAX_AGE.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.env == "production",
    )
    response.delete_cookie("oauth_state")
    return response


# ── Magic link routes ──────────────────────────────────────────────────────


class MagicLinkRequest(BaseModel):
    email: str


@router.post("/magic-link/send")
@limiter.limit("5/hour")
async def send_magic_link(
    request: Request,
    body: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Always return the same message to prevent email enumeration
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user and settings.resend_api_key:
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        db.add(
            MagicLinkToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC).replace(tzinfo=None) + _MAGIC_LINK_TTL,
            )
        )
        await db.commit()

        verify_url = f"{settings.frontend_url}/auth/verify?token={token}"
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.magic_link_from_email,
                "to": body.email,
                "subject": "Sign in to FlowShift",
                "html": (
                    f"<p>Click the link below to sign in to FlowShift. "
                    f"It expires in 15 minutes.</p>"
                    f'<p><a href="{verify_url}">Sign in →</a></p>'
                    f"<p>If you didn't request this, you can ignore this email.</p>"
                ),
            }
        )

    return {"message": "If an account with that email exists, a sign-in link has been sent."}


@router.get("/magic-link/verify")
async def verify_magic_link(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    token_hash = _hash_token(token)
    now = datetime.now(UTC).replace(tzinfo=None)

    result = await db.execute(
        select(MagicLinkToken).where(
            MagicLinkToken.token_hash == token_hash,
            MagicLinkToken.expires_at > now,
            MagicLinkToken.used_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired sign-in link.")

    record.used_at = now
    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one()
    await db.commit()

    session_id = await _create_session(user, db, request)
    dashboard_url = f"{settings.frontend_url}/dashboard?api_key={user.api_key}"
    response = RedirectResponse(dashboard_url)
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=int(_SESSION_MAX_AGE.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.env == "production",
    )
    return response


# ── Session / me ───────────────────────────────────────────────────────────


@router.get("/me")
async def me(
    db: AsyncSession = Depends(get_db),
    fs_session: str | None = Cookie(default=None),
) -> dict:
    user = await _get_session_user(fs_session, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "api_key": user.api_key,
    }


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    fs_session: str | None = Cookie(default=None),
) -> dict:
    if fs_session:
        result = await db.execute(select(UserSession).where(UserSession.id == fs_session))
        session = result.scalar_one_or_none()
        if session:
            await db.delete(session)
            await db.commit()
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "Logged out."}

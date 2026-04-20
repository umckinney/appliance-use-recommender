"""slowapi rate limiter — single instance imported by all routers."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _api_key_or_ip(request: Request) -> str:
    """Use api_key (query or Bearer header) as rate-limit key, fall back to IP."""
    key = request.query_params.get("api_key")
    if key:
        return f"apikey:{key}"
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return f"apikey:{auth[7:]}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_remote_address)

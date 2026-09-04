"""Optional API key authentication for the registry surface.

Authentication is off by default so the local demo and CI keep working with no
secret to manage. Setting ``AISHIELD_API_KEY`` turns it on for every registry
route at once — there is no per-route opt-in, because a surface that is
protected in some places and not others is the kind of thing that quietly grows
holes.

Health probes stay open: a readiness check must work without a credential, and
it reveals nothing beyond liveness and which metadata backend is configured.
"""

import logging
import secrets
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from aishield.core.config import Settings

logger = logging.getLogger("aishield.api.security")

API_KEY_HEADER = "X-API-Key"
_BEARER_PREFIX = "Bearer "

# auto_error=False so a missing header reaches our own handler, which can tell
# "no key configured" apart from "key required but absent".
_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def _presented_key(header_key: str | None, authorization: str | None) -> str | None:
    """Read the key from either accepted header, preferring the explicit one."""

    if header_key:
        return header_key
    if authorization and authorization.startswith(_BEARER_PREFIX):
        return authorization.removeprefix(_BEARER_PREFIX).strip() or None
    return None


def require_api_key(
    request: Request,
    header_key: Annotated[str | None, Depends(_api_key_header)] = None,
) -> None:
    """Reject the request unless it carries the configured key.

    A no-op when no key is configured, which is the default.
    """

    settings = cast(Settings, request.app.state.settings)
    expected = settings.api_key
    if expected is None:
        return

    presented = _presented_key(header_key, request.headers.get("Authorization"))
    if presented is None:
        logger.warning(
            "rejected an unauthenticated request",
            extra={"http_path": request.url.path, "reason": "missing key"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"an API key is required; send it as {API_KEY_HEADER} or a Bearer token",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )
    # Constant-time so a wrong key cannot be recovered by timing the comparison.
    if not secrets.compare_digest(presented, expected.get_secret_value()):
        logger.warning(
            "rejected an unauthenticated request",
            extra={"http_path": request.url.path, "reason": "invalid key"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="the API key is not valid",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )


#: Applied to the whole registry router rather than route by route.
ApiKeyDependency = Depends(require_api_key)

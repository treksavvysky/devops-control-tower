"""
Optional API key authentication for external integrations.

When JCT_API_KEY is configured, requests must include:
    Authorization: Bearer <key>

When JCT_API_KEY is not configured, all requests pass through.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

# auto_error=False so it returns None instead of 401 when no header is
# present — needed for the optional-auth mode (key not configured).
_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[str]:
    """Verify API key if JCT_API_KEY is configured.

    Returns the validated key or None if auth is disabled.
    Raises 401 if auth is enabled but key is missing/invalid.
    """
    settings = get_settings()

    if not settings.jct_api_key:
        # Auth disabled — pass through
        return None

    if credentials is None or credentials.credentials != settings.jct_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials

"""Security dependencies for staff and protected endpoints."""
import hmac
from fastapi import Header, HTTPException, status
from app.core.config import settings


def verify_staff_key(x_staff_key: str | None = Header(default=None, alias="X-Staff-Key")) -> str:
    """
    Verify staff API key using constant-time comparison.
    Rejects request with 401 if key is missing, invalid, or unconfigured.
    """
    configured_key = settings.STAFF_API_KEY

    # Fail closed if staff key is unconfigured in settings
    if not configured_key or not configured_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff authentication is not configured.",
        )

    # Reject missing credentials
    if not x_staff_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing staff API key.",
        )
        
    # Constant-time comparison prevents timing attacks; key is never logged
    if not hmac.compare_digest(x_staff_key.strip().encode("utf-8"), configured_key.strip().encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staff API key.",
        )
    return x_staff_key
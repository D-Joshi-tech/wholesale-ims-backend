import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from .models import User

# Secret key for signing app JWT session tokens
JWT_SECRET = os.getenv("JWT_SECRET", "ims_super_secret_jwt_key_2026_wholesale_desk_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

# Optional Google Client ID validation if provided in env
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

security_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(days=JWT_EXPIRATION_DAYS)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


async def verify_google_id_token(credential: str) -> dict:
    """
    Verifies a Google ID token using Google's public tokeninfo endpoint.
    Returns verified payload dictionary containing: email, name, picture, sub.
    """
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Wholesale-IMS-Backend"})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google credential token",
                )
            data = json.loads(response.read().decode("utf-8"))

        # Verify email exists and is verified
        email = data.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token does not contain an email address",
            )
        
        email_verified = data.get("email_verified")
        if email_verified is False or email_verified == "false":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account email is not verified",
            )

        # If GOOGLE_CLIENT_ID is configured, verify aud match
        if GOOGLE_CLIENT_ID and data.get("aud") != GOOGLE_CLIENT_ID:
            # Check if audience matches
            aud = data.get("aud")
            if aud != GOOGLE_CLIENT_ID:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token audience mismatch",
                )

        return {
            "email": email.strip().lower(),
            "name": data.get("name", email.split("@")[0]),
            "picture": data.get("picture"),
            "sub": data.get("sub"),
        }
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {error_msg}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google token verification error: {str(e)}",
        )


async def get_current_user(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and verifies Bearer token,
    checks if user exists in the database and is allowed.
    """
    if not auth_credentials or not auth_credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from PostgreSQL
    res = await db.execute(select(User).where(User.email == email.lower()))
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: User account not found in authorized whitelist.",
        )

    if not user.is_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Your account has been suspended or revoked by an administrator.",
        )

    return user


def require_role(allowed_roles: List[str]):
    """Role-based authorization dependency factory."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission Denied: Requires one of roles: {', '.join(allowed_roles)}",
            )
        return current_user
    return role_checker

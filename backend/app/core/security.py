import secrets
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import jwt
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash
from pydantic import BaseModel

from app.core.config import settings


class TokenPayload(BaseModel):
    sub: str  # user_id
    role: str
    type: str  # "access" or "refresh"
    iat: int
    exp: int
    jti: str  # unique token identifier for revocation


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime in seconds


# Password hashing (Argon2id)
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its Argon2id hash."""
    return _password_hash.verify(password, password_hash)


def _credential_cipher() -> Fernet:
    digest = sha256(settings.CREDENTIAL_ENCRYPTION_SECRET.encode()).digest()
    return Fernet(urlsafe_b64encode(digest))


def encrypt_credential(value: str) -> str:
    return _credential_cipher().encrypt(value.encode()).decode()


def decrypt_credential(value: str) -> str:
    try:
        return _credential_cipher().decrypt(value.encode()).decode()
    except InvalidToken as err:
        raise ValueError("Encrypted credential cannot be decrypted") from err


def hash_recovery_code(value: str) -> str:
    return sha256(value.strip().upper().encode()).hexdigest()


# JWT handling (lazy + cwd-independent)
_PRIVATE_KEY: bytes | None = None
_PUBLIC_KEY: bytes | None = None


def _resolve_key_path(configured: str, fallback_name: str) -> Path:
    p = Path(configured)
    if p.exists():
        return p
    # Fallback 1: backend/keys/<name> relative to this file (backend/app/core/security.py -> backend/keys)
    backend_keys = Path(__file__).resolve().parents[2] / "keys" / fallback_name
    if backend_keys.exists():
        return backend_keys
    # Fallback 2: ./keys/<name> relative to CWD
    cwd_keys = Path.cwd() / "keys" / fallback_name
    if cwd_keys.exists():
        return cwd_keys
    return p


def _get_private_key() -> bytes:
    global _PRIVATE_KEY
    if _PRIVATE_KEY is None:
        path = _resolve_key_path(settings.JWT_PRIVATE_KEY_PATH, "private.pem")
        if not path.exists():
            raise RuntimeError(f"JWT private key not found at {path}")
        _PRIVATE_KEY = path.read_bytes()
    return _PRIVATE_KEY


def _get_public_key() -> bytes:
    global _PUBLIC_KEY
    if _PUBLIC_KEY is None:
        path = _resolve_key_path(settings.JWT_PUBLIC_KEY_PATH, "public.pem")
        if not path.exists():
            raise RuntimeError(f"JWT public key not found at {path}")
        _PUBLIC_KEY = path.read_bytes()
    return _PUBLIC_KEY


def create_token(
    user_id: str,
    role: str,
    token_type: str,
    expires_delta: timedelta,
) -> tuple[str, str]:
    """Create a JWT token and return (token, jti)."""
    now = datetime.now(UTC)
    exp = now + expires_delta
    jti = secrets.token_urlsafe(32)

    payload = {
        "sub": user_id,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
    }

    token = jwt.encode(payload, _get_private_key(), algorithm=settings.JWT_ALGORITHM)
    return token, jti


def create_token_pair(user_id: str, role: str) -> TokenPair:
    """Create access + refresh token pair."""
    access_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    access_token, _ = create_token(user_id, role, "access", access_expires)
    refresh_token, _ = create_token(user_id, role, "refresh", refresh_expires)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_expires.total_seconds()),
    )


def create_web_session_token(user_id: str, role: str) -> str:
    token, _ = create_token(
        user_id,
        role,
        "web_session",
        timedelta(hours=settings.WEB_SESSION_MAX_HOURS),
    )
    return token


def create_pending_2fa_token(user_id: str, role: str) -> str:
    token, _ = create_token(user_id, role, "pending_2fa", timedelta(minutes=5))
    return token


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            _get_public_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "role", "type", "exp", "iat", "jti"]},
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError as err:
        raise ValueError("Token expired") from err
    except jwt.InvalidTokenError as err:
        raise ValueError(f"Invalid token: {err}") from err


def decode_token_unsafe(token: str) -> TokenPayload | None:
    """Decode token without verification (for debugging/logging)."""
    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
        )
        return TokenPayload(**payload)
    except jwt.InvalidTokenError:
        return None


# OTP generation
def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def normalize_phone(phone: str) -> str:
    """Normalize phone to E.164 format (+58XXXXXXXXXX)."""
    # Remove all non-digits
    digits = "".join(c for c in phone if c.isdigit())

    # Handle Venezuelan numbers
    if digits.startswith("58"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]

    # Validate length (Venezuelan mobile: 10 digits after country code)
    if len(digits) != 10:
        raise ValueError("Invalid phone number length")

    return f"+58{digits}"


# Rate limiting keys
def rate_limit_key(identifier: str, endpoint_group: str) -> str:
    return f"ratelimit:{identifier}:{endpoint_group}"


def otp_key(phone: str) -> str:
    return f"otp:{phone}"


def otp_attempts_key(phone: str) -> str:
    return f"otp_attempts:{phone}"


def otp_blocked_key(phone: str) -> str:
    return f"otp_blocked:{phone}"


def otp_ip_blocked_key(ip: str) -> str:
    return f"otp_ip_blocked:{ip}"


def idempotency_key(scope: str, key: str) -> str:
    return f"idemp:{scope}:{key}"


def driver_location_key(order_id: str) -> str:
    return f"driver:location:{order_id}"


def order_location_channel(order_id: str) -> str:
    return f"order:{order_id}:location"


def admin_map_channel() -> str:
    return "admin:map:updates"


def menu_cache_key(restaurant_id: str) -> str:
    return f"cache:menu:{restaurant_id}"


def restaurants_cache_key() -> str:
    return "cache:restaurants:active"

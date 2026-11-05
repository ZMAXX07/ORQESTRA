"""Automated security tests for Supabase JWT token verification."""

import time
from unittest.mock import MagicMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from jwt.exceptions import PyJWKClientError
import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import Settings
from backend.app.services.auth import AuthenticationError, TokenVerificationService

TEST_SECRET = "test-supabase-jwt-secret-key-at-least-32-chars-long"

# Generate an RSA key pair for testing asymmetric JWKS verification
_RSA_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_RSA_PUBLIC_KEY = _RSA_PRIVATE_KEY.public_key()
_RSA_PEM_PRIVATE = _RSA_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


def create_token(
    sub: str = "d3b07384-d113-40e1-bbbb-000000000001",
    email: str = "owner@example.com",
    role: str = "authenticated",
    aud: str = "authenticated",
    iss: str = None,
    expires_in: int = 3600,
    secret: str = TEST_SECRET,
    algorithm: str = "HS256",
    headers: dict = None,
) -> str:
    """Helper to generate signed JWTs for testing."""
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "aud": aud,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }
    if iss is not None:
        payload["iss"] = iss
    return jwt.encode(payload, secret, algorithm=algorithm, headers=headers)


@pytest.fixture
def auth_settings() -> Settings:
    """Settings fixture configured with test JWT secret."""
    return Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="HS256",
        ENVIRONMENT="test",
    )


def test_valid_token_verification(auth_settings: Settings):
    """Test valid JWT signature successfully decodes subject and claims."""
    service = TokenVerificationService(settings=auth_settings)
    token = create_token(sub="11111111-1111-1111-1111-111111111111", email="user@orqestra.local")

    user = service.verify_token(token)
    assert user.user_id == "11111111-1111-1111-1111-111111111111"
    assert user.email == "user@orqestra.local"
    assert user.role == "authenticated"


def test_expired_token_rejected(auth_settings: Settings):
    """Test expired JWT is rejected with TOKEN_EXPIRED code."""
    service = TokenVerificationService(settings=auth_settings)
    token = create_token(expires_in=-60)  # Expired 1 minute ago

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "TOKEN_EXPIRED"


def test_invalid_signature_rejected(auth_settings: Settings):
    """Test token signed with a different key is rejected with INVALID_SIGNATURE."""
    service = TokenVerificationService(settings=auth_settings)
    token = create_token(secret="tampered-wrong-secret-key-32-chars-long")

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "INVALID_SIGNATURE"


def test_algorithm_confusion_attack_rejected(auth_settings: Settings):
    """Test 'none' algorithm or mismatched algorithm is rejected."""
    service = TokenVerificationService(settings=auth_settings)
    # Generate token with mismatched alg header
    payload = {"sub": "123", "exp": int(time.time()) + 3600, "aud": "authenticated"}
    token = jwt.encode(payload, key="", algorithm="none")

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "INVALID_ALGORITHM"


def test_audience_mismatch_rejected(auth_settings: Settings):
    """Test token with unexpected audience claim is rejected."""
    service = TokenVerificationService(settings=auth_settings)
    token = create_token(aud="untrusted-client-aud")

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "INVALID_AUDIENCE"


def test_missing_subject_rejected(auth_settings: Settings):
    """Test token missing 'sub' claim is rejected."""
    service = TokenVerificationService(settings=auth_settings)
    payload = {"email": "no-sub@example.com", "aud": "authenticated", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "MISSING_SUBJECT"


def test_blank_subject_rejected(auth_settings: Settings):
    """Test token with empty or whitespace-only 'sub' claim is rejected."""
    service = TokenVerificationService(settings=auth_settings)
    token = create_token(sub="   ")

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "MISSING_SUBJECT"


def test_malformed_token_rejected(auth_settings: Settings):
    """Test malformed / corrupted token string is rejected."""
    service = TokenVerificationService(settings=auth_settings)

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token("completely.invalid.token")

    assert exc_info.value.code == "INVALID_TOKEN"


def test_empty_token_rejected(auth_settings: Settings):
    """Test empty token string is rejected."""
    service = TokenVerificationService(settings=auth_settings)

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token("")

    assert exc_info.value.code == "UNAUTHENTICATED"


def test_unconfigured_auth_rejected():
    """Test when server has no secret or JWKS configured, raises AUTH_UNCONFIGURED."""
    unconfigured_settings = Settings(
        SUPABASE_JWT_SECRET=None,
        SUPABASE_URL=None,
        SUPABASE_JWKS_URL=None,
        ENVIRONMENT="test",
    )
    service = TokenVerificationService(settings=unconfigured_settings)
    token = create_token(secret=TEST_SECRET)

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "AUTH_UNCONFIGURED"


def test_asymmetric_token_with_jwks_rotation():
    """Test asymmetric RS256 token verification using JWKS client key lookup."""
    settings = Settings(
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        ENVIRONMENT="test",
    )

    # Mock PyJWKClient that resolves 'test-kid'
    mock_signing_key = MagicMock()
    mock_signing_key.key = _RSA_PUBLIC_KEY

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)

    token = create_token(
        sub="22222222-2222-2222-2222-222222222222",
        email="asymmetric@orqestra.local",
        secret=_RSA_PEM_PRIVATE,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )

    user = service.verify_token(token)
    assert user.user_id == "22222222-2222-2222-2222-222222222222"
    assert user.email == "asymmetric@orqestra.local"
    mock_jwks_client.get_signing_key_from_jwt.assert_called_once_with(token)


def test_asymmetric_token_with_unknown_kid_rejected():
    """Test asymmetric RS256 token with unknown key ID in JWKS is rejected."""
    settings = Settings(
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        ENVIRONMENT="test",
    )

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("Key not found in JWKS")

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)

    token = create_token(
        sub="22222222-2222-2222-2222-222222222222",
        secret=_RSA_PEM_PRIVATE,
        algorithm="RS256",
        headers={"kid": "unknown-kid"},
    )

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "INVALID_KEY_ID"


def test_auth_me_endpoint_requires_token(client: TestClient):
    """Test GET /api/v1/auth/me returns 401 when no token is provided."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_401"


def test_valid_token_with_matching_issuer():
    """Test JWT token with matching configured issuer succeeds."""
    settings = Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ISSUER="https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1",
        ENVIRONMENT="test",
    )
    service = TokenVerificationService(settings=settings)
    token = create_token(
        sub="33333333-3333-3333-3333-333333333333",
        iss="https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1",
    )
    user = service.verify_token(token)
    assert user.user_id == "33333333-3333-3333-3333-333333333333"


def test_token_with_mismatched_issuer_rejected():
    """Test JWT token with mismatched issuer is rejected with INVALID_ISSUER."""
    settings = Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ISSUER="https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1",
        ENVIRONMENT="test",
    )
    service = TokenVerificationService(settings=settings)
    token = create_token(
        sub="33333333-3333-3333-3333-333333333333",
        iss="https://forged-attacker-project.supabase.co/auth/v1",
    )
    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)
    assert exc_info.value.code == "INVALID_ISSUER"

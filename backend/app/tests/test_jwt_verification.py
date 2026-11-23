"""Automated security tests for Supabase JWT token verification."""

import time
from unittest.mock import MagicMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
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

# Generate EC SECP256R1 (P-256) key pairs for testing ES256 JWKS verification
_EC_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_EC_PUBLIC_KEY = _EC_PRIVATE_KEY.public_key()
_EC_PEM_PRIVATE = _EC_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

_EC_WRONG_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_EC_WRONG_PEM_PRIVATE = _EC_WRONG_PRIVATE_KEY.private_bytes(
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


def test_asymmetric_es256_token_with_jwks_rotation():
    """Test asymmetric ES256 (ECDSA P-256) token verification using JWKS client lookup."""
    settings = Settings(
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="ES256",
        ENVIRONMENT="test",
    )

    mock_signing_key = MagicMock()
    mock_signing_key.key = _EC_PUBLIC_KEY

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)

    token = create_token(
        sub="44444444-4444-4444-4444-444444444444",
        email="es256-user@orqestra.local",
        secret=_EC_PEM_PRIVATE,
        algorithm="ES256",
        headers={"kid": "supabase-es256-kid-1"},
    )

    user = service.verify_token(token)
    assert user.user_id == "44444444-4444-4444-4444-444444444444"
    assert user.email == "es256-user@orqestra.local"
    assert user.role == "authenticated"
    mock_jwks_client.get_signing_key_from_jwt.assert_called_once_with(token)


def test_asymmetric_es256_token_invalid_signature_rejected():
    """Test ES256 token signed by an unauthorized private key fails verification."""
    settings = Settings(
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        ENVIRONMENT="test",
    )

    # JWKS returns the real public key, but token is signed by a different EC private key
    mock_signing_key = MagicMock()
    mock_signing_key.key = _EC_PUBLIC_KEY

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)

    forged_token = create_token(
        sub="44444444-4444-4444-4444-444444444444",
        secret=_EC_WRONG_PEM_PRIVATE,
        algorithm="ES256",
        headers={"kid": "supabase-es256-kid-1"},
    )

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(forged_token)

    assert exc_info.value.code == "INVALID_SIGNATURE"


def test_asymmetric_es256_token_unknown_kid_rejected():
    """Test ES256 token referencing an unknown kid raises INVALID_KEY_ID."""
    settings = Settings(
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        ENVIRONMENT="test",
    )

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("Key not found in JWKS")

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)

    token = create_token(
        sub="44444444-4444-4444-4444-444444444444",
        secret=_EC_PEM_PRIVATE,
        algorithm="ES256",
        headers={"kid": "unknown-kid-999"},
    )

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(token)

    assert exc_info.value.code == "INVALID_KEY_ID"


def test_auto_algorithm_mode_accepts_both_hs256_and_es256():
    """Verify that SUPABASE_JWT_ALGORITHM='auto' accepts both symmetric and asymmetric tokens."""
    settings = Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="auto",
        ENVIRONMENT="test",
    )

    mock_signing_key = MagicMock()
    mock_signing_key.key = _EC_PUBLIC_KEY
    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)

    # 1. HS256 token verifies via secret
    hs_token = create_token(sub="hs-user-001", algorithm="HS256")
    hs_user = service.verify_token(hs_token)
    assert hs_user.user_id == "hs-user-001"

    # 2. ES256 token verifies via JWKS
    es_token = create_token(
        sub="es-user-002",
        secret=_EC_PEM_PRIVATE,
        algorithm="ES256",
        headers={"kid": "es-kid"},
    )
    es_user = service.verify_token(es_token)
    assert es_user.user_id == "es-user-002"


def test_explicit_algorithm_enforcement_rejects_mismatch():
    """Verify that setting SUPABASE_JWT_ALGORITHM='ES256' rejects HS256 tokens and vice versa."""
    # When server expects ES256, HS256 must be rejected
    es_settings = Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_ALGORITHM="ES256",
        ENVIRONMENT="test",
    )
    es_service = TokenVerificationService(settings=es_settings)
    hs_token = create_token(sub="hs-user-001", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc_info:
        es_service.verify_token(hs_token)
    assert exc_info.value.code == "INVALID_ALGORITHM"
    assert "expected ES256" in str(exc_info.value)

    # When server expects HS256, ES256 must be rejected
    hs_settings = Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_ALGORITHM="HS256",
        ENVIRONMENT="test",
    )
    mock_signing_key = MagicMock()
    mock_signing_key.key = _EC_PUBLIC_KEY
    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    hs_service = TokenVerificationService(settings=hs_settings, jwks_client=mock_jwks_client)
    es_token = create_token(
        sub="es-user-002",
        secret=_EC_PEM_PRIVATE,
        algorithm="ES256",
        headers={"kid": "es-kid"},
    )

    with pytest.raises(AuthenticationError) as exc_info:
        hs_service.verify_token(es_token)
    assert exc_info.value.code == "INVALID_ALGORITHM"
    assert "expected HS256" in str(exc_info.value)


def test_unsupported_algorithm_rejected():
    """Verify that an arbitrary unsupported algorithm is rejected with INVALID_ALGORITHM."""
    import base64
    settings = Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_ALGORITHM="auto",
        ENVIRONMENT="test",
    )
    service = TokenVerificationService(settings=settings)
    header_json = b'{"alg":"UNSUPPORTED-999","typ":"JWT"}'
    b64_header = base64.urlsafe_b64encode(header_json).rstrip(b"=").decode("utf-8")
    raw_token = f"{b64_header}.eyJzdWIiOiIxMjMiLCJhdWQiOiJhdXRoZW50aWNhdGVkIn0.dGFtcGVyZWQtc2lnbmF0dXJl"

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(raw_token)
    assert exc_info.value.code == "INVALID_ALGORITHM"


def test_auto_mode_fails_closed_when_hs256_has_no_secret():
    """Verify that auto mode fails closed with AUTH_UNCONFIGURED if an HS256 token arrives without secret."""
    settings = Settings(
        SUPABASE_JWT_SECRET=None,
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="auto",
        ENVIRONMENT="test",
    )
    service = TokenVerificationService(settings=settings)
    hs_token = create_token(sub="hs-user-001", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(hs_token)
    assert exc_info.value.code == "AUTH_UNCONFIGURED"
    assert "SUPABASE_JWT_SECRET" in str(exc_info.value)


def test_jwks_network_failure_fails_closed():
    """Verify that a JWKS network or retrieval failure fails closed without unsafe fallback."""
    settings = Settings(
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="auto",
        ENVIRONMENT="test",
    )
    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.side_effect = Exception("Connection timeout reaching JWKS endpoint")

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)
    es_token = create_token(
        sub="es-user-network-fail",
        secret=_EC_PEM_PRIVATE,
        algorithm="ES256",
        headers={"kid": "es-kid"},
    )

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(es_token)
    assert exc_info.value.code == "INVALID_TOKEN"
    assert "Failed to resolve public signing key" in str(exc_info.value)


def test_algorithm_confusion_hs256_using_public_key_rejected():
    """Verify algorithm confusion attack (signing HS256 with public key string) is rejected."""
    settings = Settings(
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="auto",
        ENVIRONMENT="test",
    )
    mock_signing_key = MagicMock()
    mock_signing_key.key = _EC_PUBLIC_KEY
    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    service = TokenVerificationService(settings=settings, jwks_client=mock_jwks_client)

    # Attacker crafts HS256 token using the public key PEM as the HMAC secret
    forged_token = create_token(
        sub="attacker-victim-sub",
        secret=str(_EC_PUBLIC_KEY),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_token(forged_token)
    assert exc_info.value.code == "INVALID_SIGNATURE"



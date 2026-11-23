"""Server-side Supabase JWT verification service."""

import logging
from typing import Any, Dict, Optional
import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    PyJWKClientError,
)
from backend.app.core.config import Settings
from backend.app.schemas.auth import AuthenticatedUser

logger = logging.getLogger("orqestra.auth")

SUPPORTED_ASYMMETRIC_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
SUPPORTED_SYMMETRIC_ALGORITHMS = ["HS256", "HS384", "HS512"]


class AuthenticationError(Exception):
    """Exception raised when JWT authentication fails."""

    def __init__(self, message: str, code: str = "UNAUTHENTICATED"):
        super().__init__(message)
        self.message = message
        self.code = code


class TokenVerificationService:
    """Validates and decodes Supabase access tokens.
    
    Supports both symmetric HMAC secrets (HS256) and asymmetric public key
    rotation via Supabase JWKS endpoints (RS256, ES256).
    """

    def __init__(self, settings: Settings, jwks_client: Optional[PyJWKClient] = None):
        self.settings = settings
        self._jwks_client = jwks_client

    def _get_jwks_client(self) -> Optional[PyJWKClient]:
        if self._jwks_client is not None:
            return self._jwks_client
        jwks_url = self.settings.effective_jwks_url
        if jwks_url:
            self._jwks_client = PyJWKClient(jwks_url, cache_keys=True, max_cached_keys=16)
            return self._jwks_client
        return None

    def verify_token(self, token: str) -> AuthenticatedUser:
        """Verify Supabase JWT signature, expiry, audience, and claims.
        
        Never logs bearer tokens or credentials.
        """
        if not token or not token.strip():
            raise AuthenticationError("Authorization token is missing", code="UNAUTHENTICATED")

        # Check unverified header to prevent algorithm confusion attacks (e.g. 'none' algorithm)
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            logger.warning("Failed to decode token header")
            raise AuthenticationError("Invalid token format", code="INVALID_TOKEN") from e

        alg = unverified_header.get("alg")
        if not alg or alg == "none":
            logger.warning("Token algorithm rejected: 'none' or missing")
            raise AuthenticationError("Invalid token algorithm: unsigned tokens not permitted", code="INVALID_ALGORITHM")

        # Check configured algorithm restriction if set (auto/none/empty allows any supported algorithm)
        configured_alg = (self.settings.SUPABASE_JWT_ALGORITHM or "").strip()
        expected_alg = None if configured_alg.lower() in ("auto", "any", "none", "") else configured_alg

        if expected_alg and alg != expected_alg:
            logger.warning(f"JWT algorithm mismatch: token has {alg}, expected {expected_alg}")
            raise AuthenticationError(
                f"Invalid token algorithm: expected {expected_alg}",
                code="INVALID_ALGORITHM",
            )

        # Determine verification key/secret based on algorithm and configuration
        secret_or_key: Any = None
        allowed_algorithms = [alg]

        if alg in SUPPORTED_ASYMMETRIC_ALGORITHMS:
            jwks = self._get_jwks_client()
            if not jwks:
                logger.error("Asymmetric token received but SUPABASE_JWKS_URL/SUPABASE_URL is unconfigured")
                raise AuthenticationError(
                    "JWKS endpoint is not configured for asymmetric token verification",
                    code="AUTH_UNCONFIGURED",
                )
            try:
                signing_key = jwks.get_signing_key_from_jwt(token)
                secret_or_key = signing_key.key
            except PyJWKClientError as e:
                logger.warning(f"Failed to retrieve JWKS signing key: {e}")
                raise AuthenticationError("Invalid token key ID or key unavailable in JWKS", code="INVALID_KEY_ID") from e
            except Exception as e:
                logger.warning(f"JWKS resolution error: {e}")
                raise AuthenticationError("Failed to resolve public signing key", code="INVALID_TOKEN") from e

        elif alg in SUPPORTED_SYMMETRIC_ALGORITHMS:
            secret = self.settings.SUPABASE_JWT_SECRET
            if not secret:
                logger.error("SUPABASE_JWT_SECRET is not configured on the server")
                raise AuthenticationError(
                    "Authentication is unconfigured on server. Please set SUPABASE_JWT_SECRET.",
                    code="AUTH_UNCONFIGURED",
                )
            secret_or_key = secret
        else:
            logger.warning(f"Unsupported JWT algorithm: {alg}")
            raise AuthenticationError(
                f"Unsupported JWT algorithm: {alg}",
                code="INVALID_ALGORITHM",
            )

        decode_options: Dict[str, Any] = {
            "require": ["exp", "sub"],
            "verify_exp": True,
            "verify_aud": bool(self.settings.SUPABASE_JWT_AUDIENCE),
        }
        decode_kwargs: Dict[str, Any] = {
            "algorithms": allowed_algorithms,
            "audience": self.settings.SUPABASE_JWT_AUDIENCE,
            "options": decode_options,
        }
        if self.settings.SUPABASE_JWT_ISSUER:
            decode_kwargs["issuer"] = self.settings.SUPABASE_JWT_ISSUER
            decode_options["verify_iss"] = True

        try:
            payload: Dict[str, Any] = jwt.decode(
                token,
                secret_or_key,
                **decode_kwargs,
            )
        except ExpiredSignatureError as e:
            logger.info("Provided JWT has expired")
            raise AuthenticationError("Authentication token has expired", code="TOKEN_EXPIRED") from e
        except InvalidSignatureError as e:
            logger.warning("JWT signature verification failed")
            raise AuthenticationError("Invalid token signature", code="INVALID_SIGNATURE") from e
        except InvalidAudienceError as e:
            logger.warning("JWT audience mismatch")
            raise AuthenticationError("Invalid token audience", code="INVALID_AUDIENCE") from e
        except InvalidIssuerError as e:
            logger.warning("JWT issuer mismatch")
            raise AuthenticationError("Invalid token issuer", code="INVALID_ISSUER") from e
        except jwt.MissingRequiredClaimError as e:
            logger.warning(f"Missing required claim in JWT: {e}")
            code = "MISSING_SUBJECT" if "sub" in str(e) else "MISSING_CLAIM"
            raise AuthenticationError(f"Token is missing required claim: {e}", code=code) from e
        except (DecodeError, InvalidTokenError) as e:
            logger.warning("Malformed JWT provided")
            raise AuthenticationError("Invalid authentication token", code="INVALID_TOKEN") from e

        sub = payload.get("sub")
        if not sub or not str(sub).strip():
            raise AuthenticationError("Token subject claim is missing", code="MISSING_SUBJECT")

        return AuthenticatedUser(
            user_id=str(sub),
            email=payload.get("email"),
            role=payload.get("role", "authenticated"),
        )

"""Application configuration management using Pydantic Settings."""

import os
from functools import lru_cache
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


IN_MEMORY_ALLOWED_ENVIRONMENTS = {"development", "test", "testing", "local"}


def is_in_memory_allowed(environment: str) -> bool:
    """Return True if the specified environment permits in-memory repositories."""
    return (environment or "").lower().strip() in IN_MEMORY_ALLOWED_ENVIRONMENTS


class Settings(BaseSettings):
    """Centralized environment-based settings for Orqestra backend."""

    APP_NAME: str = "Orqestra API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    @property
    def is_in_memory_allowed(self) -> bool:
        """Return True if the current environment permits in-memory repositories."""
        return is_in_memory_allowed(self.ENVIRONMENT)

    # Explicit CORS allowed origins
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Structured logging level
    LOG_LEVEL: str = "INFO"

    # Supabase & Auth Configuration (Phase 2 & Phase 7.3)
    SUPABASE_URL: Union[str, None] = None
    SUPABASE_PUBLISHABLE_KEY: Union[str, None] = None
    SUPABASE_ANON_KEY: Union[str, None] = None
    SUPABASE_SERVICE_ROLE_KEY: Union[str, None] = None
    SUPABASE_JWT_SECRET: Union[str, None] = None
    SUPABASE_JWKS_URL: Union[str, None] = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWT_ISSUER: Union[str, None] = None
    SUPABASE_JWT_ALGORITHM: str = "HS256"

    # AI Provider Configuration (Phase 5 & Phase 10.4: Google Gemini / OpenAI)
    AI_PROVIDER: Union[str, None] = "openai"
    AI_API_KEY: Union[str, None] = None
    GEMINI_API_KEY: Union[str, None] = None
    AI_MODEL: str = "gpt-4o-mini"
    AI_BASE_URL: Union[str, None] = None
    AI_MAX_MESSAGE_LENGTH: int = 4000
    AI_REQUEST_TIMEOUT_SECONDS: float = 15.0

    # AI Intake Rate Limiting (Phase 6)
    AI_RATE_LIMIT_REQUESTS: int = 15
    AI_RATE_LIMIT_WINDOW_SECONDS: int = 60

    @property
    def effective_ai_api_key(self) -> Union[str, None]:
        """Return configured API key, supporting AI_API_KEY and GEMINI_API_KEY."""
        if self.AI_API_KEY and self.AI_API_KEY.strip():
            return self.AI_API_KEY.strip()
        if self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip():
            return self.GEMINI_API_KEY.strip()
        return None

    @property
    def effective_ai_provider(self) -> str:
        """Return normalized AI provider identifier ('gemini', 'openai', or 'openai-compatible')."""
        if self.AI_PROVIDER:
            p = self.AI_PROVIDER.lower().strip()
            if p in ("gemini", "google", "google-gemini", "google_gemini"):
                return "gemini"
            return p
        if self.GEMINI_API_KEY:
            return "gemini"
        return "openai"

    @property
    def effective_ai_base_url(self) -> str:
        """Return configured AI base URL or provider default."""
        if self.AI_BASE_URL and self.AI_BASE_URL.strip():
            return self.AI_BASE_URL.strip().rstrip("/")
        if self.effective_ai_provider == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/openai"
        return "https://api.openai.com/v1"

    @property
    def effective_ai_model(self) -> str:
        """Return configured AI model or provider default."""
        if self.effective_ai_provider == "gemini":
            if not self.AI_MODEL or self.AI_MODEL in ("gpt-4o-mini", "default"):
                return "gemini-1.5-flash"
            return self.AI_MODEL
        return self.AI_MODEL or "gpt-4o-mini"



    @field_validator("SUPABASE_JWKS_URL", mode="before")
    @classmethod
    def derive_jwks_url(cls, value: Union[str, None], info) -> Union[str, None]:
        """Derive standard Supabase JWKS endpoint if not explicitly specified."""
        if value and str(value).strip():
            return str(value).strip()
        return None

    @property
    def effective_jwks_url(self) -> Union[str, None]:
        """Return explicit JWKS URL or auto-derive from SUPABASE_URL."""
        if self.SUPABASE_JWKS_URL:
            return self.SUPABASE_JWKS_URL
        if self.SUPABASE_URL:
            return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    @property
    def effective_jwt_issuer(self) -> Union[str, None]:
        """Return explicit JWT issuer or auto-derive from SUPABASE_URL."""
        if self.SUPABASE_JWT_ISSUER:
            return self.SUPABASE_JWT_ISSUER
        if self.SUPABASE_URL:
            return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"
        return None

    @property
    def effective_anon_key(self) -> Union[str, None]:
        """Return publishable key or anon key fallback."""
        return self.SUPABASE_PUBLISHABLE_KEY or self.SUPABASE_ANON_KEY

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[List[str], str]) -> List[str]:
        """Convert comma-separated origin string into list of strings."""
        if isinstance(value, str):
            # Split and strip whitespace, filtering out empty entries
            origins = [origin.strip() for origin in value.split(",") if origin.strip()]
            return origins
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return []

    model_config = SettingsConfigDict(
        env_file=[
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                ".env",
            ),
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                ".env",
            ),
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Skip loading .env files during pytest runs to guarantee clean unit test isolation."""
        if os.getenv("PYTEST_CURRENT_TEST"):
            return (init_settings, env_settings)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)


@lru_cache
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()

"""Tests for configuration parsing and validation."""

from backend.app.core.config import Settings


def test_default_settings():
    """Verify default configuration values."""
    settings = Settings()
    assert settings.APP_NAME == "Orqestra API"
    assert settings.APP_VERSION == "0.1.0"
    assert "http://localhost:5173" in settings.CORS_ORIGINS


def test_cors_origins_string_parsing():
    """Verify comma-separated string is parsed into a list."""
    settings = Settings(
        CORS_ORIGINS="http://example.com, https://app.example.com , http://localhost:3000"
    )
    assert settings.CORS_ORIGINS == [
        "http://example.com",
        "https://app.example.com",
        "http://localhost:3000",
    ]


def test_cors_origins_list_parsing():
    """Verify list of origins is preserved and trimmed."""
    settings = Settings(CORS_ORIGINS=["http://site1.local ", " http://site2.local"])
    assert settings.CORS_ORIGINS == ["http://site1.local", "http://site2.local"]


def test_supabase_publishable_key_and_issuer_properties():
    """Verify publishable key fallback and issuer derivation."""
    settings = Settings(
        SUPABASE_URL="https://vwlwbwwrumsmjqeavvxk.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_pub_test_key",
    )
    assert settings.effective_anon_key == "sb_pub_test_key"
    assert settings.effective_jwt_issuer == "https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1"
    assert settings.effective_jwks_url == "https://vwlwbwwrumsmjqeavvxk.supabase.co/auth/v1/.well-known/jwks.json"

"""Regression test suite for staging database lifecycle, timeout bounds, and stale connection recovery.

Verifies:
1. is_server_available returns False promptly for invalid, empty, or closed port URLs.
2. get_conn_url detects stale connection files, removes them, and returns None.
3. get_conn_url(validate=False) returns raw file contents without network probing.
4. cleanup_stale_connection_files removes only connection metadata and preserves unrelated files.
5. Bounded connection attempts complete within finite timeout without indefinite hangs.
6. Real failures are preserved when a database is explicitly configured via environment variable.
7. Clean skip behavior is preserved when no database is running and none is explicitly configured.
"""

import os
import pathlib
import socket
import tempfile
import time
import pytest
import psycopg

from backend.app.tests import manage_staging_db


def _get_closed_port() -> int:
    """Finds an unused, closed local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_is_server_available_empty_or_none():
    """Verify is_server_available immediately returns False for empty or None inputs."""
    assert manage_staging_db.is_server_available(None) is False
    assert manage_staging_db.is_server_available("") is False
    assert manage_staging_db.is_server_available("invalid://uri") is False


def test_is_server_available_closed_port_bounded_time():
    """Verify is_server_available against an inactive port returns False within bounded time."""
    closed_port = _get_closed_port()
    dummy_url = f"postgresql://postgres:secret@127.0.0.1:{closed_port}/orqestra_staging_test"

    t0 = time.perf_counter()
    result = manage_staging_db.is_server_available(dummy_url, timeout=1.0)
    elapsed = time.perf_counter() - t0

    assert result is False
    # Probing an inactive port should fail quickly via socket check (well under 1.5s)
    assert elapsed < 1.5, f"Probe took too long: {elapsed:.2f}s"


def test_get_conn_url_detects_stale_file_and_recovers(tmp_path, monkeypatch):
    """Verify get_conn_url validates active server, cleans up stale files, and returns None."""
    closed_port = _get_closed_port()
    test_conn_file = tmp_path / "test_staging_conn.txt"
    test_pw_file = tmp_path / "test_staging_pw.internal"
    stale_url = f"postgresql://postgres:ephemeral@127.0.0.1:{closed_port}/orqestra_staging_test"

    test_conn_file.write_text(stale_url, encoding="utf-8")
    test_pw_file.write_text("ephemeral", encoding="utf-8")

    monkeypatch.setattr(manage_staging_db, "CONN_FILE", test_conn_file)
    monkeypatch.setattr(manage_staging_db, "PW_FILE_INTERNAL", test_pw_file)

    assert test_conn_file.exists()
    assert test_pw_file.exists()

    # Validated call should detect the server is down, unlink the files, and return None
    url = manage_staging_db.get_conn_url(validate=True, timeout=1.0)
    assert url is None
    assert not test_conn_file.exists()
    assert not test_pw_file.exists()


def test_get_conn_url_without_validation_returns_raw(tmp_path, monkeypatch):
    """Verify get_conn_url(validate=False) returns raw file contents without testing connection."""
    test_conn_file = tmp_path / "raw_conn.txt"
    raw_content = "postgresql://postgres:dummy@127.0.0.1:9999/dummy_db"
    test_conn_file.write_text(raw_content, encoding="utf-8")

    monkeypatch.setattr(manage_staging_db, "CONN_FILE", test_conn_file)

    url = manage_staging_db.get_conn_url(validate=False)
    assert url == raw_content
    # File must not be deleted when validation is disabled
    assert test_conn_file.exists()


def test_cleanup_stale_files_does_not_affect_unrelated_temp_files(tmp_path, monkeypatch):
    """Verify cleanup_stale_connection_files removes ONLY its own metadata files."""
    test_conn_file = tmp_path / "orqestra_staging_conn.txt"
    test_pw_file = tmp_path / "orqestra_staging_pw.internal"
    unrelated_file = tmp_path / "unrelated_user_data.txt"

    test_conn_file.write_text("conn_data", encoding="utf-8")
    test_pw_file.write_text("pw_data", encoding="utf-8")
    unrelated_file.write_text("critical_user_content", encoding="utf-8")

    monkeypatch.setattr(manage_staging_db, "CONN_FILE", test_conn_file)
    monkeypatch.setattr(manage_staging_db, "PW_FILE_INTERNAL", test_pw_file)

    manage_staging_db.cleanup_stale_connection_files()

    assert not test_conn_file.exists()
    assert not test_pw_file.exists()
    assert unrelated_file.exists()
    assert unrelated_file.read_text(encoding="utf-8") == "critical_user_content"


def test_bounded_connection_attempt_timeout():
    """Verify that direct psycopg connection attempts observe finite connect_timeout."""
    closed_port = _get_closed_port()
    unreachable_url = f"postgresql://postgres:secret@127.0.0.1:{closed_port}/orqestra_staging_test"

    t0 = time.perf_counter()
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(unreachable_url, connect_timeout=1)
    elapsed = time.perf_counter() - t0

    # Must complete and fail in bounded time (timeout + small socket overhead, <= 3.5s)
    assert elapsed < 3.5, f"Connection attempt exceeded finite bound: {elapsed:.2f}s"


def test_preserve_real_failures_when_database_expected(monkeypatch):
    """Verify that if STAGING_DATABASE_URL is explicitly set, connection errors are raised rather than skipped."""
    closed_port = _get_closed_port()
    expected_db_url = f"postgresql://postgres:secret@127.0.0.1:{closed_port}/orqestra_staging_test"

    monkeypatch.setenv("STAGING_DATABASE_URL", expected_db_url)

    # Resolution logic mirrors test_phase9_e2e_workflows and test_postgres_staging
    env_url = os.getenv("STAGING_DATABASE_URL") or os.getenv("ORQESTRA_STAGING_DATABASE_URL")
    resolved_url = env_url or manage_staging_db.get_conn_url(validate=True)

    # When explicit env var is set, resolved_url is non-empty
    assert resolved_url == expected_db_url

    # Connecting should raise an OperationalError, ensuring real failures are preserved
    with pytest.raises(psycopg.OperationalError):
        with psycopg.connect(resolved_url, connect_timeout=int(manage_staging_db.DEFAULT_CONNECT_TIMEOUT)):
            pass


def test_database_skip_clean_when_server_unavailable(tmp_path, monkeypatch):
    """Verify that when no database is running and no env var is set, resolved URL is None (triggering skip)."""
    monkeypatch.delenv("STAGING_DATABASE_URL", raising=False)
    monkeypatch.delenv("ORQESTRA_STAGING_DATABASE_URL", raising=False)
    non_existent_conn = tmp_path / "non_existent_staging_conn.txt"
    monkeypatch.setattr(manage_staging_db, "CONN_FILE", non_existent_conn)

    # Ensure no valid running server is returned
    env_url = os.getenv("STAGING_DATABASE_URL") or os.getenv("ORQESTRA_STAGING_DATABASE_URL")
    resolved_url = env_url or manage_staging_db.get_conn_url(validate=True)

    # When no local PostgreSQL server is active, resolved_url must be None
    assert resolved_url is None


def test_remote_staging_database_url_safely_ignored_by_default(tmp_path, monkeypatch):
    """Verify that when STAGING_DATABASE_URL points to a remote host, get_local_staging_url ignores it."""
    remote_url = "postgresql://postgres.vclkeubwpiyhuvprvngx:secret@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
    monkeypatch.setenv("STAGING_DATABASE_URL", remote_url)
    monkeypatch.delenv("ALLOW_REMOTE_STAGING_TESTS", raising=False)
    non_existent_conn = tmp_path / "non_existent_staging_conn.txt"
    monkeypatch.setattr(manage_staging_db, "CONN_FILE", non_existent_conn)

    assert manage_staging_db.get_local_staging_url(validate=True) is None

    # When explicitly opted in via ALLOW_REMOTE_STAGING_TESTS=1
    monkeypatch.setenv("ALLOW_REMOTE_STAGING_TESTS", "1")
    assert manage_staging_db.get_local_staging_url(validate=False) == remote_url


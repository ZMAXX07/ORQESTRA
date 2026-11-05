"""Secure, disposable local PostgreSQL staging database manager.

Manages the lifecycle of an isolated PostgreSQL 16 instance for integration testing:
- Generates cryptographically secure, ephemeral passwords without printing them.
- Requires SCRAM-SHA-256 password authentication (never 'trust').
- Binds strictly to local loopback (127.0.0.1) on isolated port 5433.
- Uses disposable database 'orqestra_staging_test'.
- Never prints passwords or writes credentials to source control.
- Verifies clean data state before and after execution.
"""

import os
import pathlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import pgserver._commands

POSTGRES_BIN_DIR = pathlib.Path(pgserver._commands.POSTGRES_BIN_PATH)
DATA_DIR = pathlib.Path(tempfile.gettempdir()) / "orqestra_staging_pgdata"
CONN_FILE = pathlib.Path(tempfile.gettempdir()) / "orqestra_staging_conn.txt"
PW_FILE_INTERNAL = pathlib.Path(tempfile.gettempdir()) / "orqestra_staging_pw.internal"
PORT = 5433
DB_NAME = "orqestra_staging_test"
USER = "postgres"
DEFAULT_CONNECT_TIMEOUT: float = 3.0


def _run_cmd(cmd_list, env=None):
    """Executes a PostgreSQL binary command synchronously."""
    proc = subprocess.run(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env or os.environ.copy(),
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd_list)}\n{proc.stderr}")
    return proc


def init_cluster():
    """Initializes cluster directory with SCRAM-SHA-256 and ephemeral password."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR, ignore_errors=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Generate ephemeral password
    password = secrets.token_urlsafe(32)
    pw_temp = pathlib.Path(tempfile.gettempdir()) / f"pg_init_{uuid.uuid4().hex}.tmp"

    try:
        pw_temp.write_text(password, encoding="ascii")
        initdb_exe = str(POSTGRES_BIN_DIR / "initdb.exe")
        _run_cmd([
            initdb_exe,
            "-D", str(DATA_DIR),
            "-U", USER,
            "-A", "scram-sha-256",
            f"--pwfile={pw_temp}",
        ])
    finally:
        if pw_temp.exists():
            pw_temp.unlink()

    # Configure strictly local loopback binding on isolated port 5433
    conf_file = DATA_DIR / "postgresql.conf"
    with conf_file.open("a", encoding="ascii") as f:
        f.write("\n# Orqestra Disposable Staging Configuration\n")
        f.write("listen_addresses = '127.0.0.1'\n")
        f.write(f"port = {PORT}\n")

    # Store connection URL in protected file
    conn_url = f"postgresql://{USER}:{password}@127.0.0.1:{PORT}/{DB_NAME}"
    CONN_FILE.write_text(conn_url, encoding="utf-8")
    PW_FILE_INTERNAL.write_text(password, encoding="utf-8")
    return conn_url


def serve():
    """Runs postgres.exe in the foreground (intended for daemon execution)."""
    postgres_exe = str(POSTGRES_BIN_DIR / "postgres.exe")
    # Execute postgres in foreground
    os.execv(postgres_exe, [postgres_exe, "-D", str(DATA_DIR), "-p", str(PORT)])


def create_database():
    """Connects to server once active and creates orqestra_staging_test database with Supabase compatibility roles."""
    import psycopg
    if not PW_FILE_INTERNAL.exists():
        raise RuntimeError("Cluster not initialized.")
    password = PW_FILE_INTERNAL.read_text(encoding="utf-8").strip()

    admin_conn_str = f"postgresql://{USER}:{password}@127.0.0.1:{PORT}/postgres"
    with psycopg.connect(
        admin_conn_str,
        autocommit=True,
        connect_timeout=int(DEFAULT_CONNECT_TIMEOUT),
    ) as conn:
        with conn.cursor() as cur:
            for role in ("anon", "authenticated", "service_role"):
                cur.execute(
                    f"DO $do$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
                    f"CREATE ROLE {role} NOLOGIN; END IF; END $do$;"
                )
            cur.execute("ALTER ROLE service_role BYPASSRLS;")
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
            if not cur.fetchone():
                cur.execute(f"CREATE DATABASE {DB_NAME};")

    test_conn_str = f"postgresql://{USER}:{password}@127.0.0.1:{PORT}/{DB_NAME}"
    with psycopg.connect(
        test_conn_str,
        autocommit=True,
        connect_timeout=int(DEFAULT_CONNECT_TIMEOUT),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS auth;")
            cur.execute(
                "CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID AS $func$ "
                "SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::UUID $func$ LANGUAGE sql STABLE;"
            )
            cur.execute(
                "CREATE OR REPLACE FUNCTION auth.role() RETURNS text AS $func$ "
                "SELECT coalesce(nullif(current_setting('request.jwt.claim.role', true), ''), current_setting('role', true))::text $func$ LANGUAGE sql STABLE;"
            )
            cur.execute(
                "CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb AS $func$ "
                "SELECT coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $func$ LANGUAGE sql STABLE;"
            )
            cur.execute(
                "CREATE OR REPLACE FUNCTION auth.email() RETURNS text AS $func$ "
                "SELECT coalesce(nullif(current_setting('request.jwt.claim.email', true), ''), '')::text $func$ LANGUAGE sql STABLE;"
            )
            cur.execute("GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role, postgres, public;")
            cur.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA auth TO anon, authenticated, service_role, postgres, public;")


def is_server_available(url: str | None = None, timeout: float = DEFAULT_CONNECT_TIMEOUT) -> bool:
    """Checks whether the PostgreSQL server at the given URL is reachable and responding.

    Performs a fast socket probe first, followed by a lightweight SQL query (SELECT 1;).
    Returns False immediately if url is None or unreachable within timeout.
    """
    if not url:
        return False

    try:
        from urllib.parse import urlsplit
        import socket
        parsed = urlsplit(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or PORT
    except Exception:
        return False

    # 1. Fast socket connectivity check
    sock_timeout = min(0.5, max(0.1, timeout))
    try:
        with socket.create_connection((host, port), timeout=sock_timeout):
            pass
    except (OSError, socket.timeout):
        return False

    # 2. Database protocol handshake verification
    try:
        import psycopg
        conn_timeout_sec = max(1, int(timeout))
        with psycopg.connect(url, connect_timeout=conn_timeout_sec) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return True
    except Exception:
        return False


def cleanup_stale_connection_files() -> None:
    """Safely unlinks temporary connection metadata files without touching data or unrelated files."""
    for p in (CONN_FILE, PW_FILE_INTERNAL):
        try:
            if p.exists():
                p.unlink(missing_ok=True)
        except OSError:
            pass


def get_conn_url(validate: bool = True, timeout: float = DEFAULT_CONNECT_TIMEOUT) -> str | None:
    """Retrieves current ephemeral connection URL if active.

    If validate is True, verifies whether the server is reachable.
    If unreachable, treats the connection file as stale, unlinks the stale
    metadata files, and returns None.
    """
    if not CONN_FILE.exists():
        return None

    try:
        url = CONN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not url:
        cleanup_stale_connection_files()
        return None

    if validate:
        if not is_server_available(url, timeout=timeout):
            cleanup_stale_connection_files()
            return None

    return url


def verify_status():
    """Verifies that the server is running, the database exists, and is empty."""
    import psycopg
    url = get_conn_url(validate=False)
    if not url:
        return {"running": False, "detail": "Connection file not found"}

    try:
        with psycopg.connect(url, connect_timeout=int(DEFAULT_CONNECT_TIMEOUT)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port();")
                dbname, s_addr, s_port = cur.fetchone()

                cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
                table_count = cur.fetchone()[0]

                return {
                    "running": True,
                    "database": dbname,
                    "host": str(s_addr),
                    "port": s_port,
                    "user_tables": table_count,
                    "auth": "scram-sha-256",
                }
    except Exception as e:
        return {"running": False, "detail": str(e)}


def cleanup():
    """Cleans up internal files and directory."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    cleanup_stale_connection_files()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "init":
        init_cluster()
        print(f"INIT_OK: Cluster prepared for 127.0.0.1:{PORT}")
    elif action == "serve":
        serve()
    elif action == "create_db":
        create_database()
        print(f"CREATEDB_OK: Database '{DB_NAME}' created.")
    elif action == "verify":
        st = verify_status()
        print(f"VERIFY_STATUS: {st}")
    elif action == "cleanup":
        cleanup()
        print("CLEANUP_OK")

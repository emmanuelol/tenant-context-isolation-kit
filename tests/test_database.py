"""
Comprehensive Unit Tests for PostgreSQL Row-Level Security (RLS) Database Hooks.
================================================================================
Validates SQL injection sanitization, fail-closed tenant boundary enforcement,
parameterization of session variables, and lifecycle scoping.
"""
import pytest
from tenant_context_isolation_kit.context import TenantContext, tenant_scope, get_current_tenant
from tenant_context_isolation_kit.exceptions import (
    TenantIsolationError,
    MissingTenantContextError,
)
from tenant_context_isolation_kit.database import (
    sanitize_tenant_id_for_sql,
    build_set_tenant_sql,
    attach_tenant_rls_listener,
)


class MockCursor:
    def __init__(self):
        self.executed_statements = []

    def execute(self, stmt):
        self.executed_statements.append(stmt)


class MockDBAPIConnection:
    def __init__(self):
        self.cursor_instance = MockCursor()

    def cursor(self):
        return self.cursor_instance


class MockSQLAlchemyConnection:
    def __init__(self):
        self.executed_statements = []

    def execute(self, stmt):
        self.executed_statements.append(stmt)


def test_sanitize_tenant_id_valid_inputs():
    """Verify standard valid tenant identifiers pass without modification."""
    assert sanitize_tenant_id_for_sql("tenant-123") == "tenant-123"
    assert sanitize_tenant_id_for_sql("acme_corp") == "acme_corp"
    assert sanitize_tenant_id_for_sql("tenant.production.v2") == "tenant.production.v2"
    assert sanitize_tenant_id_for_sql("org-42_sub.domain") == "org-42_sub.domain"


@pytest.mark.parametrize(
    "malicious_payload",
    [
        "tenant'; DROP TABLE users; --",
        "' OR '1'='1",
        "admin'--",
        "tenant/*comment*/",
        "tenant; SELECT pg_sleep(5);",
        "tenant' UNION SELECT username, password FROM users --",
        "tenant\\0",
        "",
        "   ",
        None,
        12345,
        "a" * 129,  # Exceeds max length limit (128)
        "tenant$name",
        "tenant@domain",
        "tenant!danger",
    ],
)
def test_sanitize_tenant_id_rejects_sql_injection_and_invalid_inputs(malicious_payload):
    """Verify any invalid character, injection vector, or out-of-spec input raises TenantIsolationError."""
    with pytest.raises(TenantIsolationError):
        sanitize_tenant_id_for_sql(malicious_payload)


def test_build_set_tenant_sql():
    """Verify generated SQL queries for local vs session scoping and custom variable names."""
    sql_local = build_set_tenant_sql("acme-prod", is_local=True)
    assert sql_local == "SET LOCAL app.current_tenant = 'acme-prod';"

    sql_session = build_set_tenant_sql("acme-prod", is_local=False)
    assert sql_session == "SET app.current_tenant = 'acme-prod';"

    sql_custom = build_set_tenant_sql("acme-prod", variable_name="myapp.tenant_id", is_local=True)
    assert sql_custom == "SET LOCAL myapp.tenant_id = 'acme-prod';"


def test_attach_tenant_rls_listener_with_active_context():
    """Verify listener executes SET LOCAL with active tenant context across DBAPI and SQLAlchemy interfaces."""
    ctx = TenantContext(
        tenant_id="tenant-secure-77",
        workspace_id="ws-77",
        sheet_id="sheet-77",
    )

    with tenant_scope(ctx):
        # 1. DBAPI connection (cursor interface)
        dbapi_conn = MockDBAPIConnection()
        attach_tenant_rls_listener(dbapi_conn)
        assert len(dbapi_conn.cursor_instance.executed_statements) == 1
        assert (
            dbapi_conn.cursor_instance.executed_statements[0]
            == "SET LOCAL app.current_tenant = 'tenant-secure-77';"
        )

        # 2. SQLAlchemy connection (execute interface)
        sa_conn = MockSQLAlchemyConnection()
        attach_tenant_rls_listener(sa_conn, variable_name="security.active_tenant", is_local=False)
        assert len(sa_conn.executed_statements) == 1
        assert (
            sa_conn.executed_statements[0]
            == "SET security.active_tenant = 'tenant-secure-77';"
        )


def test_attach_tenant_rls_listener_fail_closed_when_no_context():
    """Verify fail-closed architecture raises MissingTenantContextError when context is missing."""
    assert get_current_tenant() is None
    conn = MockDBAPIConnection()

    with pytest.raises(MissingTenantContextError) as exc_info:
        attach_tenant_rls_listener(conn, enforce=True)

    assert "No active TenantContext found" in str(exc_info.value)
    assert len(conn.cursor_instance.executed_statements) == 0


def test_attach_tenant_rls_listener_graceful_when_enforce_false():
    """Verify enforce=False allows unauthenticated connections without executing SQL statements."""
    assert get_current_tenant() is None
    conn = MockDBAPIConnection()

    attach_tenant_rls_listener(conn, enforce=False)
    assert len(conn.cursor_instance.executed_statements) == 0


def test_attach_tenant_rls_listener_unsupported_connection_type():
    """Verify attempting to attach listener to invalid object raises TenantIsolationError."""
    ctx = TenantContext(tenant_id="tenant-valid", workspace_id="ws-1", sheet_id="sheet-1")

    with tenant_scope(ctx):
        with pytest.raises(TenantIsolationError) as exc_info:
            attach_tenant_rls_listener(object())

        assert "Unsupported connection or session object" in str(exc_info.value)

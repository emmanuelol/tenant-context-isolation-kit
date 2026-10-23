"""
Unit tests for Tenant Context Isolation Kit middleware, exceptions, database hooks, and telemetry.
"""
import logging
import pytest
from tenant_context_isolation_kit.exceptions import (
    TenantIsolationError,
    MissingTenantContextError,
    CrossTenantAccessError,
    TenantQuotaExceededError,
    TenantConfigurationError,
)
from tenant_context_isolation_kit.context import TenantContext, get_current_tenant
from tenant_context_isolation_kit.middleware import TenantContextMiddleware
from tenant_context_isolation_kit.database import (
    sanitize_tenant_id_for_sql,
    build_set_tenant_sql,
    attach_tenant_rls_listener,
)
from tenant_context_isolation_kit.telemetry import (
    TenantLogFilter,
    structlog_tenant_processor,
    inject_tenant_span_attributes,
)


def test_exception_hierarchy():
    """Verify exception hierarchy derives from TenantIsolationError."""
    assert issubclass(MissingTenantContextError, TenantIsolationError)
    assert issubclass(CrossTenantAccessError, TenantIsolationError)
    assert issubclass(TenantQuotaExceededError, TenantIsolationError)
    assert issubclass(TenantConfigurationError, TenantIsolationError)

    err = MissingTenantContextError("No tenant context found")
    assert isinstance(err, TenantIsolationError)
    assert str(err) == "No tenant context found"


@pytest.mark.asyncio
async def test_asgi_middleware_extracts_and_binds_context():
    """Verify ASGI middleware extracts header and scopes contextvars."""
    executed_contexts = []

    async def dummy_app(scope, receive, send):
        assert scope["type"] == "http"
        current = get_current_tenant()
        executed_contexts.append(current)
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"status": "ok"}',
        })

    middleware = TenantContextMiddleware(
        app=dummy_app,
        tenant_header="x-tenant-id",
        workspace_header="x-workspace-id",
        enforce_tenant=True,
    )

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/resource",
        "headers": [
            (b"x-tenant-id", b"tenant-alpha"),
            (b"x-workspace-id", b"ws-42"),
        ],
    }

    sent_messages = []
    async def fake_receive():
        return {"type": "http.request"}

    async def fake_send(msg):
        sent_messages.append(msg)

    # Initial state outside request is None
    assert get_current_tenant() is None

    await middleware(scope, fake_receive, fake_send)

    # Context was properly bound during request
    assert len(executed_contexts) == 1
    assert executed_contexts[0] is not None
    assert executed_contexts[0].tenant_id == "tenant-alpha"
    assert executed_contexts[0].workspace_id == "ws-42"

    # Context is cleaned up after request completes
    assert get_current_tenant() is None
    assert sent_messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_asgi_middleware_enforce_tenant_rejection():
    """Verify middleware rejects request when tenant is missing in enforce mode."""
    async def dummy_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})

    middleware = TenantContextMiddleware(
        app=dummy_app,
        tenant_header="x-tenant-id",
        enforce_tenant=True,
    )

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/data",
        "headers": [],
    }

    sent_messages = []
    async def fake_send(msg):
        sent_messages.append(msg)

    await middleware(scope, None, fake_send)

    assert len(sent_messages) >= 1
    assert sent_messages[0]["status"] == 401
    assert get_current_tenant() is None


@pytest.mark.asyncio
async def test_asgi_middleware_passthrough_non_http():
    """Verify middleware ignores lifespan or websocket without crashing."""
    executed = False
    async def lifespan_app(scope, receive, send):
        nonlocal executed
        executed = True

    middleware = TenantContextMiddleware(app=lifespan_app)
    await middleware({"type": "lifespan"}, None, None)
    assert executed is True


def test_database_sanitize_and_set_tenant_sql():
    """Verify SQL injection prevention and SQL statement construction."""
    safe = sanitize_tenant_id_for_sql("tenant_123-abc")
    assert safe == "tenant_123-abc"

    with pytest.raises(TenantIsolationError):
        sanitize_tenant_id_for_sql("tenant'; DROP TABLE users; --")

    with pytest.raises(TenantIsolationError):
        sanitize_tenant_id_for_sql("   ")

    sql_local = build_set_tenant_sql("tenant-42", is_local=True)
    assert sql_local == "SET LOCAL app.current_tenant = 'tenant-42';"

    sql_session = build_set_tenant_sql("tenant-42", is_local=False)
    assert sql_session == "SET app.current_tenant = 'tenant-42';"


def test_database_attach_tenant_rls_listener():
    """Verify event listener attaches to mock sessionmaker or connection."""
    executed_statements = []

    class FakeCursor:
        def execute(self, stmt):
            executed_statements.append(stmt)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def execute(self, stmt):
            executed_statements.append(stmt)

    ctx = TenantContext(
        tenant_id="tenant-prod-99",
        workspace_id="ws-99",
        sheet_id="sheet-99",
    )

    from tenant_context_isolation_kit.context import tenant_scope
    with tenant_scope(ctx):
        conn = FakeConnection()
        attach_tenant_rls_listener(conn)

    assert len(executed_statements) == 1
    assert "tenant-prod-99" in executed_statements[0]


def test_telemetry_tenant_log_filter():
    """Verify standard logging.Filter populates record.tenant_id."""
    log_filter = TenantLogFilter()
    record = logging.LogRecord("test", logging.INFO, "path", 1, "msg", (), None)

    # When no tenant in context
    assert log_filter.filter(record) is True
    assert record.tenant_id == "none"

    # When tenant in context
    ctx = TenantContext(tenant_id="t-audit", workspace_id="ws-audit", sheet_id="s-audit")
    from tenant_context_isolation_kit.context import tenant_scope
    with tenant_scope(ctx):
        log_filter.filter(record)
        assert record.tenant_id == "t-audit"


def test_telemetry_structlog_processor():
    """Verify structlog processor injects tenant metadata into event dictionary."""
    event = {"event": "user_action"}
    processed = structlog_tenant_processor(None, "info", event)
    assert processed["tenant_id"] is None

    ctx = TenantContext(tenant_id="t-proc", workspace_id="ws-proc", sheet_id="s-proc")
    from tenant_context_isolation_kit.context import tenant_scope
    with tenant_scope(ctx):
        processed = structlog_tenant_processor(None, "info", event)
        assert processed["tenant_id"] == "t-proc"
        assert processed["workspace_id"] == "ws-proc"


def test_telemetry_inject_tenant_span_attributes():
    """Verify OpenTelemetry span attributes helper."""
    class FakeSpan:
        def __init__(self):
            self.attributes = {}

        def set_attribute(self, key, value):
            self.attributes[key] = value

    span = FakeSpan()
    inject_tenant_span_attributes(span)
    assert span.attributes["tenant.id"] == "none"

    ctx = TenantContext(tenant_id="t-span", workspace_id="ws-span", sheet_id="s-span")
    from tenant_context_isolation_kit.context import tenant_scope
    with tenant_scope(ctx):
        inject_tenant_span_attributes(span)
        assert span.attributes["tenant.id"] == "t-span"
        assert span.attributes["tenant.workspace_id"] == "ws-span"

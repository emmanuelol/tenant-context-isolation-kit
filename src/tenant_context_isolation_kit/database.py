"""
Database and Row-Level Security (RLS) Integration Hooks.
========================================================
Provides connection and session hooks to enforce PostgreSQL Row-Level Security (RLS)
via `SET LOCAL app.current_tenant = :tenant_id`. Ensures queries execute strictly
within the scope of the tenant bound to the current execution context.
"""
from __future__ import annotations

import re
from typing import Any, Optional
from tenant_context_isolation_kit.context import get_current_tenant
from tenant_context_isolation_kit.exceptions import (
    TenantIsolationError,
    MissingTenantContextError,
)

_VALID_TENANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")


def sanitize_tenant_id_for_sql(tenant_id: Optional[str]) -> str:
    """
    Validates tenant identifier against strict whitelist to prevent SQL injection
    in session variable declarations.
    """
    if not tenant_id or not isinstance(tenant_id, str):
        raise TenantIsolationError("Tenant ID cannot be null or empty for SQL session variable.")
    cleaned = tenant_id.strip()
    if not _VALID_TENANT_ID_PATTERN.match(cleaned):
        raise TenantIsolationError(
            f"Invalid tenant ID format '{tenant_id}'. Must be alphanumeric with hyphens, periods, or underscores."
        )
    return cleaned


def build_set_tenant_sql(
    tenant_id: str,
    variable_name: str = "app.current_tenant",
    is_local: bool = True,
) -> str:
    """
    Generates parameterized SET [LOCAL] statement for PostgreSQL RLS.
    """
    safe_id = sanitize_tenant_id_for_sql(tenant_id)
    scope_keyword = "LOCAL " if is_local else ""
    return f"SET {scope_keyword}{variable_name} = '{safe_id}';"


def attach_tenant_rls_listener(
    conn_or_session: Any,
    variable_name: str = "app.current_tenant",
    is_local: bool = True,
    enforce: bool = True,
) -> None:
    """
    Executes SET LOCAL session variable on the target DBAPI connection or cursor.
    Uses active TenantContext from contextvars.
    """
    current = get_current_tenant()
    if not current or not current.tenant_id:
        if enforce:
            raise MissingTenantContextError(
                "Cannot attach tenant RLS session variable: No active TenantContext found."
            )
        return

    sql_statement = build_set_tenant_sql(
        current.tenant_id,
        variable_name=variable_name,
        is_local=is_local,
    )

    if hasattr(conn_or_session, "cursor"):
        cursor = conn_or_session.cursor()
        cursor.execute(sql_statement)
    elif hasattr(conn_or_session, "execute"):
        conn_or_session.execute(sql_statement)
    else:
        raise TenantIsolationError(
            f"Unsupported connection or session object: {type(conn_or_session)}"
        )

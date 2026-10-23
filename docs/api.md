# API Reference

::: tenant_context_isolation_kit
    options:
      members:
        - TenantContext
        - tenant_scope
        - get_current_tenant
        - TenantConfigSchema
        - SafeClient
        - SafeSpreadsheet
        - SafeWorksheet
        - IsolatedClientRegistry
        - TenantIsolationError
        - MissingTenantContextError
        - CrossTenantAccessError
        - TenantQuotaExceededError
        - TenantConfigurationError
        - TenantContextMiddleware
        - sanitize_tenant_id_for_sql
        - build_set_tenant_sql
        - attach_tenant_rls_listener
        - TenantLogFilter
        - structlog_tenant_processor
        - inject_tenant_span_attributes

---

## Core Classes

### `TenantContext`
Immutable execution context containing resolved tenant parameters and explicit API clients.

### `tenant_scope(ctx: TenantContext)`
Context manager to scope execution under an explicit `TenantContext`. Safely restores previous context upon exit via ContextVar tokens.

### `get_current_tenant() -> Optional[TenantContext]`
Returns the active `TenantContext` bound to the current execution thread or task.

---

## Exceptions

All exceptions derive from `TenantIsolationError`:
* `TenantIsolationError`: Base exception.
* `MissingTenantContextError`: Raised when tenant context is required but absent.
* `CrossTenantAccessError`: Raised upon unauthorized cross-tenant data access.
* `TenantQuotaExceededError`: Raised on quota or rate limit violations.
* `TenantConfigurationError`: Raised on configuration or schema validation failure.

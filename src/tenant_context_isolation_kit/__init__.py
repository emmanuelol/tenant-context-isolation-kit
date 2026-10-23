"""
tenant-context-isolation-kit: SRE-hardened multi-tenant execution context, strict
dependency injection, and resilient client pooling.
"""

__version__ = "0.2.2"

# Core context and client primitives (always available)
from tenant_context_isolation_kit.context import (
    TenantContext,
    tenant_scope,
    get_current_tenant,
)
from tenant_context_isolation_kit.schemas import (
    TenantConfigSchema,
)
from tenant_context_isolation_kit.clients import (
    SafeClient,
    SafeSpreadsheet,
    SafeWorksheet,
    IsolatedClientRegistry,
)
from tenant_context_isolation_kit.exceptions import (
    TenantIsolationError,
    MissingTenantContextError,
    CrossTenantAccessError,
    TenantQuotaExceededError,
    TenantConfigurationError,
)

__all__ = [
    "__version__",
    "TenantContext",
    "tenant_scope",
    "get_current_tenant",
    "TenantConfigSchema",
    "SafeClient",
    "SafeSpreadsheet",
    "SafeWorksheet",
    "IsolatedClientRegistry",
    "TenantIsolationError",
    "MissingTenantContextError",
    "CrossTenantAccessError",
    "TenantQuotaExceededError",
    "TenantConfigurationError",
]

# Optional ASGI middleware export
try:
    from tenant_context_isolation_kit.middleware import TenantContextMiddleware
    __all__.append("TenantContextMiddleware")
except ImportError:
    pass

# Optional database RLS hooks export
try:
    from tenant_context_isolation_kit.database import (
        sanitize_tenant_id_for_sql,
        build_set_tenant_sql,
        attach_tenant_rls_listener,
    )
    __all__.extend([
        "sanitize_tenant_id_for_sql",
        "build_set_tenant_sql",
        "attach_tenant_rls_listener",
    ])
except ImportError:
    pass

# Optional telemetry and observability export
try:
    from tenant_context_isolation_kit.telemetry import (
        TenantLogFilter,
        structlog_tenant_processor,
        inject_tenant_span_attributes,
    )
    __all__.extend([
        "TenantLogFilter",
        "structlog_tenant_processor",
        "inject_tenant_span_attributes",
    ])
except ImportError:
    pass

# Optional routing module export
try:
    from tenant_context_isolation_kit.routing import (
        TenantRoutingResolver,
        resolve_cascading_destinations,
        verify_tenant_token,
        get_or_create_folder,
    )
    __all__.extend([
        "TenantRoutingResolver",
        "resolve_cascading_destinations",
        "verify_tenant_token",
        "get_or_create_folder",
    ])
except ImportError:
    pass

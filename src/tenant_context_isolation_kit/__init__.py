"""
tenant-context-isolation-kit: SRE-hardened multi-tenant execution context, strict
dependency injection, and resilient client pooling.
"""

__version__ = "0.2.0"

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
from tenant_context_isolation_kit.middleware import (
    TenantContextMiddleware,
)
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
    "TenantContextMiddleware",
    "sanitize_tenant_id_for_sql",
    "build_set_tenant_sql",
    "attach_tenant_rls_listener",
    "TenantLogFilter",
    "structlog_tenant_processor",
    "inject_tenant_span_attributes",
]

# Optional forward export for routing module
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

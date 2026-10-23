"""
tenant-context-isolation-kit: SRE-hardened multi-tenant execution context, strict
dependency injection, and resilient client pooling.
"""

__version__ = "0.1.0"

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
]

# Optional forward export for routing module (populated in T-02)
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

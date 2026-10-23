"""
Multi-Tenant Execution Context and Scope Isolation.
===================================================
Provides immutable TenantContext dataclass and ContextVar-based execution scoping
to guarantee zero implicit global state leakage across background workers and tasks.
"""
from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Optional, Any, Mapping, Generator


@dataclass(frozen=True)
class TenantContext:
    """
    Immutable execution context containing resolved tenant parameters and explicit API clients.
    """
    tenant_id: str
    workspace_id: str
    sheet_id: str
    inbox_folder_id: Optional[str] = None
    vault_folder_id: Optional[str] = None
    organization_name: Optional[str] = None
    manager_phone: Optional[str] = None
    timezone: str = "America/Mexico_City"
    gc_client: Optional[Any] = None
    drive_service: Optional[Any] = None
    extra_metadata: Mapping[str, Any] = field(default_factory=dict)

    def with_clients(self, gc_client: Any, drive_service: Any) -> TenantContext:
        """Returns a new TenantContext instance with explicit client bindings."""
        return replace(
            self,
            gc_client=gc_client,
            drive_service=drive_service,
        )

    def with_metadata(self, **kwargs: Any) -> TenantContext:
        """Returns a new TenantContext instance with updated extra_metadata dictionary."""
        merged = dict(self.extra_metadata)
        merged.update(kwargs)
        return replace(self, extra_metadata=merged)

    def get(self, key: str, default: Any = None) -> Any:
        """Safely fetch from dataclass attributes or extra_metadata."""
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        return self.extra_metadata.get(key, default)

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and key not in self.extra_metadata and not hasattr(self, key):
            raise KeyError(key)
        return val

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or key in self.extra_metadata


_CURRENT_TENANT: ContextVar[Optional[TenantContext]] = ContextVar("current_tenant", default=None)


def get_current_tenant() -> Optional[TenantContext]:
    """Returns the active TenantContext bound to the current execution thread/task."""
    return _CURRENT_TENANT.get()


@contextmanager
def tenant_scope(ctx: TenantContext) -> Generator[TenantContext, None, None]:
    """
    Context manager to scope execution under an explicit TenantContext.
    Restores previous context upon exit.
    """
    token = _CURRENT_TENANT.set(ctx)
    try:
        yield ctx
    finally:
        _CURRENT_TENANT.reset(token)

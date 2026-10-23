"""
Tenant Context Isolation Kit Exception Hierarchy.
================================================
Provides a clear, strongly-typed exception hierarchy for failure boundaries
and cross-tenant isolation enforcement.
"""
from __future__ import annotations


class TenantIsolationError(Exception):
    """Base exception for all errors raised by tenant-context-isolation-kit."""
    pass


class MissingTenantContextError(TenantIsolationError):
    """Raised when an operation requires an active tenant context but none is set."""
    pass


class CrossTenantAccessError(TenantIsolationError):
    """Raised when an operation attempts unauthorized access across tenant boundaries."""
    pass


class TenantQuotaExceededError(TenantIsolationError):
    """Raised when a tenant breaches rate limits, throughput limits, or resource quotas."""
    pass


class TenantConfigurationError(TenantIsolationError):
    """Raised when a tenant record, schema, or configuration fails validation."""
    pass

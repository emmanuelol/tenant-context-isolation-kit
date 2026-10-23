"""
Observability and Telemetry Integration.
========================================
Automatic injection of tenant execution context into Python standard logging,
structlog processors, and OpenTelemetry distributed trace spans.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from tenant_context_isolation_kit.context import get_current_tenant


class TenantLogFilter(logging.Filter):
    """
    Standard library logging.Filter that attaches active tenant_id and workspace_id
    to LogRecord instances for structured logging and log correlation.
    """

    def __init__(self, default_tenant: str = "none", default_workspace: str = "none"):
        super().__init__()
        self.default_tenant = default_tenant
        self.default_workspace = default_workspace

    def filter(self, record: logging.LogRecord) -> bool:
        current = get_current_tenant()
        if current and current.tenant_id:
            record.tenant_id = current.tenant_id
            record.workspace_id = current.workspace_id or self.default_workspace
        else:
            record.tenant_id = self.default_tenant
            record.workspace_id = self.default_workspace
        return True


def structlog_tenant_processor(
    logger: Any,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    structlog-compatible processor that automatically decorates log events
    with active tenant context parameters.
    """
    current = get_current_tenant()
    if current:
        event_dict["tenant_id"] = current.tenant_id
        event_dict["workspace_id"] = current.workspace_id
    else:
        event_dict["tenant_id"] = None
        event_dict["workspace_id"] = None
    return event_dict


def inject_tenant_span_attributes(
    span: Any,
    default_tenant: str = "none",
) -> None:
    """
    Injects active tenant metadata as semantic attributes onto an OpenTelemetry Span.
    """
    current = get_current_tenant()
    if current and current.tenant_id:
        span.set_attribute("tenant.id", current.tenant_id)
        if current.workspace_id:
            span.set_attribute("tenant.workspace_id", current.workspace_id)
    else:
        span.set_attribute("tenant.id", default_tenant)

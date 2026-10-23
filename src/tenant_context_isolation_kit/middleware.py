"""
ASGI Middleware for Multi-Tenant Context Binding.
=================================================
Drop-in ASGI middleware for FastAPI, Starlette, and modern Python async web frameworks.
Extracts tenant identifiers from incoming headers or tokens, constructs TenantContext,
and scopes execution safely via ContextVar-based tenant_scope.
"""
from __future__ import annotations

import json
from typing import Callable, Optional, Any, Dict
from tenant_context_isolation_kit.context import TenantContext, tenant_scope
from tenant_context_isolation_kit.exceptions import MissingTenantContextError


class TenantContextMiddleware:
    """
    Standard ASGI middleware for tenant context injection and isolation.
    """

    def __init__(
        self,
        app: Any,
        tenant_header: str = "x-tenant-id",
        workspace_header: str = "x-workspace-id",
        enforce_tenant: bool = False,
        context_resolver: Optional[Callable[[Dict[str, str]], TenantContext]] = None,
    ):
        self.app = app
        self.tenant_header = tenant_header.lower().encode("latin-1")
        self.workspace_header = workspace_header.lower().encode("latin-1")
        self.enforce_tenant = enforce_tenant
        self.context_resolver = context_resolver

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        tenant_val = headers.get(self.tenant_header)
        workspace_val = headers.get(self.workspace_header)

        tenant_id = tenant_val.decode("latin-1").strip() if tenant_val else None
        workspace_id = workspace_val.decode("latin-1").strip() if workspace_val else None

        if not tenant_id:
            if self.enforce_tenant:
                await self._send_unauthorized(send, "Missing required tenant header")
                return
            await self.app(scope, receive, send)
            return

        resolved_workspace = workspace_id or tenant_id
        if self.context_resolver:
            ctx = self.context_resolver({
                "tenant_id": tenant_id,
                "workspace_id": resolved_workspace,
            })
        else:
            ctx = TenantContext(
                tenant_id=tenant_id,
                workspace_id=resolved_workspace,
                sheet_id="",
            )

        with tenant_scope(ctx):
            await self.app(scope, receive, send)

    async def _send_unauthorized(self, send: Callable, detail: str) -> None:
        body = json.dumps({"error": "Unauthorized", "detail": detail}).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode("latin-1")],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

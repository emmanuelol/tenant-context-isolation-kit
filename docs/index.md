# Tenant Context Isolation Kit

Welcome to the **tenant-context-isolation-kit** documentation.

`tenant-context-isolation-kit` is an SRE-hardened multi-tenant execution context, strict dependency injection, and zero-bleed isolation library for modern Python runtimes.

---

## Key Guarantees

* **Zero Asynchronous Context Bleed:** Uses `ContextVar` scoping wrapped in `tenant_scope` and frozen `TenantContext` to eliminate task-level credential leaks during `asyncio.gather` and coroutine switches.
* **Database Kernel Row-Level Security:** Integrates directly with PostgreSQL RLS via transaction-scoped session hooks (`SET LOCAL app.current_tenant = :tenant_id`), preventing data leaks even from unparameterized queries.
* **Resilient Client Pooling:** `SafeClient`, `SafeSpreadsheet`, and `SafeWorksheet` with bounded exponential retry policies for high-concurrency cloud API access.
* **Quota Protection & Anti-Throttling:** Redis batch cache warming for tenant registries, reducing external I/O sweeps by over 95%.
* **Constant-Time Verification:** Anti-timing attack token authentication via `secrets.compare_digest`.

---

## Quickstart Example

```python
from tenant_context_isolation_kit import TenantContext, tenant_scope, get_current_tenant

# Define immutable tenant context
ctx = TenantContext(
    tenant_id="tenant-alpha",
    workspace_id="ws-alpha",
    sheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
)

# Bind execution scope
with tenant_scope(ctx):
    active = get_current_tenant()
    assert active.tenant_id == "tenant-alpha"
```

For full API specifications, see the [API Reference](api.md).

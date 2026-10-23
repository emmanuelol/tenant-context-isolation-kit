# ADR 001: ContextVars vs. ThreadLocal for Multi-Tenant Scoping

* **Status:** Accepted
* **Date:** 2026-10-22
* **Deciders:** Core Architecture Team

---

## Context and Problem Statement

Multi-tenant Python services must guarantee that execution context (tenant ID, workspace ID, API clients, credentials) remains strictly isolated per request or background task.

In legacy Python WSGI architectures (e.g., standard Django/Flask on Gunicorn sync workers), `threading.local()` was the standard mechanism for thread-bound state. However, modern Python architectures heavily utilize asynchronous event loops (`asyncio`, Starlette, FastAPI, Celery async workers). In an async runtime:
1. Multiple concurrent requests execute cooperatively within the **same OS thread**.
2. When a coroutine awaits I/O (`await asyncio.sleep()`, database query, HTTP call), the event loop pauses the task and switches to another task.
3. If `threading.local()` is used, task B will read or overwrite task A's tenant context, resulting in catastrophic cross-tenant data bleed.

---

## Decision

We use **PEP 567 `contextvars.ContextVar`** as the foundational context-binding primitive, managed exclusively via the `tenant_scope` context manager and frozen `TenantContext` dataclass.

```python
_CURRENT_TENANT: ContextVar[Optional[TenantContext]] = ContextVar("current_tenant", default=None)
```

For thread pools and subprocesses where OS thread boundaries exist without shared event loops, `IsolatedClientRegistry` combines unshared client factories with thread-local client caching and `os.register_at_fork` protection.

---

## Consequences

### Positive:
* **Zero Async Context Bleed:** Coroutines inherit isolated copies of context; context switches do not leak state between tasks.
* **Deterministic Lifecycle:** `tenant_scope` uses tokens to guarantee symmetric reset in a `finally` block, ensuring no leftover context outside the request block.
* **Compatibility:** Natively supported by Python 3.7+ and standard async frameworks.

### Negative / Trade-offs:
* Passing execution to raw unmanaged threads requires explicit propagation via `contextvars.copy_context().run()`.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-10-22

### Added
* **PEP 561 Type Marker (`py.typed`):** Added packaging marker enabling downstream `mypy` and `pyright` type inference.
* **Custom Exception Hierarchy (`exceptions.py`):** Introduced `TenantIsolationError`, `MissingTenantContextError`, `CrossTenantAccessError`, `TenantQuotaExceededError`, and `TenantConfigurationError`.
* **ASGI Middleware (`middleware.py`):** Drop-in `TenantContextMiddleware` for FastAPI and Starlette with automatic header extraction and ContextVar scoping.
* **Database & RLS Hooks (`database.py`):** PostgreSQL Row-Level Security connection listeners with SQL injection sanitization and `SET LOCAL app.current_tenant` scoping.
* **Observability & Telemetry (`telemetry.py`):** `TenantLogFilter` for Python `logging`, structlog event processors, and OpenTelemetry semantic span attribute injectors.
* **Concurrency Stress Suite (`tests/test_concurrency_isolation.py`):** Fuzz test executing 1,000 tasks across 50 tenants with zero context bleed.
* **Reference Architecture Stack (`examples/fastapi-postgres-rls/`):** Runnable FastAPI + PostgreSQL RLS demo proving database-level tenant isolation.
* **Security & Governance:** Added `SECURITY.md` threat model, multi-version CI matrix testing, PyPI OIDC trusted publishing, Bandit security scanner, and pre-commit hooks.
* **Architecture Decision Records (ADRs):** Documented core decisions (`001-contextvars-vs-threadlocal.md`, `002-fail-closed-routing-strategy.md`, `003-postgresql-rls-connection-scoping.md`).
* **MkDocs Material Documentation Config:** Added `mkdocs.yml` site structure.

---

## [0.1.0] - 2026-10-22

### Added
* Initial release of `tenant-context-isolation-kit`.
* ContextVar-based `TenantContext` dataclass and `tenant_scope` context manager.
* Resilient client pooling wrappers (`SafeClient`, `SafeSpreadsheet`, `SafeWorksheet`) with Tenacity exponential backoff.
* `IsolatedClientRegistry` with unshared client factories and thread-local caching.
* Pydantic v2 `TenantConfigSchema` for tenant registry record validation.
* `TenantRoutingResolver` with Redis batch cache warming for quota protection.
* Constant-time token verification (`verify_tenant_token`) against timing attacks.

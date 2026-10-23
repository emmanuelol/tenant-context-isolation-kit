# 🛡️ tenant-context-isolation-kit

[![CI Pipeline](https://github.com/emmanuelol/tenant-context-isolation-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/emmanuelol/tenant-context-isolation-kit/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

SRE-hardened multi-tenant execution context, strict dependency injection, and resilient client pooling.
Designed specifically for high-concurrency background job workers, asynchronous agents, and zero-trust cloud pipelines.

---

## 🎯 Key Architectural Primitives

| Primitive | Mechanism | SRE Guarantee |
|---|---|---|
| **Immutable TenantContext** | Frozen dataclass + ContextVar scope | Eliminates implicit global state and `os.environ` mutations across concurrent worker jobs. |
| **Cascading Asset Resolution** | 3-tier resolution hierarchy | Resolves operational targets (Registry Vault -> Routing Map -> Fallback) with fast-fail diagnostics. |
| **Redis Quota Protection** | All-tenant batch cache warming | Eliminates Google Sheets API HTTP 429 `RESOURCE_EXHAUSTED` spikes on worker startup. |
| **Transient Error Resilience** | SafeClient with Tenacity exponential retry | Retries socket timeouts and resets while immediately aborting on `WorksheetNotFound`. |
| **Fast-Fail Deadline Armor** | `.with_fast_fail()` wrapper | Bounds socket timeouts and total delay, ensuring worker threads unwind strictly before thread pool timeouts. |
| **Isolated Client Registry** | Fresh factory instantiation & thread-local caching | Guarantees zero cross-tenant credential bleed with automatic child process clearing on `os.fork()`. |
| **Drive Query Injection Shield** | Single-quote escaping (`\'`) | Prevents search query injection when creating or querying Drive folder structures. |
| **Constant-Time Verification** | `secrets.compare_digest` | Protects tenant tokens against side-channel timing attacks. |

---

## 🚀 Quickstart

### 1. Immutable Dependency Injection

```python
from tenant_context_isolation_kit import TenantContext, tenant_scope, get_current_tenant

# Define immutable context at worker boundary
ctx = TenantContext(
    tenant_id="enterprise-org",
    workspace_id="site-mexico",
    sheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
    timezone="America/Mexico_City",
)

# Bind to ContextVar execution scope
with tenant_scope(ctx):
    active = get_current_tenant()
    assert active.workspace_id == "site-mexico"
```

### 2. Resilient Sheets Client & Fast-Fail Execution

```python
from tenant_context_isolation_kit import SafeClient

# Wrap raw gspread client
safe_gc = SafeClient(raw_gspread_client)

# Standard resilient access with exponential backoff
sheet = safe_gc.open_by_key("target-sheet-id")

# Fast-fail execution view for thread-pool bounded workers
fast_gc = safe_gc.with_fast_fail(timeout=(3.0, 5.0), max_delay=10.0)
fast_sheet = fast_gc.open_by_key("target-sheet-id")
```

### 3. Cascading Destination Resolution

```python
from tenant_context_isolation_kit.routing import resolve_cascading_destinations

resolved, missing = resolve_cascading_destinations(
    vault_data={"sheet_id": "primary-sheet-id"},
    map_data={"inbox_folder_id": "inbox-folder-id"},
    default_sheet_id="default-fallback-sheet",
)

if missing:
    raise ValueError(f"Incomplete tenant configuration. Missing: {missing}")
```

---

## 🧪 Testing & Clean-Room Verification

```bash
# Run local test suite
make test

# Run clean-room blacklist verification
make check-blacklist

# Run multi-stage Docker build & Trivy security audit
make audit
```

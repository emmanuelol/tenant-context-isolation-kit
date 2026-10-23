# Security Policy and Threat Model

`tenant-context-isolation-kit` provides security-critical multi-tenant execution context boundaries. We maintain strict security engineering standards and encourage responsible disclosure.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :warning: Security patches only |
| < 0.1.0 | :x:                |

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.**

If you discover a vulnerability or security boundary flaw:
1. Open a **Private Vulnerability Advisory** directly on GitHub under the repository's `Security` tab.
2. Alternatively, email the maintainer at `security@tenant-context.dev` with encrypted PGP details.
3. Include reproducible proof-of-concept code, environment details, and affected components.

We follow coordinated vulnerability disclosure and will respond within 48 hours with a preliminary assessment and remediation roadmap.

---

## Threat Model & Boundary Scope

### In Scope (What this kit defends against):
* **Asynchronous Context Bleed:** Prevention of `ContextVar` leakage across concurrent coroutines, background tasks, or `asyncio.gather` sweeps.
* **Thread-Local State Leakage:** Encapsulation of client instances and credentials inside `IsolatedClientRegistry` preventing cross-thread credential pollution.
* **Timing Attacks:** Constant-time token verification via `secrets.compare_digest` in `verify_tenant_token`.
* **API Resource Exhaustion / Quota Starvation:** Redis-backed batch warming and bounded fast-fail retries preventing downstream HTTP 429 quota depletion.
* **Injection Vulnerabilities:**
  * Strict sanitization of tenant identifiers before binding to SQL session variables (`sanitize_tenant_id_for_sql`).
  * Escaping single quotes in Drive search queries (`get_or_create_folder`) preventing Drive Query Injection.

### Out of Scope (What this kit does NOT defend against):
* **Host / OS Memory Compromise:** Direct OS-level memory tampering, core dumps, or hypervisor side-channel attacks on shared infrastructure.
* **Compromised Infrastructure Credentials:** Root Google Cloud service account key theft or leaked database superuser passwords.
* **Misconfigured Downstream RLS Policies:** PostgreSQL Row-Level Security policies authored without `app.current_tenant` checks.

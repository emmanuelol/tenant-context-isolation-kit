# ADR 003: PostgreSQL Row-Level Security Connection Scoping

* **Status:** Accepted
* **Date:** 2026-10-22
* **Deciders:** Core Architecture Team

---

## Context and Problem Statement

Application-level tenant isolation (e.g., adding `WHERE tenant_id = :id` to every ORM query) relies 100% on developer discipline. In large distributed teams, a single missing `WHERE` clause or unparameterized joined query can leak private records across tenants.

Furthermore, multi-tenant connection pools share physical database connections across requests. If a tenant identifier is bound to a connection using a session-wide variable (`SET app.current_tenant = ...`), and that connection is returned to the pool without being reset, subsequent requests run with the previous tenant's permissions (Connection Pool Poisoning).

---

## Decision

We combine **`tenant-context-isolation-kit`** with native **PostgreSQL Row-Level Security (RLS)** via transaction-scoped local session variables:

1. **Transaction-Local Scoping (`SET LOCAL`):**
   * We execute `SET LOCAL app.current_tenant = :tenant_id;` inside transactions.
   * `SET LOCAL` is automatically rolled back and discarded by PostgreSQL when the transaction commits or aborts, eliminating connection pool poisoning.
2. **Whitelist Sanitization:**
   * `sanitize_tenant_id_for_sql` validates tenant identifiers against `^[a-zA-Z0-9_\-\.]{1,128}$` before string interpolation to eliminate SQL injection risks.
3. **Database-Level Enforcement:**
   * PostgreSQL RLS policies enforce `USING (tenant_id = current_setting('app.current_tenant', true))` at the engine level for all `SELECT`, `INSERT`, `UPDATE`, and `DELETE` operations.

---

## Consequences

### Positive:
* Defense-in-depth: even unqualified queries (`SELECT * FROM documents`) only return rows belonging to the active tenant.
* Immune to connection pool contamination due to transaction-local `SET LOCAL` semantics.
* Independent of application-level ORM filters.

### Negative / Trade-offs:
* Requires PostgreSQL as the database backend.
* Database superuser accounts bypass RLS by default; application database roles must be non-superusers without `BYPASSRLS` privileges.

# ADR 002: Fail-Closed Cascading Routing and Batch Cache Warming

* **Status:** Accepted
* **Date:** 2026-10-22
* **Deciders:** Core Architecture Team

---

## Context and Problem Statement

Multi-tenant platforms relying on distributed routing maps or configuration sheets face two primary operational risks:
1. **API Quota Starvation (HTTP 429):** If each worker task makes an uncoordinated API request to read tenant configuration sheets, high concurrency causes instantaneous quota exhaustion.
2. **Ambiguous Default Fallback:** When a requested tenant cannot be resolved, naive systems often fall back to default assets, potentially writing sensitive tenant data to a global shared folder or spreadsheet.

---

## Decision

1. **Cascading Resolution Hierarchy:**
   * Primary: Vault runtime configuration.
   * Secondary: Static routing dictionary.
   * Tertiary: System default sheet identifier.
2. **Fail-Closed Resolution:**
   * If any mandatory destination (sheet_id, inbox_folder_id, vault_folder_id) cannot be resolved through the explicit hierarchy, `resolve_cascading_destinations` returns the exact missing keys list, allowing workers to fail closed immediately rather than guessing.
3. **Batch Redis Warming on Cache Miss:**
   * On cache miss in `TenantRoutingResolver.get_tenant_config()`, the resolver reads the entire tenant registry in a single I/O read and warms Redis with a 3600-second TTL for *all* registered tenants at once.

---

## Consequences

### Positive:
* Eliminates N+1 API reads to external configuration sheets.
* Guaranteed fail-closed behavior: no accidental cross-tenant data leakage to system defaults.
* High resilience during Google API downtime or network partitions.

### Negative / Trade-offs:
* Redis is an operational dependency for caching; however, fallback to direct sheet reads remains available when Redis is omitted.

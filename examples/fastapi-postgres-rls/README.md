# Production-Grade Multi-Tenant Isolation with PostgreSQL RLS

This reference implementation demonstrates defense-in-depth tenant isolation combining `tenant-context-isolation-kit` and native **PostgreSQL Row-Level Security (RLS)**.

---

## Architectural Problem

In traditional multi-tenant architectures sharing a single database, developers typically rely on application-level filtering:
```sql
SELECT * FROM documents WHERE tenant_id = 'tenant-alpha';
```
If an engineer forgets the `WHERE tenant_id = ...` clause, cross-tenant data leakage occurs immediately.

---

## The Solution: Defense-in-Depth

This architecture enforces isolation at **two independent boundaries**:

```
[ HTTP Request ]
       │  (Header: 'X-Tenant-ID: acme')
       ▼
[ TenantContextMiddleware ]
       │  (Binds TenantContext to ContextVar via tenant_scope)
       ▼
[ Database Session Hook ]
       │  (Executes 'SET LOCAL app.current_tenant = :tenant_id')
       ▼
[ PostgreSQL Kernel RLS ]
          (Policy: tenant_id = current_setting('app.current_tenant', true))
```

Even if the application executes an unqualified `SELECT * FROM documents`, the PostgreSQL query engine itself rejects rows not matching `app.current_tenant`.

---

## Quickstart

### 1. Launch PostgreSQL and API
```bash
docker compose up -d
```

### 2. Initialize PostgreSQL Table & RLS Policy
Run in `psql` or container:
```sql
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL
);

-- Enable Row-Level Security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Enforce strict tenant isolation policy
CREATE POLICY tenant_isolation_policy ON documents
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true));
```

### 3. Verify Isolation via Curl

#### Create document as Tenant Alpha:
```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-alpha" \
  -d '{"title": "Alpha Confidential Q3", "content": "Revenue projected at $4M"}'
```

#### Create document as Tenant Beta:
```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-beta" \
  -d '{"title": "Beta Secret Strategy", "content": "Expanding into APAC"}'
```

#### Query as Tenant Alpha (Returns only Alpha docs):
```bash
curl http://localhost:8000/documents -H "X-Tenant-ID: tenant-alpha"
```
**Response:**
```json
[
  {
    "id": 1,
    "tenant_id": "tenant-alpha",
    "title": "Alpha Confidential Q3",
    "content": "Revenue projected at $4M"
  }
]
```
*(Notice: Tenant Beta's documents are completely invisible!)*

#### Query as Tenant Beta (Returns only Beta docs):
```bash
curl http://localhost:8000/documents -H "X-Tenant-ID: tenant-beta"
```
**Response:**
```json
[
  {
    "id": 2,
    "tenant_id": "tenant-beta",
    "title": "Beta Secret Strategy",
    "content": "Expanding into APAC"
  }
]
```

#### Query with No Tenant Header:
```bash
curl http://localhost:8000/documents
```
**Response:** `401 Unauthorized`

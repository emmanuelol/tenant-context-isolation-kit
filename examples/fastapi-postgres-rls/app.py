"""
FastAPI + PostgreSQL Row-Level Security (RLS) Multi-Tenant Reference Architecture.
==================================================================================
Demonstrates ironclad multi-tenant data isolation using tenant-context-isolation-kit
and PostgreSQL Row-Level Security policies.

Flow:
  1. Incoming HTTP request includes 'X-Tenant-ID: acme-corp'.
  2. TenantContextMiddleware validates header and binds TenantContext to ContextVar.
  3. Database connection listener executes 'SET LOCAL app.current_tenant = :tenant_id'.
  4. Postgres kernel enforces 'tenant_isolation_policy' on all SQL queries automatically.
     Even 'SELECT * FROM documents' only returns rows owned by 'acme-corp'.
"""
from __future__ import annotations

import os
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, select, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from tenant_context_isolation_kit import (
    TenantContextMiddleware,
    get_current_tenant,
    attach_tenant_rls_listener,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/multitenant_demo",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)


class DocumentCreate(BaseModel):
    title: str
    content: str


class DocumentResponse(BaseModel):
    id: int
    tenant_id: str
    title: str
    content: str

    class Config:
        from_attributes = True


def get_db():
    """
    Database dependency that yields a Session with PostgreSQL RLS local tenant scoping.
    """
    db: Session = SessionLocal()
    try:
        current = get_current_tenant()
        if not current or not current.tenant_id:
            raise HTTPException(status_code=401, detail="Missing or unauthenticated tenant")

        # Execute SET LOCAL app.current_tenant = :tenant_id on transaction
        attach_tenant_rls_listener(db.connection(), is_local=True)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app = FastAPI(
    title="Multi-Tenant RLS Demo",
    description="Production-grade multi-tenant API powered by tenant-context-isolation-kit",
    version="1.0.0",
)

# Attach ASGI context isolation middleware
app.add_middleware(
    TenantContextMiddleware,
    tenant_header="x-tenant-id",
    workspace_header="x-workspace-id",
    enforce_tenant=False,  # Allow unauthenticated health check, enforce on routes
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/whoami")
def whoami():
    current = get_current_tenant()
    if not current:
        return {"authenticated": False, "tenant": None}
    return {
        "authenticated": True,
        "tenant_id": current.tenant_id,
        "workspace_id": current.workspace_id,
    }


@app.post("/documents", response_model=DocumentResponse)
def create_document(doc_in: DocumentCreate, db: Session = Depends(get_db)):
    current = get_current_tenant()
    assert current is not None
    doc = Document(
        tenant_id=current.tenant_id,
        title=doc_in.title,
        content=doc_in.content,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@app.get("/documents", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    """
    Note: Query intentionally has no WHERE tenant_id = ... filter.
    PostgreSQL Row-Level Security automatically isolates rows at kernel level.
    """
    return db.query(Document).all()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

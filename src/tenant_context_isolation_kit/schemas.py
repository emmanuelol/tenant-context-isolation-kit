"""
Multi-Tenant Configuration and Record Validation Schemas.
=========================================================
Strict Pydantic v2 schemas for parsing, normalizing, and validating tenant registry records.
"""
from __future__ import annotations

from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


def _clean_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none", "null") else None


class TenantConfigSchema(BaseModel):
    """
    Standard schema for tenant configuration records.
    Allows dynamic extra fields for flexible downstream adapter enrichment.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None
    sheet_id: Optional[str] = None
    inbox_folder_id: Optional[str] = None
    vault_folder_id: Optional[str] = None
    manager_phone: Optional[str] = None
    shift_log_sheet_id: Optional[str] = None
    timezone: str = Field(default="America/Mexico_City")
    cogs_margin: Optional[float] = None

    @field_validator(
        "tenant_id",
        "workspace_id",
        "sheet_id",
        "inbox_folder_id",
        "vault_folder_id",
        "manager_phone",
        "shift_log_sheet_id",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, v: Any) -> Optional[str]:
        return _clean_str(v)

    @field_validator("timezone", mode="before")
    @classmethod
    def clean_timezone(cls, v: Any) -> str:
        s = _clean_str(v)
        return s or "America/Mexico_City"

    @field_validator("cogs_margin", mode="before")
    @classmethod
    def clean_cogs_margin(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        try:
            s_val = str(v).replace("%", "").strip()
            val = float(s_val)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(0.85, val)) if val > 0 else 0.0
        except (ValueError, TypeError):
            return None

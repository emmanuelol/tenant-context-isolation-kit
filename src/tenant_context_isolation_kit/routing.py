"""
Multi-Tenant Routing, Quota Protection, and Safe Asset Management.
=================================================================
Implements cascading credential and destination resolution (Vault -> Routing Map -> Fallback),
Redis batch cache warming to prevent Google Sheets API quota exhaustion (HTTP 429),
constant-time tenant token verification, legacy E.164 normalization, and Drive API injection prevention.
"""
from __future__ import annotations

import re
import json
import logging
import secrets
import socket
from typing import Optional, Dict, Any, Tuple, List
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from googleapiclient.errors import HttpError
from tenant_context_isolation_kit.schemas import TenantConfigSchema

logger = logging.getLogger(__name__)


def normalize_phone_e164(raw_phone: str) -> str:
    """
    Sanitizes and normalizes phone numbers to standard E.164 with Mexican mobile compatibility (+521).
    """
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", str(raw_phone))
    if not digits:
        return ""
    if len(digits) == 10:
        digits = f"521{digits}"
    elif len(digits) == 12 and digits.startswith("52"):
        digits = f"521{digits[2:]}"
    return f"+{digits}"


def resolve_cascading_destinations(
    vault_data: Optional[Dict[str, Any]],
    map_data: Optional[Dict[str, Any]],
    default_sheet_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Resolves operational target assets using the Cascading Resolution Hierarchy:
    1. Primary: Vault configuration (centralized runtime management).
    2. Secondary: Static routing map dictionary.
    3. Tertiary: System default sheet identifier.
    Returns resolved dictionary and list of any unfulfilled target keys.
    """
    v = vault_data or {}
    m = map_data or {}

    sheet_id = v.get("sheet_id") or m.get("sheet_id") or default_sheet_id
    inbox_folder_id = v.get("inbox_folder_id") or m.get("inbox_folder_id")
    vault_folder_id = v.get("vault_folder_id") or m.get("vault_folder_id")

    resolved = {
        "sheet_id": sheet_id,
        "inbox_folder_id": inbox_folder_id,
        "vault_folder_id": vault_folder_id,
    }

    missing = [k for k, val in resolved.items() if not val]
    return resolved, missing


class TenantRoutingResolver:
    """
    Resolver for multi-tenant configuration and active tenant registries.
    Features Redis batch cache warming on miss to eliminate HTTP 429 quota exhaustion.
    """

    def __init__(self, redis_client: Optional[Any] = None, cache_prefix: str = "tenant_creds"):
        self.redis = redis_client
        self._cache_prefix = cache_prefix

    def get_tenant_config(
        self,
        gc: Any,
        admin_sheet_id: str,
        workspace_id: str,
        tab_name: str = "Tenant_Registry",
        id_column: str = "workspace_id",
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches tenant credentials with Redis cache-first lookup.
        On cache miss, reads entire tab and warms Redis for ALL tenants in a single I/O sweep.
        """
        cache_key = f"{self._cache_prefix}_{workspace_id}"
        if self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read failed for {cache_key}: {e}")

        try:
            ws = gc.open_by_key(admin_sheet_id).worksheet(tab_name)
            all_records = ws.get_all_records()

            # Batch warm Redis for quota protection (3600s TTL)
            if self.redis:
                try:
                    for rec in all_records:
                        target_id = rec.get(id_column) or rec.get("workspace_id")
                        if target_id:
                            self.redis.setex(
                                f"{self._cache_prefix}_{target_id}",
                                3600,
                                json.dumps(rec),
                            )
                except Exception as cache_err:
                    logger.warning(f"Redis batch cache warming failed: {cache_err}")

            for rec in all_records:
                target_id = rec.get(id_column) or rec.get("workspace_id")
                if str(target_id) == str(workspace_id):
                    try:
                        validated = TenantConfigSchema(**rec)
                        return validated.model_dump(by_alias=True)
                    except Exception as ve:
                        logger.warning(f"Tenant config validation warning for {workspace_id}: {ve}")
                        return rec
            return None
        except Exception as e:
            logger.error(f"Error fetching tenant config for {workspace_id}: {e}")
            return None

    def get_active_tenants(
        self,
        gc: Any,
        admin_sheet_id: str,
        tab_name: str = "Active_Tenants",
        status_column: str = "status",
        active_value: str = "Active",
    ) -> List[Dict[str, Any]]:
        """
        Fetches all active tenants with 15-minute Redis caching.
        """
        cache_key = f"active_tenants_cache_{tab_name}"
        if self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")

        try:
            ws = gc.open_by_key(admin_sheet_id).worksheet(tab_name)
            records = ws.get_all_records()
            active = [r for r in records if r.get(status_column) == active_value]

            if self.redis:
                try:
                    self.redis.setex(cache_key, 900, json.dumps(active))
                except Exception as e:
                    logger.warning(f"Redis cache write failed: {e}")
            return active
        except Exception as e:
            logger.error(f"Error fetching active tenants: {e}")
            return []


def verify_tenant_token(
    resolver: TenantRoutingResolver,
    gc: Any,
    admin_sheet_id: str,
    workspace_id: str,
    candidate_token: str,
    token_field: str = "dashboard_token",
) -> bool:
    """
    Validates candidate token against registered tenant token in constant time (anti-timing attack).
    """
    if not candidate_token:
        return False
    config = resolver.get_tenant_config(gc, admin_sheet_id, workspace_id)
    if not config:
        return False
    expected = config.get(token_field) or config.get("dashboard_token")
    if not expected:
        return False
    return secrets.compare_digest(str(expected).strip(), str(candidate_token).strip())


def _is_retryable_drive_error(exc: BaseException) -> bool:
    if isinstance(exc, HttpError):
        status = getattr(exc, "status_code", None)
        if status is None and getattr(exc, "resp", None):
            status = getattr(exc.resp, "status", None)
        try:
            status = int(status)
        except (TypeError, ValueError):
            return False
        return status in (429, 500, 502, 503, 504)
    return isinstance(exc, (ConnectionError, TimeoutError, socket.error, OSError))


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    retry=retry_if_exception(_is_retryable_drive_error),
    reraise=True,
)
def get_or_create_folder(drive_service: Any, folder_name: str, parent_id: Optional[str] = None) -> str:
    """
    Resolves or creates a Google Drive folder safely.
    Escapes single quotes to prevent Drive Query Injection attacks.
    """
    safe_name = folder_name.replace("'", "\\'")
    query = f"name='{safe_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = drive_service.files().list(q=query, spaces="drive", fields="files(id)").execute()
    items = results.get("files", [])

    if items:
        return items[0]["id"]

    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    created = drive_service.files().create(body=metadata, fields="id").execute()
    return created.get("id")

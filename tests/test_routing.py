import json
import pytest
from unittest.mock import MagicMock
import httplib2
from googleapiclient.errors import HttpError

from tenant_context_isolation_kit.routing import (
    TenantRoutingResolver,
    resolve_cascading_destinations,
    normalize_phone_e164,
    verify_tenant_token,
    get_or_create_folder,
)


class TestCascadingDestinations:
    def test_primary_priority_vault_record(self):
        vault_data = {"sheet_id": "vault_sheet_111", "inbox_folder_id": "inbox_111", "vault_folder_id": "vault_111"}
        map_data = {"sheet_id": "map_sheet_222"}
        res, missing = resolve_cascading_destinations(vault_data, map_data, default_sheet_id="default_333")
        assert res["sheet_id"] == "vault_sheet_111"
        assert res["inbox_folder_id"] == "inbox_111"
        assert res["vault_folder_id"] == "vault_111"
        assert len(missing) == 0

    def test_secondary_priority_map_data(self):
        vault_data = {}
        map_data = {"sheet_id": "map_sheet_222", "inbox_folder_id": "inbox_222", "vault_folder_id": "vault_222"}
        res, missing = resolve_cascading_destinations(vault_data, map_data, default_sheet_id="default_333")
        assert res["sheet_id"] == "map_sheet_222"
        assert len(missing) == 0

    def test_fallback_priority_default_sheet(self):
        vault_data = {"inbox_folder_id": "inbox_333", "vault_folder_id": "vault_333"}
        map_data = {}
        res, missing = resolve_cascading_destinations(vault_data, map_data, default_sheet_id="default_333")
        assert res["sheet_id"] == "default_333"
        assert len(missing) == 0

    def test_missing_destinations_detected(self):
        res, missing = resolve_cascading_destinations({}, {})
        assert "sheet_id" in missing
        assert "inbox_folder_id" in missing
        assert "vault_folder_id" in missing


class TestPhoneNormalization:
    def test_preserves_valid_e164_mexico(self):
        assert normalize_phone_e164("+5215512345678") == "+5215512345678"

    def test_local_10_digits_normalizes_to_mexico_mobile(self):
        assert normalize_phone_e164("5512345678") == "+5215512345678"

    def test_12_digits_with_country_code_inserts_mobile_prefix(self):
        assert normalize_phone_e164("525512345678") == "+5215512345678"

    def test_sanitizes_spaces_and_quotes(self):
        assert normalize_phone_e164('"+52 55 1234 5678"') == "+5215512345678"

    def test_empty_phone_returns_empty_string(self):
        assert normalize_phone_e164("") == ""


class TestTenantRoutingResolver:
    def test_get_tenant_config_redis_cache_hit(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({
            "tenant_id": "t1",
            "workspace_id": "w1",
            "sheet_id": "s1",
        })
        resolver = TenantRoutingResolver(redis_client=mock_redis)
        mock_gc = MagicMock()

        config = resolver.get_tenant_config(mock_gc, "admin_sheet_id", "w1", tab_name="Registry")
        assert config is not None
        assert config["workspace_id"] == "w1"
        mock_gc.open_by_key.assert_not_called()

    def test_get_tenant_config_batch_cache_warming_on_miss(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # Cache miss

        mock_gc = MagicMock()
        mock_ws = MagicMock()
        mock_gc.open_by_key.return_value.worksheet.return_value = mock_ws
        mock_ws.get_all_records.return_value = [
            {"workspace_id": "w1", "tenant_id": "t1", "sheet_id": "s1"},
            {"workspace_id": "w2", "tenant_id": "t2", "sheet_id": "s2"},
        ]

        resolver = TenantRoutingResolver(redis_client=mock_redis)
        config = resolver.get_tenant_config(mock_gc, "admin_sheet_id", "w1", tab_name="Registry")

        assert config is not None
        assert config["workspace_id"] == "w1"
        assert mock_redis.setex.call_count == 2

    def test_get_active_tenants_caches_in_redis(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        mock_gc = MagicMock()
        mock_ws = MagicMock()
        mock_gc.open_by_key.return_value.worksheet.return_value = mock_ws
        mock_ws.get_all_records.return_value = [
            {"workspace_id": "w1", "status": "Active"},
            {"workspace_id": "w2", "status": "Inactive"},
        ]

        resolver = TenantRoutingResolver(redis_client=mock_redis)
        active = resolver.get_active_tenants(mock_gc, "admin_sheet_id", tab_name="Active_Tenants")

        assert len(active) == 1
        assert active[0]["workspace_id"] == "w1"
        mock_redis.setex.assert_called_once()


class TestTokenVerification:
    def test_verify_tenant_token_constant_time(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"dashboard_token": "secret_token_123"})
        mock_gc = MagicMock()

        resolver = TenantRoutingResolver(redis_client=mock_redis)
        assert verify_tenant_token(resolver, mock_gc, "admin_id", "w1", "secret_token_123") is True
        assert verify_tenant_token(resolver, mock_gc, "admin_id", "w1", "wrong_token") is False
        assert verify_tenant_token(resolver, mock_gc, "admin_id", "w1", "") is False


class TestDriveFolderSanitization:
    def test_get_or_create_folder_escapes_single_quotes_anti_injection(self):
        mock_drive = MagicMock()
        mock_drive.files().list().execute.return_value = {"files": [{"id": "f_123"}]}

        folder_id = get_or_create_folder(mock_drive, "O'Reilly & Associates", parent_id="root_id")
        assert folder_id == "f_123"

        call_q = mock_drive.files().list.call_args[1]["q"]
        assert "name='O\\'Reilly & Associates'" in call_q

    def test_get_or_create_folder_creates_if_missing(self):
        mock_drive = MagicMock()
        mock_drive.files().list().execute.return_value = {"files": []}
        mock_drive.files().create().execute.return_value = {"id": "new_created_folder"}

        folder_id = get_or_create_folder(mock_drive, "New_Workspace", parent_id="root_id")
        assert folder_id == "new_created_folder"

    def test_get_or_create_folder_does_not_retry_forbidden_403(self):
        mock_drive = MagicMock()
        resp_403 = httplib2.Response({"status": 403, "reason": "Forbidden"})
        err_403 = HttpError(resp_403, b"Forbidden")
        mock_drive.files().list().execute.side_effect = err_403

        with pytest.raises(HttpError):
            get_or_create_folder(mock_drive, "Secure_Folder")

        assert mock_drive.files().list().execute.call_count == 1

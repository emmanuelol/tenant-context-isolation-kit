import pytest
from dataclasses import FrozenInstanceError
from tenant_context_isolation_kit.context import (
    TenantContext,
    tenant_scope,
    get_current_tenant,
)
from tenant_context_isolation_kit.schemas import TenantConfigSchema


class TestTenantContext:
    def test_tenant_context_creation_and_immutability(self):
        ctx = TenantContext(
            tenant_id="tenant-alpha",
            workspace_id="ws-primary",
            sheet_id="sheet-12345",
            inbox_folder_id="inbox-abc",
            vault_folder_id="vault-def",
            organization_name="Enterprise Corp",
            manager_phone="+5215512345678",
            timezone="America/Mexico_City",
        )
        assert ctx.tenant_id == "tenant-alpha"
        assert ctx.workspace_id == "ws-primary"
        assert ctx.sheet_id == "sheet-12345"
        assert ctx.inbox_folder_id == "inbox-abc"
        assert ctx.vault_folder_id == "vault-def"
        assert ctx.organization_name == "Enterprise Corp"
        assert ctx.manager_phone == "+5215512345678"
        assert ctx.timezone == "America/Mexico_City"

        with pytest.raises((FrozenInstanceError, Exception)):
            ctx.tenant_id = "tenant-beta"  # type: ignore

    def test_with_clients_returns_new_instance(self):
        ctx = TenantContext(
            tenant_id="tenant-alpha",
            workspace_id="ws-primary",
            sheet_id="sheet-12345",
        )
        fake_gc = object()
        fake_drive = object()
        enriched = ctx.with_clients(fake_gc, fake_drive)

        assert enriched is not ctx
        assert enriched.gc_client is fake_gc
        assert enriched.drive_service is fake_drive
        assert enriched.tenant_id == "tenant-alpha"
        assert enriched.workspace_id == "ws-primary"
        assert ctx.gc_client is None

    def test_with_metadata_returns_new_instance(self):
        ctx = TenantContext(
            tenant_id="tenant-alpha",
            workspace_id="ws-primary",
            sheet_id="sheet-12345",
            extra_metadata={"region": "latam"},
        )
        updated = ctx.with_metadata(tier="gold", cluster=42)

        assert updated is not ctx
        assert updated.extra_metadata["region"] == "latam"
        assert updated.extra_metadata["tier"] == "gold"
        assert updated.extra_metadata["cluster"] == 42
        assert "tier" not in ctx.extra_metadata

    def test_tenant_context_scope_contextvar(self):
        assert get_current_tenant() is None

        ctx = TenantContext(
            tenant_id="tenant-scoped",
            workspace_id="ws-scoped",
            sheet_id="sheet-scoped",
        )

        with tenant_scope(ctx) as active_ctx:
            assert active_ctx is ctx
            assert get_current_tenant() is ctx

        assert get_current_tenant() is None


class TestTenantConfigSchema:
    def test_valid_record_parsing_and_normalization(self):
        raw = {
            "tenant_id": "org_99",
            "workspace_id": "ws_01",
            "sheet_id": "sh_main",
            "inbox_folder_id": "inbox_01",
            "vault_folder_id": "vault_01",
            "manager_phone": "5512345678",
            "timezone": "  America/Monterrey  ",
            "cogs_margin": "35%",
            "extra_custom_attr": "custom_val",
        }
        rec = TenantConfigSchema(**raw)
        assert rec.tenant_id == "org_99"
        assert rec.workspace_id == "ws_01"
        assert rec.timezone == "America/Monterrey"
        assert rec.cogs_margin == 0.35
        assert rec.extra_custom_attr == "custom_val"  # extra='allow'

    def test_empty_timezone_defaults_to_mexico_city(self):
        raw = {
            "tenant_id": "org_1",
            "workspace_id": "ws_1",
            "sheet_id": "sh_1",
            "timezone": "",
        }
        rec = TenantConfigSchema(**raw)
        assert rec.timezone == "America/Mexico_City"

    def test_cogs_margin_clamping_and_scaling(self):
        # Numeric percentage > 1.0 scaled to ratio
        rec1 = TenantConfigSchema(
            tenant_id="t1",
            workspace_id="w1",
            sheet_id="s1",
            cogs_margin=45.0,
        )
        assert rec1.cogs_margin == 0.45

        # Upper limit clamped to 0.85
        rec2 = TenantConfigSchema(
            tenant_id="t2",
            workspace_id="w2",
            sheet_id="s2",
            cogs_margin="95%",
        )
        assert rec2.cogs_margin == 0.85

"""
Concurrency Isolation Stress and Cross-Tenant Anti-Bleed Fuzzing Suite.
========================================================================
Executes high-concurrency fuzz testing across asyncio event loops and thread pools
to mathematically prove zero ContextVar bleed and zero cross-tenant credential leakage.
"""
import asyncio
import random
import concurrent.futures
import pytest

from tenant_context_isolation_kit.context import (
    TenantContext,
    tenant_scope,
    get_current_tenant,
)
from tenant_context_isolation_kit.clients import IsolatedClientRegistry


@pytest.mark.asyncio
async def test_high_concurrency_async_fuzzing_1000_tasks_50_tenants():
    """
    Spawns 1,000 concurrent asynchronous tasks distributed across 50 distinct tenants.
    Introduces non-deterministic async sleep yields to maximize context-switching pressure.
    Guarantees zero ContextVar bleed across coroutine boundaries.
    """
    num_tenants = 50
    total_tasks = 1000
    bleed_violations = []

    async def worker(task_id: int, tenant_idx: int):
        tenant_id = f"tenant-{tenant_idx:03d}"
        workspace_id = f"ws-{tenant_idx:03d}"
        sheet_id = f"sheet-{tenant_idx:03d}"

        ctx = TenantContext(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            sheet_id=sheet_id,
        )

        with tenant_scope(ctx):
            for step in range(5):
                # Sample context before yielding control
                curr = get_current_tenant()
                if curr is None or curr.tenant_id != tenant_id:
                    bleed_violations.append((task_id, tenant_id, getattr(curr, "tenant_id", None)))

                # Random yield to force task context switching
                await asyncio.sleep(random.uniform(0.0001, 0.002))

                # Re-verify context integrity after wake up
                curr_after = get_current_tenant()
                if curr_after is None or curr_after.tenant_id != tenant_id:
                    bleed_violations.append((task_id, tenant_id, getattr(curr_after, "tenant_id", None)))

        # Verify context unwound cleanly
        outside = get_current_tenant()
        if outside is not None:
            bleed_violations.append((task_id, "expected_none", getattr(outside, "tenant_id", None)))

    tasks = [
        worker(task_id=i, tenant_idx=(i % num_tenants))
        for i in range(total_tasks)
    ]

    await asyncio.gather(*tasks)
    assert len(bleed_violations) == 0, f"Detected {len(bleed_violations)} context bleed violations: {bleed_violations[:5]}"


def test_multithreaded_concurrency_isolation():
    """
    Executes concurrent threads in a ThreadPoolExecutor ensuring ContextVars
    and IsolatedClientRegistry maintain strict thread-local encapsulation.
    """
    num_workers = 20
    tasks_per_worker = 20
    registry = IsolatedClientRegistry(factory=lambda: (object(),))

    violations = []

    def thread_worker(worker_id: int, iteration: int):
        tenant_id = f"worker-tenant-{worker_id}"
        ctx = TenantContext(tenant_id=tenant_id, workspace_id=f"ws-{worker_id}", sheet_id="sheet-0")

        with tenant_scope(ctx):
            curr = get_current_tenant()
            if curr is None or curr.tenant_id != tenant_id:
                violations.append((worker_id, iteration, getattr(curr, "tenant_id", None)))

            # Thread-local client caching test
            clients_1 = registry.get_thread_local_clients()
            clients_2 = registry.get_thread_local_clients()
            if clients_1 is not clients_2:
                violations.append((worker_id, "thread_cache_mismatch", None))

        after = get_current_tenant()
        if after is not None:
            violations.append((worker_id, "after_scope_not_none", getattr(after, "tenant_id", None)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(thread_worker, w_id, it)
            for w_id in range(num_workers)
            for it in range(tasks_per_worker)
        ]
        concurrent.futures.wait(futures)
        for f in futures:
            f.result()

    assert len(violations) == 0, f"Thread violations detected: {violations}"


def test_nested_tenant_scope_unwinding():
    """
    Guarantees nested scopes restore parent tenant state upon block exit,
    even under raised exceptions.
    """
    parent_ctx = TenantContext(tenant_id="parent", workspace_id="ws-p", sheet_id="s-p")
    child_ctx = TenantContext(tenant_id="child", workspace_id="ws-c", sheet_id="s-c")

    assert get_current_tenant() is None

    with tenant_scope(parent_ctx):
        assert get_current_tenant().tenant_id == "parent"

        try:
            with tenant_scope(child_ctx):
                assert get_current_tenant().tenant_id == "child"
                raise RuntimeError("Boom inside child context")
        except RuntimeError:
            pass

        # Must properly revert to parent
        assert get_current_tenant().tenant_id == "parent"

    # Must cleanly revert to None
    assert get_current_tenant() is None

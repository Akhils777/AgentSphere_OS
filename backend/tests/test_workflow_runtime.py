import pytest
from app.runtime.workflow_engine import engine
from app.memory.firestore_memory import memory_bank
from app.storage import store


@pytest.mark.asyncio
async def test_workflow_execution_success():
    entity_name = "test_supplier_omega"
    wf = engine.create("Evaluate supplier risk before onboarding", "test-user", {"entity": entity_name})
    assert wf["status"] == "queued"
    assert wf["progress"] == 0

    await engine.run(wf)

    updated_wf = engine.get(wf["workflow_id"])
    assert updated_wf["status"] == "completed"
    assert updated_wf["progress"] == 100
    assert updated_wf.get("memory_updated") is True

    # Verify tasks were created and completed
    tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
    assert len(tasks) == 4
    for task in tasks:
        assert task["status"] == "completed"
        assert task["execution_time_ms"] is not None

    # Verify entity memory was recorded truthfully
    mem = memory_bank.recall(entity_name)
    assert mem is not None
    assert mem["entity"] == entity_name
    assert "Supplier risk assessment complete" in mem["previous_analysis"]
    assert "Supplier risk assessment completed" in mem["previous_decisions"]


@pytest.mark.asyncio
async def test_workflow_execution_failure():
    entity_name = "test_supplier_failure"
    # Inject mock_error to simulate provider quota or timeout failure
    wf = engine.create("Evaluate high risk vendor", "test-user", {
        "entity": entity_name,
        "mock_error": "quota_exceeded"
    })

    await engine.run(wf)

    updated_wf = engine.get(wf["workflow_id"])
    assert updated_wf["status"] == "failed"
    assert updated_wf.get("memory_updated") is False

    # Verify task recorded the failure
    tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
    failed_tasks = [t for t in tasks if t["status"] == "failed"]
    assert len(failed_tasks) > 0
    assert failed_tasks[0]["error"] == "quota_exceeded"


@pytest.mark.asyncio
async def test_memory_integrity_after_failure():
    """Ensure failed workflows never write success records and never overwrite existing memory."""
    entity_name = "established_vendor_corp"
    # Seed original valid memory
    memory_bank.remember(
        entity_name,
        "Original pre-audit approval record from 2025.",
        ["Initial onboarding approved"],
        "WF-LEGACY-001"
    )

    # Provoke a failed workflow on this entity
    wf = engine.create("Re-evaluate vendor after alert", "test-user", {
        "entity": entity_name,
        "mock_error": "model_unavailable"
    })

    await engine.run(wf)

    updated_wf = engine.get(wf["workflow_id"])
    assert updated_wf["status"] == "failed"
    assert updated_wf.get("memory_updated") is False

    # Critical check: Existing memory must remain completely intact and unaltered
    mem = memory_bank.recall(entity_name)
    assert mem is not None
    assert mem["previous_analysis"] == "Original pre-audit approval record from 2025."
    assert mem["workflow_id"] == "WF-LEGACY-001"
    assert mem["previous_decisions"] == ["Initial onboarding approved"]


@pytest.mark.asyncio
async def test_missing_entity_does_not_default_to_supplier_abc():
    """Ensure workflows without explicit entity do not silently corrupt supplier_ABC."""
    # Ensure supplier_ABC is empty initially in isolated store
    assert memory_bank.recall("supplier_ABC") is None

    # Launch workflow without entity in context
    wf = engine.create("General analysis without target vendor", "test-user", {})

    await engine.run(wf)

    updated_wf = engine.get(wf["workflow_id"])
    assert updated_wf["status"] == "completed"
    assert updated_wf.get("memory_updated") is False

    # Critical check: supplier_ABC must NOT have been created or modified
    assert memory_bank.recall("supplier_ABC") is None


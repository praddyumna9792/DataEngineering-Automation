"""
Unit and Integration tests for Stateful Execution Engine and Checkpoint Recovery.
"""
import pytest
from core.execution_engine import ExecutionEngine
from core.migration_planner import MigrationPlanner
from core.models import RunStatus, BatchStatus


@pytest.fixture
def planned_customer_migration(tmp_path):
    planner = MigrationPlanner()
    plan, diag = planner.create_plan(
        source_table_name="customer_history",
        target_table_name="CUSTOMER_HISTORY",
    )
    assert plan is not None
    return plan


def test_execution_requires_approval(planned_customer_migration):
    engine = ExecutionEngine()
    plan = planned_customer_migration
    # Must be unapproved by default
    assert plan.is_approved is False

    with pytest.raises(ValueError, match="Plan must be explicitly approved"):
        engine.start_migration(plan)


def test_approved_plan_executes_successfully(planned_customer_migration):
    engine = ExecutionEngine()
    planner = MigrationPlanner()
    plan = planned_customer_migration

    # Approve plan
    ok, errs = planner.approve_plan(plan, "QA Tester")
    assert ok is True

    # Execute
    run = engine.start_migration(plan)
    assert run.status == RunStatus.COMPLETED
    assert run.total_rows_migrated == plan.source_metadata.row_count
    assert run.reconciliation_report is not None
    assert run.reconciliation_report["status"] == "VERIFIED_100_PERCENT"
    assert all(b.status == BatchStatus.COMPLETED for b in run.batches)


def test_simulated_failure_and_resume(planned_customer_migration):
    engine = ExecutionEngine()
    planner = MigrationPlanner()
    plan = planned_customer_migration

    ok, _ = planner.approve_plan(plan, "QA Tester")
    assert ok is True

    # Start run with intentional failure on batch 2
    run = engine.start_migration(plan, simulate_failure_on_batch=2)
    assert run.status == RunStatus.PARTIALLY_COMPLETED
    assert run.batches[0].status == BatchStatus.COMPLETED
    assert run.batches[1].status == BatchStatus.FAILED

    # Resume the interrupted run
    resumed = engine.resume_migration(run.run_id)
    assert resumed.status == RunStatus.COMPLETED
    assert resumed.batches[0].status == BatchStatus.COMPLETED
    assert resumed.batches[1].status == BatchStatus.COMPLETED
    assert resumed.total_rows_migrated == plan.source_metadata.row_count

"""
End-to-End Simulation tests for LegacyLift workflows.
Tests complete paths: Discovery -> Planning -> Review -> Approval -> Execution -> Reconciliation.
"""
import pytest
from core.migration_planner import MigrationPlanner
from core.execution_engine import ExecutionEngine
from core.models import RunStatus, LoadStrategy


def test_e2e_case_a_new_snowflake_target():
    """Complete workflow for a target table that does NOT exist in Snowflake."""
    planner = MigrationPlanner()
    engine = ExecutionEngine()

    # 1. User provides only 2 table names
    plan, diag = planner.create_plan(
        source_table_name="orders_archive",
        target_table_name="ORDERS_ARCHIVE",
    )
    assert plan is not None
    assert plan.target_exists is False
    assert plan.load_strategy == LoadStrategy.INITIAL_LOAD
    assert "CREATE TABLE IF NOT EXISTS" in plan.stage4_sql

    # 2. Approve
    approved, errs = planner.approve_plan(plan, "Senior Architect")
    assert approved is True
    assert plan.is_approved is True

    # 3. Execute
    run = engine.start_migration(plan)
    assert run.status == RunStatus.COMPLETED
    assert run.total_rows_migrated == 5_400_000
    assert run.reconciliation_report["parity_percentage"] == 100.0


def test_e2e_case_b_existing_snowflake_target():
    """Complete workflow for an existing Snowflake table with compatible schema."""
    planner = MigrationPlanner()
    engine = ExecutionEngine()

    plan, diag = planner.create_plan(
        source_table_name="customer_history",
        target_table_name="CUSTOMER_HISTORY",
    )
    assert plan is not None
    assert plan.target_exists is True
    # Redundant CREATE TABLE must NOT be generated!
    assert "CREATE TABLE IF NOT EXISTS" not in plan.stage4_sql
    assert "Redundant CREATE TABLE DDL is SUPPRESSED" in plan.stage4_sql

    # Approve & Execute
    planner.approve_plan(plan, "Lead Architect")
    run = engine.start_migration(plan)
    assert run.status == RunStatus.COMPLETED
    assert run.total_rows_migrated == 1_250_000


def test_e2e_incompatible_schema_blocked():
    """Incompatible schema prevents unsafe automated execution."""
    planner = MigrationPlanner()
    plan, diag = planner.create_plan(
        source_table_name="employee_records",
        target_table_name="EMPLOYEE_RECORDS",
    )
    assert plan is None
    assert any("INCOMPATIBLE" in e for e in diag["errors"])


def test_e2e_ambiguous_source_table():
    """Ambiguous source table requires user specification."""
    planner = MigrationPlanner()
    plan, diag = planner.create_plan(
        source_table_name="legacy_transactions",
        target_table_name="LEGACY_TRANSACTIONS",
    )
    assert plan is None
    assert diag["source_status"] == "AMBIGUOUS"
    assert len(diag["source_matches"]) == 2


def test_e2e_sql_edit_invalidates_approval():
    """Editing SQL after approval immediately revokes approval."""
    planner = MigrationPlanner()
    plan, _ = planner.create_plan(
        source_table_name="orders_archive",
        target_table_name="ORDERS_ARCHIVE",
    )
    planner.approve_plan(plan)
    assert plan.is_approved is True

    # User modifies Stage 1 SQL
    plan = planner.update_plan_sql(plan, "stage1", "-- Modified by user\nSELECT 1;")
    assert plan.is_approved is False
    assert plan.sql_modified_since_approval is True

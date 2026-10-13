"""
Unit tests for Mandatory Existing Snowflake Target Logic.
Verifies Case A (New target) and Case B (Existing target).
"""
import pytest
from core.target_table_manager import TargetTableManager
from core.models import TableMetadata, ColumnMetadata, LoadStrategy


@pytest.fixture
def sample_source_table():
    return TableMetadata(
        fully_qualified_id="acme.raw.customers",
        project_or_db="acme",
        dataset_or_schema="raw",
        table_name="customers",
        columns=[
            ColumnMetadata(name="cust_id", data_type="INT64", is_primary_key=True),
            ColumnMetadata(name="email", data_type="STRING"),
        ],
        row_count=1000,
    )


def test_case_a_target_does_not_exist(sample_source_table):
    strategy, diff, info = TargetTableManager.evaluate_target_strategy(
        target_exists=False,
        existing_target_meta=None,
        source_meta=sample_source_table,
    )
    assert info["case"] == "CASE_A_TARGET_NEW"
    assert info["create_table_required"] is True
    assert strategy == LoadStrategy.INITIAL_LOAD
    assert info["can_proceed"] is True
    assert diff is None


def test_case_b_target_already_exists_compatible(sample_source_table):
    target_meta = TableMetadata(
        fully_qualified_id="DW.PUBLIC.CUSTOMERS",
        project_or_db="DW",
        dataset_or_schema="PUBLIC",
        table_name="CUSTOMERS",
        columns=[
            ColumnMetadata(name="CUST_ID", data_type="NUMBER(38,0)", is_primary_key=True),
            ColumnMetadata(name="EMAIL", data_type="VARCHAR"),
        ],
    )
    strategy, diff, info = TargetTableManager.evaluate_target_strategy(
        target_exists=True,
        existing_target_meta=target_meta,
        source_meta=sample_source_table,
    )
    assert info["case"] == "CASE_B_TARGET_EXISTS_COMPATIBLE"
    assert info["create_table_required"] is False  # REDUNDANT DDL SUPPRESSED!
    assert strategy == LoadStrategy.MERGE  # Recommends MERGE for tables with PK
    assert info["can_proceed"] is True


def test_case_b_target_already_exists_incompatible(sample_source_table):
    target_meta = TableMetadata(
        fully_qualified_id="DW.PUBLIC.CUSTOMERS",
        project_or_db="DW",
        dataset_or_schema="PUBLIC",
        table_name="CUSTOMERS",
        columns=[
            ColumnMetadata(name="CUST_ID", data_type="DATE"),  # Incompatible type
        ],
    )
    strategy, diff, info = TargetTableManager.evaluate_target_strategy(
        target_exists=True,
        existing_target_meta=target_meta,
        source_meta=sample_source_table,
    )
    assert info["case"] == "CASE_B_TARGET_EXISTS_INCOMPATIBLE"
    assert info["can_proceed"] is False
    assert diff.is_safe_to_load is False

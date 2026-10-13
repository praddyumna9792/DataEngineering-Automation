"""
Unit tests for Four-Stage SQL Generator and SQL Validator.
"""
import pytest
from core.sql_generator import SQLGenerator
from core.sql_validator import SQLValidator
from core.models import TableMetadata, ColumnMetadata, ColumnMapping, BatchDefinition, LoadStrategy


@pytest.fixture
def sample_setup():
    source_meta = TableMetadata(
        fully_qualified_id="proj.dataset.users",
        project_or_db="proj",
        dataset_or_schema="dataset",
        table_name="users",
        columns=[
            ColumnMetadata(name="user_id", data_type="INT64", is_primary_key=True),
            ColumnMetadata(name="email", data_type="STRING"),
        ],
        row_count=5000,
    )
    mappings = [
        ColumnMapping(source_column="user_id", target_column="USER_ID", source_type="INT64", target_type="NUMBER(38,0)", is_primary_key=True),
        ColumnMapping(source_column="email", target_column="EMAIL", source_type="STRING", target_type="VARCHAR", transformation_rule="LOWER"),
    ]
    batches = [
        BatchDefinition(
            batch_id="b1",
            batch_number=1,
            total_batches=1,
            partition_start=None,
            partition_end=None,
            filter_expression="1=1",
            rows_expected=5000,
        )
    ]
    return source_meta, mappings, batches


def test_sql_generator_stage1(sample_setup):
    source_meta, mappings, batches = sample_setup
    sql = SQLGenerator.generate_stage1_iceberg_export(source_meta, mappings, batches)
    assert "EXPORT DATA OPTIONS" in sql
    assert "format = 'PARQUET'" in sql
    assert "`proj.dataset.users`" in sql
    assert "LOWER(`email`)" in sql


def test_sql_generator_stage4_target_not_exists(sample_setup):
    source_meta, mappings, batches = sample_setup
    sql = SQLGenerator.generate_stage4_native_load(
        source_meta=source_meta,
        target_meta=None,
        target_fqn="DW.HIST.USERS",
        mappings=mappings,
        batches=batches,
        load_strategy=LoadStrategy.INITIAL_LOAD,
        target_exists=False,
    )
    assert "CREATE TABLE IF NOT EXISTS DW.HIST.USERS" in sql
    assert "INSERT INTO DW.HIST.USERS" in sql


def test_sql_generator_stage4_target_already_exists(sample_setup):
    source_meta, mappings, batches = sample_setup
    sql = SQLGenerator.generate_stage4_native_load(
        source_meta=source_meta,
        target_meta=None,
        target_fqn="DW.HIST.USERS",
        mappings=mappings,
        batches=batches,
        load_strategy=LoadStrategy.MERGE,
        target_exists=True,  # TARGET ALREADY EXISTS!
    )
    # MANDATORY: CREATE TABLE must NOT be generated!
    assert "CREATE TABLE IF NOT EXISTS DW.HIST.USERS" not in sql
    assert "Redundant CREATE TABLE DDL is SUPPRESSED" in sql
    assert "MERGE INTO DW.HIST.USERS" in sql


def test_sql_validator():
    safe_sql = "SELECT * FROM users WHERE id = 1;"
    res = SQLValidator.validate_sql_text(safe_sql, "test")
    assert res["is_valid"] is True
    assert len(res["errors"]) == 0

    destructive_sql = "DROP TABLE users; SELECT 1;"
    res_dest = SQLValidator.validate_sql_text(destructive_sql, "test")
    assert res_dest["is_valid"] is False
    assert any("DROP TABLE" in e for e in res_dest["errors"])

"""
Unit tests for Schema and Mapping Managers.
"""
import pytest
from core.schema_manager import SchemaManager
from core.mapping_manager import MappingManager
from core.models import ColumnMetadata, SchemaCompatibilityStatus


def test_type_mapping():
    assert SchemaManager.map_bq_to_snowflake_type("INT64") == "NUMBER(38,0)"
    assert SchemaManager.map_bq_to_snowflake_type("STRING") == "VARCHAR"
    assert SchemaManager.map_bq_to_snowflake_type("NUMERIC", 38, 9) == "NUMBER(38,9)"
    assert SchemaManager.map_bq_to_snowflake_type("TIMESTAMP") == "TIMESTAMP_NTZ"
    assert SchemaManager.map_bq_to_snowflake_type("BOOL") == "BOOLEAN"
    assert SchemaManager.map_bq_to_snowflake_type("JSON") == "VARIANT"


def test_parse_json_schema():
    json_text = """[
        {"name": "user_id", "type": "INT64", "mode": "REQUIRED", "is_primary_key": true},
        {"name": "email", "type": "STRING", "mode": "NULLABLE"}
    ]"""
    cols = SchemaManager.parse_schema_file(json_text, "schema.json")
    assert len(cols) == 2
    assert cols[0].name == "user_id"
    assert cols[0].data_type == "INT64"
    assert cols[0].is_primary_key is True
    assert cols[0].is_nullable is False
    assert cols[1].name == "email"
    assert cols[1].is_nullable is True


def test_parse_csv_mapping():
    csv_bytes = b'''source_column,target_column,source_type,target_type,transformation_rule
user_id,USER_ID,INT64,"NUMBER(38,0)",DIRECT
email_addr,EMAIL,STRING,VARCHAR(255),LOWER
'''
    mappings, val = MappingManager.parse_mapping_file(csv_bytes, "mapping.csv")
    assert val["is_valid"] is True
    assert len(mappings) == 2
    assert mappings[0].source_column == "user_id"
    assert mappings[0].target_column == "USER_ID"
    assert mappings[1].transformation_rule == "LOWER"


def test_schema_comparison_exact():
    source_cols = [
        ColumnMetadata(name="id", data_type="INT64"),
        ColumnMetadata(name="name", data_type="STRING"),
    ]
    target_cols = [
        ColumnMetadata(name="ID", data_type="NUMBER(38,0)"),
        ColumnMetadata(name="NAME", data_type="VARCHAR"),
    ]
    diff = SchemaManager.compare_schemas(source_cols, target_cols)
    assert diff.status == SchemaCompatibilityStatus.EXACT_MATCH
    assert diff.is_safe_to_load is True
    assert len(diff.missing_columns_in_target) == 0


def test_schema_comparison_incompatible_type():
    source_cols = [
        ColumnMetadata(name="id", data_type="INT64"),
    ]
    target_cols = [
        ColumnMetadata(name="ID", data_type="BOOLEAN"),  # Incompatible type
    ]
    diff = SchemaManager.compare_schemas(source_cols, target_cols)
    assert diff.status == SchemaCompatibilityStatus.INCOMPATIBLE
    assert diff.is_safe_to_load is False
    assert len(diff.mismatched_types) == 1

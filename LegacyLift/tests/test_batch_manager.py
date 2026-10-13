"""
Unit tests for Batch Manager and partitioning boundaries.
"""
import pytest
from core.batch_manager import BatchManager
from core.models import TableMetadata, ColumnMetadata


def test_partition_batches():
    source_meta = TableMetadata(
        fully_qualified_id="p.d.events",
        project_or_db="p",
        dataset_or_schema="d",
        table_name="events",
        columns=[
            ColumnMetadata(name="event_id", data_type="INT64"),
            ColumnMetadata(name="event_date", data_type="DATE", is_partition_col=True),
        ],
        row_count=2_000_000,
        partition_field="event_date",
        partition_type="DAY",
    )
    batches = BatchManager.plan_batches(source_meta, batch_size=500_000)
    assert len(batches) >= 4
    assert batches[0].batch_number == 1
    assert "event_date >=" in batches[0].filter_expression
    assert sum(b.rows_expected for b in batches) == 2_000_000


def test_single_batch_for_small_table():
    source_meta = TableMetadata(
        fully_qualified_id="p.d.small_lookup",
        project_or_db="p",
        dataset_or_schema="d",
        table_name="small_lookup",
        columns=[ColumnMetadata(name="code", data_type="STRING")],
        row_count=50,
    )
    batches = BatchManager.plan_batches(source_meta)
    assert len(batches) == 1
    assert batches[0].filter_expression == "1=1"
    assert batches[0].rows_expected == 50

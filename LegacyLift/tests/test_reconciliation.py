"""
Unit tests for Data Reconciliation Service.
"""
from core.reconciliation import ReconciliationService
from core.models import BatchDefinition, BatchStatus


def test_reconciliation_exact_match():
    batches = [
        BatchDefinition(
            batch_id="b1",
            batch_number=1,
            total_batches=2,
            partition_start="2023-01-01",
            partition_end="2023-02-01",
            filter_expression="1=1",
            status=BatchStatus.COMPLETED,
            rows_expected=500,
            rows_migrated=500,
        ),
        BatchDefinition(
            batch_id="b2",
            batch_number=2,
            total_batches=2,
            partition_start="2023-02-01",
            partition_end="2023-03-01",
            filter_expression="1=1",
            status=BatchStatus.COMPLETED,
            rows_expected=500,
            rows_migrated=500,
        ),
    ]

    report = ReconciliationService.generate_reconciliation_report(
        source_row_count=1000,
        target_row_count=1000,
        batches=batches,
        source_table_id="source.tbl",
        target_table_id="target.tbl",
    )

    assert report["is_exact_match"] is True
    assert report["parity_percentage"] == 100.0
    assert report["discrepancy"] == 0
    assert report["status"] == "VERIFIED_100_PERCENT"
    assert report["completed_batches"] == 2


def test_reconciliation_partial():
    batches = [
        BatchDefinition(
            batch_id="b1",
            batch_number=1,
            total_batches=2,
            partition_start=None,
            partition_end=None,
            filter_expression="1=1",
            status=BatchStatus.COMPLETED,
            rows_expected=500,
            rows_migrated=500,
        ),
        BatchDefinition(
            batch_id="b2",
            batch_number=2,
            total_batches=2,
            partition_start=None,
            partition_end=None,
            filter_expression="1=1",
            status=BatchStatus.FAILED,
            rows_expected=500,
            rows_migrated=0,
        ),
    ]

    report = ReconciliationService.generate_reconciliation_report(
        source_row_count=1000,
        target_row_count=500,
        batches=batches,
        source_table_id="source.tbl",
        target_table_id="target.tbl",
    )

    assert report["is_exact_match"] is False
    assert report["parity_percentage"] == 50.0
    assert report["discrepancy"] == 500
    assert report["status"] == "PARTIAL"
    assert report["failed_batches"] == 1

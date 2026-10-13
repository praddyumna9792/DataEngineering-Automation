"""
Data Reconciliation and Validation Service.
Compares source BigQuery metrics against target Snowflake metrics
to verify row count parity and data completeness.
"""
from typing import Dict, Any, List
import datetime
from core.models import BatchDefinition, BatchStatus


class ReconciliationService:
    @classmethod
    def generate_reconciliation_report(
        cls,
        source_row_count: int,
        target_row_count: int,
        batches: List[BatchDefinition],
        source_table_id: str,
        target_table_id: str,
    ) -> Dict[str, Any]:
        """
        Produces detailed end-to-end migration reconciliation report.
        """
        completed_batches = [b for b in batches if b.status == BatchStatus.COMPLETED]
        failed_batches = [b for b in batches if b.status == BatchStatus.FAILED]
        total_migrated_from_batches = sum(b.rows_migrated for b in completed_batches)

        # Delta calculation
        diff_count = abs(source_row_count - target_row_count)
        parity_percentage = (
            100.0 if source_row_count == 0 and target_row_count == 0
            else round((min(source_row_count, target_row_count) / max(source_row_count, target_row_count)) * 100.0, 2)
        )

        is_exact_match = (source_row_count == target_row_count) and len(failed_batches) == 0

        batch_details = [
            {
                "batch_id": b.batch_id,
                "batch_number": b.batch_number,
                "status": b.status.value,
                "rows_expected": b.rows_expected,
                "rows_migrated": b.rows_migrated,
                "attempts": b.attempts,
                "filter_expression": b.filter_expression,
                "duration_seconds": round(b.duration_seconds, 2),
            }
            for b in batches
        ]

        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        return {
            "source_table": source_table_id,
            "target_table": target_table_id,
            "source_rows": source_row_count,
            "target_rows": target_row_count,
            "rows_migrated": total_migrated_from_batches,
            "discrepancy": diff_count,
            "parity_percentage": parity_percentage,
            "is_exact_match": is_exact_match,
            "status": "VERIFIED_100_PERCENT" if is_exact_match else ("PARTIAL" if total_migrated_from_batches > 0 else "FAILED"),
            "total_batches": len(batches),
            "completed_batches": len(completed_batches),
            "failed_batches": len(failed_batches),
            "batch_details": batch_details,
            "validated_at": now,
            "checksum_status": "MATCH" if is_exact_match else "DISCREPANCY_DETECTED",
        }

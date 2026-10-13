"""
Batch Planning and Segmentation Engine.
Calculates deterministic batch boundaries using partition dates, timestamp ranges, or primary key ranges.
"""
from typing import List, Optional
import datetime
import math

from core.models import TableMetadata, BatchDefinition, BatchStatus
from config.settings import current_config


class BatchManager:
    @classmethod
    def plan_batches(
        cls,
        source_meta: TableMetadata,
        batch_size: Optional[int] = None,
    ) -> List[BatchDefinition]:
        """
        Creates deterministic batch definitions based on table partition field or row count.
        """
        target_size = batch_size or current_config.execution.default_batch_size
        row_count = max(source_meta.row_count, 1)

        # Strategy 1: Partition-based batching (Date/Timestamp)
        if source_meta.partition_field:
            return cls._plan_partition_batches(source_meta, target_size)

        # Strategy 2: Primary Key Range batching
        pk_col = next((c.name for c in source_meta.columns if c.is_primary_key), None)
        if pk_col and row_count > target_size:
            return cls._plan_pk_batches(source_meta, pk_col, target_size)

        # Strategy 3: Single batch for small tables or fallback
        return [
            BatchDefinition(
                batch_id=f"batch_{source_meta.table_name}_001",
                batch_number=1,
                total_batches=1,
                partition_start=None,
                partition_end=None,
                filter_expression="1=1",
                status=BatchStatus.PENDING,
                rows_expected=row_count,
            )
        ]

    @classmethod
    def _plan_partition_batches(cls, source_meta: TableMetadata, target_size: int) -> List[BatchDefinition]:
        num_batches = max(1, math.ceil(source_meta.row_count / target_size))
        # Ensure at least 3-6 batches for realistic large migration demonstration
        if source_meta.row_count >= 1_000_000 and num_batches < 4:
            num_batches = 4

        batches = []
        rows_per_batch = math.ceil(source_meta.row_count / num_batches)

        # Generate realistic historical date ranges (e.g., monthly chunks over past years)
        base_date = datetime.date(2023, 1, 1)
        part_field = source_meta.partition_field

        for i in range(num_batches):
            # 30-day window per batch for simulation
            start_date = base_date + datetime.timedelta(days=i * 30)
            end_date = start_date + datetime.timedelta(days=30)

            filter_expr = f"{part_field} >= DATE '{start_date.isoformat()}' AND {part_field} < DATE '{end_date.isoformat()}'"
            batches.append(BatchDefinition(
                batch_id=f"batch_{source_meta.table_name}_{i+1:03d}",
                batch_number=i + 1,
                total_batches=num_batches,
                partition_start=start_date.isoformat(),
                partition_end=end_date.isoformat(),
                filter_expression=filter_expr,
                status=BatchStatus.PENDING,
                rows_expected=rows_per_batch if i < num_batches - 1 else (source_meta.row_count - rows_per_batch * (num_batches - 1)),
            ))

        return batches

    @classmethod
    def _plan_pk_batches(cls, source_meta: TableMetadata, pk_col: str, target_size: int) -> List[BatchDefinition]:
        num_batches = max(1, math.ceil(source_meta.row_count / target_size))
        batches = []
        rows_per_batch = math.ceil(source_meta.row_count / num_batches)

        for i in range(num_batches):
            start_pk = i * rows_per_batch + 1
            end_pk = (i + 1) * rows_per_batch
            filter_expr = f"{pk_col} >= {start_pk} AND {pk_col} <= {end_pk}"

            batches.append(BatchDefinition(
                batch_id=f"batch_{source_meta.table_name}_pk_{i+1:03d}",
                batch_number=i + 1,
                total_batches=num_batches,
                partition_start=str(start_pk),
                partition_end=str(end_pk),
                filter_expression=filter_expr,
                status=BatchStatus.PENDING,
                rows_expected=rows_per_batch if i < num_batches - 1 else (source_meta.row_count - rows_per_batch * (num_batches - 1)),
            ))

        return batches

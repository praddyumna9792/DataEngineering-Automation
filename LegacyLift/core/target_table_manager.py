"""
Target Table Manager for enforcing mandatory Snowflake existing-table logic.
Checks target existence, evaluates schema compatibility, selects load strategy,
and prevents redundant DDL or destructive overwrites.
"""
from typing import Optional, Dict, Any, Tuple
from core.models import (
    TableMetadata,
    TargetTableStatus,
    SchemaDiff,
    SchemaCompatibilityStatus,
    LoadStrategy,
)
from core.schema_manager import SchemaManager


class TargetTableManager:
    @staticmethod
    def evaluate_target_strategy(
        target_exists: bool,
        existing_target_meta: Optional[TableMetadata],
        source_meta: TableMetadata,
        user_strategy_override: Optional[LoadStrategy] = None,
        confirm_overwrite: bool = False,
    ) -> Tuple[LoadStrategy, Optional[SchemaDiff], Dict[str, Any]]:
        """
        Determines the execution strategy and schema compatibility for the Snowflake target table.

        Returns:
            strategy: LoadStrategy (INITIAL_LOAD, APPEND, MERGE, CONTROLLED_REFRESH, RESUME)
            schema_diff: SchemaDiff if target exists, else None
            decision_info: Dict containing rationale and safety assertions
        """
        # Case A: Target does not exist
        if not target_exists or existing_target_meta is None:
            strategy = LoadStrategy.INITIAL_LOAD
            return strategy, None, {
                "case": "CASE_A_TARGET_NEW",
                "table_exists": False,
                "strategy": strategy.value,
                "create_table_required": True,
                "message": "Target table does not exist. A new table will be created during approved execution.",
                "is_destructive": False,
                "can_proceed": True,
            }

        # Case B: Target already exists
        schema_diff = SchemaManager.compare_schemas(
            source_cols=source_meta.columns,
            target_cols=existing_target_meta.columns,
        )

        # Check compatibility
        can_proceed = schema_diff.is_safe_to_load
        if not can_proceed:
            return LoadStrategy.APPEND, schema_diff, {
                "case": "CASE_B_TARGET_EXISTS_INCOMPATIBLE",
                "table_exists": True,
                "strategy": "BLOCKED",
                "create_table_required": False,
                "message": "Target table exists but has INCOMPATIBLE schema. Loading is blocked until conflicts are resolved.",
                "is_destructive": False,
                "can_proceed": False,
            }

        # Compatible existing target: determine load operation
        if user_strategy_override:
            strategy = user_strategy_override
        else:
            # Default for existing compatible table:
            # If source has primary keys, recommend MERGE to prevent duplicate ingestion
            has_pk = any(c.is_primary_key for c in source_meta.columns)
            strategy = LoadStrategy.MERGE if has_pk else LoadStrategy.APPEND

        is_destructive = strategy == LoadStrategy.CONTROLLED_REFRESH
        if is_destructive and not confirm_overwrite:
            can_proceed = False
            message = "Controlled Refresh / Overwrite requires explicit confirmation before proceeding."
        else:
            message = f"Existing table will be reused with {strategy.value} strategy. No redundant CREATE TABLE statement will be generated."

        return strategy, schema_diff, {
            "case": "CASE_B_TARGET_EXISTS_COMPATIBLE",
            "table_exists": True,
            "strategy": strategy.value,
            "create_table_required": False,
            "message": message,
            "is_destructive": is_destructive,
            "can_proceed": can_proceed,
        }

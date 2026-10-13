"""
Migration Planner Service for LegacyLift.
Assembles metadata discovery, schema reconciliation, mapping configuration,
batch planning, four-stage SQL generation, and approval management.
"""
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
import datetime
import uuid

if TYPE_CHECKING:
    from persistence.repositories import PlanRepository

from core.models import (
    MigrationPlan,
    TableMetadata,
    TargetTableStatus,
    LoadStrategy,
    ColumnMapping,
    BatchDefinition,
)
from core.metadata_discovery import MetadataDiscoveryService
from core.schema_manager import SchemaManager
from core.mapping_manager import MappingManager
from core.target_table_manager import TargetTableManager
from core.batch_manager import BatchManager
from core.sql_generator import SQLGenerator
from core.sql_validator import SQLValidator


class MigrationPlanner:
    def __init__(
        self,
        discovery_service: Optional[MetadataDiscoveryService] = None,
        plan_repo: Optional["PlanRepository"] = None,
    ):
        self.discovery = discovery_service or MetadataDiscoveryService()
        if plan_repo is None:
            from persistence.repositories import PlanRepository
            plan_repo = PlanRepository()
        self.plan_repo = plan_repo

    def create_plan(
        self,
        source_table_name: str,
        target_table_name: str,
        source_scope: Optional[str] = None,
        target_scope: Optional[str] = None,
        uploaded_mapping_bytes: Optional[bytes] = None,
        mapping_filename: Optional[str] = None,
        uploaded_schema_text: Optional[str] = None,
        schema_filename: Optional[str] = None,
        load_strategy_override: Optional[LoadStrategy] = None,
        confirm_overwrite: bool = False,
    ) -> Tuple[Optional[MigrationPlan], Dict[str, Any]]:
        """
        Main entry point for generating a complete MigrationPlan from 2 mandatory inputs
        plus optional mapping/schema uploads.
        """
        diagnostics: Dict[str, Any] = {
            "source_status": "PENDING",
            "target_status": "PENDING",
            "errors": [],
            "warnings": [],
        }

        # 1. Resolve Source Table
        src_status, src_matches, source_meta = self.discovery.resolve_source_table(
            table_name=source_table_name,
            search_scope=source_scope,
        )
        diagnostics["source_status"] = src_status
        diagnostics["source_matches"] = [m.fully_qualified_id for m in src_matches]

        if src_status == "NOT_FOUND":
            diagnostics["errors"].append(f"BigQuery source table '{source_table_name}' was not found in authorized datasets.")
            return None, diagnostics
        elif src_status == "AMBIGUOUS":
            diagnostics["errors"].append(
                f"Source table name '{source_table_name}' is ambiguous ({len(src_matches)} matches found). "
                f"Please specify the exact dataset or select from candidates: {[m.fully_qualified_id for m in src_matches]}"
            )
            return None, diagnostics

        # 2. Resolve Target Table (Mandatory Snowflake Existing-Table Check)
        tgt_status, tgt_matches, target_meta, target_fqn = self.discovery.resolve_target_table(
            table_name=target_table_name,
            search_scope=target_scope,
        )
        diagnostics["target_status"] = tgt_status.value
        diagnostics["target_matches"] = [m.fully_qualified_id for m in tgt_matches]
        diagnostics["target_fqn"] = target_fqn

        if tgt_status == TargetTableStatus.AMBIGUOUS:
            diagnostics["errors"].append(
                f"Snowflake target table '{target_table_name}' matches multiple existing objects. "
                f"Please select from: {[m.fully_qualified_id for m in tgt_matches]}"
            )
            return None, diagnostics

        target_exists = (tgt_status == TargetTableStatus.EXISTS and target_meta is not None)

        # 3. Handle Schema Upload (if provided)
        if uploaded_schema_text and schema_filename:
            parsed_cols = SchemaManager.parse_schema_file(uploaded_schema_text, schema_filename)
            if parsed_cols:
                # Merge or override source column definitions
                diagnostics["warnings"].append(f"Parsed {len(parsed_cols)} column definitions from uploaded schema file.")

        # 4. Handle Column Mappings (Upload or Default Generation)
        mappings: List[ColumnMapping] = []
        if uploaded_mapping_bytes and mapping_filename:
            parsed_mappings, mapping_val = MappingManager.parse_mapping_file(uploaded_mapping_bytes, mapping_filename)
            diagnostics["mapping_validation"] = mapping_val
            if not mapping_val["is_valid"]:
                diagnostics["errors"].extend(mapping_val["errors"])
                return None, diagnostics
            mappings = parsed_mappings
            diagnostics["warnings"].extend(mapping_val.get("warnings", []))
        else:
            mappings = MappingManager.generate_default_mappings(
                source_cols=source_meta.columns,
                target_cols=target_meta.columns if target_meta else None,
            )

        # 5. Evaluate Target Strategy & Schema Reconciliation
        strategy, schema_diff, strategy_info = TargetTableManager.evaluate_target_strategy(
            target_exists=target_exists,
            existing_target_meta=target_meta,
            source_meta=source_meta,
            user_strategy_override=load_strategy_override,
            confirm_overwrite=confirm_overwrite,
        )
        diagnostics["strategy_info"] = strategy_info

        if not strategy_info["can_proceed"]:
            diagnostics["errors"].append(strategy_info["message"])
            return None, diagnostics

        # 6. Batch Planning
        batches = BatchManager.plan_batches(source_meta)

        # 7. Generate 4-Stage SQL
        stages_sql = SQLGenerator.generate_all_stages(
            source_meta=source_meta,
            target_meta=target_meta,
            target_fqn=target_fqn,
            mappings=mappings,
            batches=batches,
            load_strategy=strategy,
            target_exists=target_exists,
        )

        # 8. Readiness Report
        readiness = self.discovery.evaluate_readiness(
            source_meta=source_meta,
            target_meta=target_meta,
            target_fqn=target_fqn,
        )

        # 9. Create Plan Model
        plan_id = f"plan_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        plan = MigrationPlan(
            plan_id=plan_id,
            source_table_id=source_meta.fully_qualified_id,
            target_table_id=target_fqn,
            source_metadata=source_meta,
            target_metadata=target_meta,
            target_exists=target_exists,
            schema_diff=schema_diff,
            mappings=mappings,
            stage1_sql=stages_sql["stage1"],
            stage2_sql=stages_sql["stage2"],
            stage3_sql=stages_sql["stage3"],
            stage4_sql=stages_sql["stage4"],
            batches=batches,
            readiness_report=readiness,
            load_strategy=strategy,
            is_approved=False,
        )

        # Persist Plan to SQLite
        self.plan_repo.save_plan(plan)
        return plan, diagnostics

    def update_plan_sql(self, plan: MigrationPlan, stage_key: str, new_sql: str) -> MigrationPlan:
        """
        Updates SQL for a stage.
        MANDATORY: Editing the SQL after approval invalidates the previous approval!
        """
        if stage_key == "stage1":
            plan.stage1_sql = new_sql
        elif stage_key == "stage2":
            plan.stage2_sql = new_sql
        elif stage_key == "stage3":
            plan.stage3_sql = new_sql
        elif stage_key == "stage4":
            plan.stage4_sql = new_sql

        plan.sql_modified_since_approval = True
        plan.is_approved = False
        plan.approved_at = None
        plan.approved_by = None
        plan.version += 1

        self.plan_repo.save_plan(plan)
        return plan

    def approve_plan(self, plan: MigrationPlan, approved_by: str = "Lead Data Architect") -> Tuple[bool, List[str]]:
        """
        Explicit approval before execution.
        Validates all SQL stages before allowing approval.
        """
        validation = SQLValidator.validate_all_stages({
            "stage1": plan.stage1_sql,
            "stage2": plan.stage2_sql,
            "stage3": plan.stage3_sql,
            "stage4": plan.stage4_sql,
        })

        if not validation["is_valid"]:
            return False, validation["errors"]

        plan.is_approved = True
        plan.approved_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        plan.approved_by = approved_by
        plan.sql_modified_since_approval = False

        self.plan_repo.save_plan(plan)
        return True, []

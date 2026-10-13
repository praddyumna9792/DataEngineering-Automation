"""
Data models for LegacyLift core domain.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
import datetime
import uuid


class TargetTableStatus(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    EXISTS = "EXISTS"
    AMBIGUOUS = "AMBIGUOUS"
    ERROR = "ERROR"


class SchemaCompatibilityStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"


class LoadStrategy(str, Enum):
    INITIAL_LOAD = "INITIAL_LOAD"
    APPEND = "APPEND"
    MERGE = "MERGE"
    CONTROLLED_REFRESH = "CONTROLLED_REFRESH"
    RESUME = "RESUME"


class BatchStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


@dataclass
class ColumnMetadata:
    name: str
    data_type: str
    is_nullable: bool = True
    is_partition_col: bool = False
    is_clustering_col: bool = False
    is_primary_key: bool = False
    precision: Optional[int] = None
    scale: Optional[int] = None
    comment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "is_nullable": self.is_nullable,
            "is_partition_col": self.is_partition_col,
            "is_clustering_col": self.is_clustering_col,
            "is_primary_key": self.is_primary_key,
            "precision": self.precision,
            "scale": self.scale,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColumnMetadata":
        return cls(**data)


@dataclass
class TableMetadata:
    fully_qualified_id: str  # e.g., "acme-analytics-prod.legacy_dw.customer_history"
    project_or_db: str
    dataset_or_schema: str
    table_name: str
    columns: List[ColumnMetadata] = field(default_factory=list)
    row_count: int = 0
    size_bytes: int = 0
    partition_field: Optional[str] = None
    partition_type: Optional[str] = None  # e.g., "DAY", "MONTH", "INTEGER_RANGE"
    clustering_fields: List[str] = field(default_factory=list)
    location: str = "US"
    description: Optional[str] = None

    def get_column(self, col_name: str) -> Optional[ColumnMetadata]:
        for col in self.columns:
            if col.name.lower() == col_name.lower():
                return col
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fully_qualified_id": self.fully_qualified_id,
            "project_or_db": self.project_or_db,
            "dataset_or_schema": self.dataset_or_schema,
            "table_name": self.table_name,
            "columns": [c.to_dict() for c in self.columns],
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "partition_field": self.partition_field,
            "partition_type": self.partition_type,
            "clustering_fields": self.clustering_fields,
            "location": self.location,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TableMetadata":
        cols_data = data.pop("columns", [])
        cols = [ColumnMetadata.from_dict(c) for c in cols_data]
        return cls(columns=cols, **data)


@dataclass
class ColumnMapping:
    source_column: str
    target_column: str
    source_type: str
    target_type: str
    transformation_rule: str = "DIRECT"  # DIRECT, UPPER, LOWER, TRIM, COALESCE, CAST, CUSTOM
    custom_expression: Optional[str] = None
    is_primary_key: bool = False
    is_nullable: bool = True
    default_value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_column": self.source_column,
            "target_column": self.target_column,
            "source_type": self.source_type,
            "target_type": self.target_type,
            "transformation_rule": self.transformation_rule,
            "custom_expression": self.custom_expression,
            "is_primary_key": self.is_primary_key,
            "is_nullable": self.is_nullable,
            "default_value": self.default_value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColumnMapping":
        return cls(**data)


@dataclass
class SchemaDiff:
    status: SchemaCompatibilityStatus
    missing_columns_in_target: List[str] = field(default_factory=list)
    extra_columns_in_target: List[str] = field(default_factory=list)
    mismatched_types: List[Dict[str, Any]] = field(default_factory=list)
    compatibility_notes: List[str] = field(default_factory=list)
    is_safe_to_load: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "missing_columns_in_target": self.missing_columns_in_target,
            "extra_columns_in_target": self.extra_columns_in_target,
            "mismatched_types": self.mismatched_types,
            "compatibility_notes": self.compatibility_notes,
            "is_safe_to_load": self.is_safe_to_load,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchemaDiff":
        status = SchemaCompatibilityStatus(data["status"])
        return cls(
            status=status,
            missing_columns_in_target=data.get("missing_columns_in_target", []),
            extra_columns_in_target=data.get("extra_columns_in_target", []),
            mismatched_types=data.get("mismatched_types", []),
            compatibility_notes=data.get("compatibility_notes", []),
            is_safe_to_load=data.get("is_safe_to_load", True),
        )


@dataclass
class BatchDefinition:
    batch_id: str
    batch_number: int
    total_batches: int
    partition_start: Optional[str]
    partition_end: Optional[str]
    filter_expression: str
    status: BatchStatus = BatchStatus.PENDING
    rows_expected: int = 0
    rows_migrated: int = 0
    attempts: int = 0
    last_error: Optional[str] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "batch_number": self.batch_number,
            "total_batches": self.total_batches,
            "partition_start": self.partition_start,
            "partition_end": self.partition_end,
            "filter_expression": self.filter_expression,
            "status": self.status.value,
            "rows_expected": self.rows_expected,
            "rows_migrated": self.rows_migrated,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchDefinition":
        status = BatchStatus(data.get("status", "PENDING"))
        data_copy = dict(data)
        data_copy["status"] = status
        return cls(**data_copy)


@dataclass
class MigrationReadinessReport:
    is_ready: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    estimated_duration_minutes: float = 0.0
    architecture_decision: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_ready": self.is_ready,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "architecture_decision": self.architecture_decision,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationReadinessReport":
        return cls(**data)


@dataclass
class MigrationPlan:
    plan_id: str
    source_table_id: str
    target_table_id: str
    source_metadata: TableMetadata
    target_metadata: Optional[TableMetadata]
    target_exists: bool
    schema_diff: Optional[SchemaDiff]
    mappings: List[ColumnMapping]
    stage1_sql: str  # BQ -> Iceberg in GCS
    stage2_sql: str  # Schema DDL
    stage3_sql: str  # Snowflake Iceberg integration / External volume
    stage4_sql: str  # Snowflake Native Table Load (conditional DDL + DML)
    batches: List[BatchDefinition]
    readiness_report: MigrationReadinessReport
    load_strategy: LoadStrategy = LoadStrategy.INITIAL_LOAD
    is_approved: bool = False
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    sql_modified_since_approval: bool = False
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source_table_id": self.source_table_id,
            "target_table_id": self.target_table_id,
            "source_metadata": self.source_metadata.to_dict(),
            "target_metadata": self.target_metadata.to_dict() if self.target_metadata else None,
            "target_exists": self.target_exists,
            "schema_diff": self.schema_diff.to_dict() if self.schema_diff else None,
            "mappings": [m.to_dict() for m in self.mappings],
            "stage1_sql": self.stage1_sql,
            "stage2_sql": self.stage2_sql,
            "stage3_sql": self.stage3_sql,
            "stage4_sql": self.stage4_sql,
            "batches": [b.to_dict() for b in self.batches],
            "readiness_report": self.readiness_report.to_dict(),
            "load_strategy": self.load_strategy.value,
            "is_approved": self.is_approved,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "sql_modified_since_approval": self.sql_modified_since_approval,
            "version": self.version,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationPlan":
        source_meta = TableMetadata.from_dict(data["source_metadata"])
        target_meta = TableMetadata.from_dict(data["target_metadata"]) if data.get("target_metadata") else None
        schema_diff = SchemaDiff.from_dict(data["schema_diff"]) if data.get("schema_diff") else None
        mappings = [ColumnMapping.from_dict(m) for m in data.get("mappings", [])]
        batches = [BatchDefinition.from_dict(b) for b in data.get("batches", [])]
        readiness = MigrationReadinessReport.from_dict(data["readiness_report"])
        strategy = LoadStrategy(data.get("load_strategy", "INITIAL_LOAD"))

        return cls(
            plan_id=data["plan_id"],
            source_table_id=data["source_table_id"],
            target_table_id=data["target_table_id"],
            source_metadata=source_meta,
            target_metadata=target_meta,
            target_exists=data.get("target_exists", False),
            schema_diff=schema_diff,
            mappings=mappings,
            stage1_sql=data["stage1_sql"],
            stage2_sql=data["stage2_sql"],
            stage3_sql=data["stage3_sql"],
            stage4_sql=data["stage4_sql"],
            batches=batches,
            readiness_report=readiness,
            load_strategy=strategy,
            is_approved=data.get("is_approved", False),
            approved_at=data.get("approved_at"),
            approved_by=data.get("approved_by"),
            sql_modified_since_approval=data.get("sql_modified_since_approval", False),
            version=data.get("version", 1),
            created_at=data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )


@dataclass
class MigrationRun:
    run_id: str
    plan_id: str
    source_table_id: str
    target_table_id: str
    mode: str = "SIMULATION"
    status: RunStatus = RunStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_stage: str = "Stage 1 — Iceberg Export"
    stage_statuses: Dict[str, str] = field(default_factory=lambda: {
        "stage1": "PENDING",
        "stage2": "PENDING",
        "stage3": "PENDING",
        "stage4": "PENDING",
    })
    batches: List[BatchDefinition] = field(default_factory=list)
    total_rows_expected: int = 0
    total_rows_migrated: int = 0
    logs: List[str] = field(default_factory=list)
    reconciliation_report: Optional[Dict[str, Any]] = None
    error_summary: Optional[str] = None

    def log(self, message: str) -> None:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.logs.append(f"[{timestamp}] {message}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "source_table_id": self.source_table_id,
            "target_table_id": self.target_table_id,
            "mode": self.mode,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_stage": self.current_stage,
            "stage_statuses": self.stage_statuses,
            "batches": [b.to_dict() for b in self.batches],
            "total_rows_expected": self.total_rows_expected,
            "total_rows_migrated": self.total_rows_migrated,
            "logs": self.logs,
            "reconciliation_report": self.reconciliation_report,
            "error_summary": self.error_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationRun":
        status = RunStatus(data.get("status", "PENDING"))
        batches = [BatchDefinition.from_dict(b) for b in data.get("batches", [])]
        data_copy = dict(data)
        data_copy["status"] = status
        data_copy["batches"] = batches
        return cls(**data_copy)

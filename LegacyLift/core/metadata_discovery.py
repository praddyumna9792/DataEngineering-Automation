"""
Metadata Discovery Service for BigQuery and Snowflake.
Resolves table names, handles ambiguity, retrieves partition/clustering metadata,
and generates migration readiness reports.
"""
from typing import Tuple, List, Optional, Dict, Any
from core.models import (
    TableMetadata,
    TargetTableStatus,
    MigrationReadinessReport,
)
from connectors.bigquery_connector import BigQueryConnector
from connectors.snowflake_connector import SnowflakeConnector
from connectors.gcs_connector import GCSConnector
from config.settings import current_config


class MetadataDiscoveryService:
    def __init__(
        self,
        bq_connector: Optional[BigQueryConnector] = None,
        sf_connector: Optional[SnowflakeConnector] = None,
        gcs_connector: Optional[GCSConnector] = None,
    ):
        self.bq = bq_connector or BigQueryConnector()
        self.sf = sf_connector or SnowflakeConnector()
        self.gcs = gcs_connector or GCSConnector()

    def resolve_source_table(
        self,
        table_name: str,
        search_scope: Optional[str] = None,
    ) -> Tuple[str, List[TableMetadata], Optional[TableMetadata]]:
        """
        Resolves BigQuery source table name.
        Returns:
            status: "FOUND", "AMBIGUOUS", "NOT_FOUND"
            matches: List[TableMetadata]
            selected: Optional[TableMetadata] (set only when exactly 1 match or explicitly scoped)
        """
        clean_name = table_name.strip()
        if not clean_name:
            return "NOT_FOUND", [], None

        # Check if user already entered a fully qualified name (project.dataset.table)
        if clean_name.count(".") == 2:
            meta = self.bq.get_table_metadata(clean_name)
            if meta:
                return "FOUND", [meta], meta
            return "NOT_FOUND", [], None

        matches = self.bq.search_tables(clean_name, search_scope=search_scope)
        if len(matches) == 1:
            return "FOUND", matches, matches[0]
        elif len(matches) > 1:
            return "AMBIGUOUS", matches, None
        else:
            return "NOT_FOUND", [], None

    def resolve_target_table(
        self,
        table_name: str,
        search_scope: Optional[str] = None,
    ) -> Tuple[TargetTableStatus, List[TableMetadata], Optional[TableMetadata], str]:
        """
        Resolves Snowflake target table name.
        Returns:
            status: TargetTableStatus (EXISTS, NOT_FOUND, AMBIGUOUS)
            matches: List[TableMetadata]
            selected: Optional[TableMetadata] (if exists)
            resolved_fqn: Fully qualified name to use
        """
        clean_name = table_name.strip().upper()
        if not clean_name:
            return TargetTableStatus.NOT_FOUND, [], None, ""

        default_fqn = (
            f"{current_config.snowflake.default_database}."
            f"{current_config.snowflake.default_schema}."
            f"{clean_name.split('.')[-1]}"
        )

        if clean_name.count(".") == 2:
            meta = self.sf.get_table_metadata(clean_name)
            if meta:
                return TargetTableStatus.EXISTS, [meta], meta, clean_name
            return TargetTableStatus.NOT_FOUND, [], None, clean_name

        matches = self.sf.search_tables(clean_name, search_scope=search_scope)
        if len(matches) == 1:
            return TargetTableStatus.EXISTS, matches, matches[0], matches[0].fully_qualified_id
        elif len(matches) > 1:
            return TargetTableStatus.AMBIGUOUS, matches, None, default_fqn
        else:
            # Does not exist -> will be created in default DB and Schema
            return TargetTableStatus.NOT_FOUND, [], None, default_fqn

    def evaluate_readiness(
        self,
        source_meta: Optional[TableMetadata],
        target_meta: Optional[TableMetadata],
        target_fqn: str,
    ) -> MigrationReadinessReport:
        """Generates comprehensive migration readiness report."""
        checks = []
        warnings = []
        errors = []

        # 1. BigQuery Source check
        if source_meta:
            checks.append({
                "component": "BigQuery Source Table",
                "status": "PASS",
                "details": f"Resolved {source_meta.fully_qualified_id} ({source_meta.row_count:,} rows, {len(source_meta.columns)} cols)",
            })
            if source_meta.row_count > 10_000_000 and not source_meta.partition_field:
                warnings.append("High volume source table (>10M rows) has no partition field. Batching will use primary key range.")
        else:
            checks.append({
                "component": "BigQuery Source Table",
                "status": "FAIL",
                "details": "Source table not resolved.",
            })
            errors.append("Valid BigQuery source table is required.")

        # 2. Snowflake Target check
        if target_meta:
            checks.append({
                "component": "Snowflake Target Table",
                "status": "INFO",
                "details": f"Target table already exists: {target_meta.fully_qualified_id}. Redundant DDL will be suppressed.",
            })
        else:
            checks.append({
                "component": "Snowflake Target Table",
                "status": "PASS",
                "details": f"Target table {target_fqn} does not exist. CREATE TABLE DDL will be generated.",
            })

        # 3. GCS Bucket Access
        bucket_check = self.gcs.check_bucket_access(current_config.gcp.gcs_bucket)
        if bucket_check.get("success"):
            checks.append({
                "component": "GCS Storage Staging",
                "status": "PASS",
                "details": f"Verified access to {current_config.gcp.gcs_bucket}",
            })
        else:
            checks.append({
                "component": "GCS Storage Staging",
                "status": "WARN",
                "details": bucket_check.get("message", "GCS check warning"),
            })
            warnings.append(f"GCS bucket check: {bucket_check.get('message')}")

        # 4. Snowflake Integration Check
        sf_check = self.sf.test_connection()
        if sf_check.get("success"):
            checks.append({
                "component": "Snowflake Warehouse & Integrations",
                "status": "PASS",
                "details": f"Warehouse: {current_config.snowflake.warehouse}, External Volume: {current_config.snowflake.external_volume}",
            })
        else:
            checks.append({
                "component": "Snowflake Warehouse & Integrations",
                "status": "WARN",
                "details": sf_check.get("message"),
            })

        # Cost & Duration Estimation
        row_count = source_meta.row_count if source_meta else 0
        size_gb = (source_meta.size_bytes / (1024 ** 3)) if source_meta and source_meta.size_bytes else 0.5
        est_cost = max(0.50, round(size_gb * 0.05 + 0.20, 2))  # $0.05 per GB processing + warehouse credit
        est_duration = max(1.0, round((row_count / 1_000_000) * 2.5 + 1.0, 1))

        is_ready = len(errors) == 0

        arch_decision = "BigQuery -> Apache Iceberg (GCS) -> Snowflake External Volume -> Snowflake Native Table"

        return MigrationReadinessReport(
            is_ready=is_ready,
            checks=checks,
            warnings=warnings,
            errors=errors,
            estimated_cost_usd=est_cost,
            estimated_duration_minutes=est_duration,
            architecture_decision=arch_decision,
        )

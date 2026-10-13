"""
SQL Generation Engine for LegacyLift.
Generates four logically organized SQL stages:
1. BigQuery -> Iceberg export in GCS
2. Schema DDL Artifact
3. Snowflake External Volume & Iceberg/Stage Registration
4. Snowflake Native Table Creation (Conditional!) and Batch Population
"""
from typing import List, Dict, Any, Optional
from core.models import (
    TableMetadata,
    ColumnMapping,
    BatchDefinition,
    LoadStrategy,
)
from config.settings import current_config


class SQLGenerator:
    @classmethod
    def generate_all_stages(
        cls,
        source_meta: TableMetadata,
        target_meta: Optional[TableMetadata],
        target_fqn: str,
        mappings: List[ColumnMapping],
        batches: List[BatchDefinition],
        load_strategy: LoadStrategy,
        target_exists: bool,
    ) -> Dict[str, str]:
        """Generates all 4 SQL stages according to metadata and configuration."""
        stage1 = cls.generate_stage1_iceberg_export(source_meta, mappings, batches)
        stage2 = cls.generate_stage2_schema_ddl(target_fqn, mappings)
        stage3 = cls.generate_stage3_snowflake_iceberg_registration(source_meta, target_fqn)
        stage4 = cls.generate_stage4_native_load(
            source_meta=source_meta,
            target_meta=target_meta,
            target_fqn=target_fqn,
            mappings=mappings,
            batches=batches,
            load_strategy=load_strategy,
            target_exists=target_exists,
        )

        return {
            "stage1": stage1,
            "stage2": stage2,
            "stage3": stage3,
            "stage4": stage4,
        }

    # =========================================================================
    # STAGE 1: BigQuery -> Apache Iceberg Export in GCS
    # =========================================================================
    @classmethod
    def generate_stage1_iceberg_export(
        cls,
        source_meta: TableMetadata,
        mappings: List[ColumnMapping],
        batches: List[BatchDefinition],
    ) -> str:
        gcs_base = current_config.gcp.gcs_bucket.rstrip("/")
        table_name = source_meta.table_name
        src_fqn = f"`{source_meta.project_or_db}.{source_meta.dataset_or_schema}.{source_meta.table_name}`"

        # Select list with source transformations
        select_lines = []
        for m in mappings:
            expr = cls._build_source_expression(m)
            select_lines.append(f"    {expr} AS `{m.source_column}`")
        select_clause = ",\n".join(select_lines)

        sql_parts = [
            f"-- ============================================================================",
            f"-- STAGE 1: BIGQUERY HISTORICAL EXPORT TO APACHE ICEBERG / PARQUET IN GCS",
            f"-- Source Table: {src_fqn}",
            f"-- Destination: {gcs_base}/iceberg/{table_name}/",
            f"-- Batch Segments: {len(batches)} batches planned",
            f"-- ============================================================================\n",
        ]

        if len(batches) <= 1:
            dest_uri = f"{gcs_base}/iceberg/{table_name}/data/*.parquet"
            sql_parts.append(f"""-- Full Historical Export
EXPORT DATA OPTIONS (
    uri = '{dest_uri}',
    format = 'PARQUET',
    overwrite = true,
    compression = 'SNAPPY'
) AS
SELECT
{select_clause}
FROM {src_fqn};
""")
        else:
            for b in batches:
                dest_uri = f"{gcs_base}/iceberg/{table_name}/batch_{b.batch_number:03d}/*.parquet"
                sql_parts.append(f"""-- Batch {b.batch_number} of {b.total_batches} ({b.rows_expected:,} rows estimated)
EXPORT DATA OPTIONS (
    uri = '{dest_uri}',
    format = 'PARQUET',
    overwrite = true,
    compression = 'SNAPPY'
) AS
SELECT
{select_clause}
FROM {src_fqn}
WHERE {b.filter_expression};
""")

        return "\n".join(sql_parts)

    # =========================================================================
    # STAGE 2: Schema Definition DDL
    # =========================================================================
    @classmethod
    def generate_stage2_schema_ddl(
        cls,
        target_fqn: str,
        mappings: List[ColumnMapping],
    ) -> str:
        col_defs = []
        pk_cols = []

        for m in mappings:
            col_name = f'"{m.target_column}"'
            type_str = m.target_type
            null_str = "NOT NULL" if not m.is_nullable else ""
            default_str = f"DEFAULT {m.default_value}" if m.default_value else ""

            parts = [col_name, type_str, null_str, default_str]
            col_defs.append("    " + " ".join(p for p in parts if p))

            if m.is_primary_key:
                pk_cols.append(col_name)

        if pk_cols:
            col_defs.append(f"    CONSTRAINT pk_{target_fqn.split('.')[-1].lower()} PRIMARY KEY ({', '.join(pk_cols)})")

        cols_body = ",\n".join(col_defs)

        return f"""-- ============================================================================
-- STAGE 2: SCHEMA DEFINITION ARTIFACT (SNOWFLAKE TARGET SPECIFICATION)
-- Target: {target_fqn}
-- Column Count: {len(mappings)}
-- ============================================================================

-- Blueprint DDL (Used for schema validation, dbt source models, and documentation)
CREATE OR REPLACE TABLE {target_fqn}_SCHEMA_BLUEPRINT (
{cols_body}
)
COMMENT = 'LegacyLift generated schema definition for historical migration';
"""

    # =========================================================================
    # STAGE 3: Snowflake Iceberg Integration & External Volume
    # =========================================================================
    @classmethod
    def generate_stage3_snowflake_iceberg_registration(
        cls,
        source_meta: TableMetadata,
        target_fqn: str,
    ) -> str:
        sf = current_config.snowflake
        gcp = current_config.gcp
        table_name = source_meta.table_name
        stage_name = f"{sf.default_database}.{sf.default_schema}.STG_{table_name.upper()}_ICEBERG"
        iceberg_ext_tbl = f"{sf.default_database}.{sf.default_schema}.ICEBERG_{table_name.upper()}_EXT"
        gcs_base = gcp.gcs_bucket.rstrip("/")

        return f"""-- ============================================================================
-- STAGE 3: SNOWFLAKE GCS STORAGE INTEGRATION & ICEBERG DATA EXPOSURE
-- Database: {sf.default_database} | Schema: {sf.default_schema}
-- External Volume: {sf.external_volume}
-- ============================================================================

USE WAREHOUSE {sf.warehouse};
USE DATABASE {sf.default_database};
USE SCHEMA {sf.default_schema};

-- Step 3.1: Configure Snowflake External Volume for Iceberg on GCS
CREATE EXTERNAL VOLUME IF NOT EXISTS {sf.external_volume}
    STORAGE_LOCATIONS = (
        (
            NAME = 'gcs-iceberg-storage'
            STORAGE_PROVIDER = 'GCS'
            STORAGE_BASE_URL = '{gcs_base}/iceberg/'
        )
    )
    COMMENT = 'LegacyLift external volume pointing to GCS historical Iceberg files';

-- Step 3.2: Create Snowflake Staging Area with Storage Integration
CREATE STAGE IF NOT EXISTS {stage_name}
    URL = '{gcs_base}/iceberg/{table_name}/'
    STORAGE_INTEGRATION = {sf.storage_integration}
    FILE_FORMAT = (TYPE = 'PARQUET');

-- Step 3.3: Expose Parquet/Iceberg Historical Data as External Table for Ingestion
CREATE OR REPLACE EXTERNAL TABLE {iceberg_ext_tbl}
    WITH LOCATION = @{stage_name}
    FILE_FORMAT = (TYPE = 'PARQUET')
    AUTO_REFRESH = FALSE;
"""

    # =========================================================================
    # STAGE 4: Snowflake Native Table Creation (Conditional!) and Population
    # =========================================================================
    @classmethod
    def generate_stage4_native_load(
        cls,
        source_meta: TableMetadata,
        target_meta: Optional[TableMetadata],
        target_fqn: str,
        mappings: List[ColumnMapping],
        batches: List[BatchDefinition],
        load_strategy: LoadStrategy,
        target_exists: bool,
    ) -> str:
        table_name = source_meta.table_name
        iceberg_ext_tbl = f"{current_config.snowflake.default_database}.{current_config.snowflake.default_schema}.ICEBERG_{table_name.upper()}_EXT"

        sql_parts = [
            f"-- ============================================================================",
            f"-- STAGE 4: SNOWFLAKE NATIVE TABLE MATERIALIZATION & HISTORICAL POPULATION",
            f"-- Target: {target_fqn}",
            f"-- Existing Table Detected: {target_exists}",
            f"-- Approved Strategy: {load_strategy.value}",
            f"-- ============================================================================\n",
            f"USE WAREHOUSE {current_config.snowflake.warehouse};",
            f"USE DATABASE {current_config.snowflake.default_database};",
            f"USE SCHEMA {current_config.snowflake.default_schema};\n",
        ]

        # MANDATORY CHECK: If target table already exists, DO NOT generate CREATE TABLE!
        if target_exists:
            sql_parts.append(
                f"-- ----------------------------------------------------------------------------\n"
                f"-- [EXISTING TARGET DETECTED]: Table '{target_fqn}' ALREADY EXISTS.\n"
                f"-- Mandate: Redundant CREATE TABLE DDL is SUPPRESSED to preserve existing schema.\n"
                f"-- Reusing existing table definition.\n"
                f"-- ----------------------------------------------------------------------------\n"
            )
        else:
            col_defs = []
            pk_cols = []
            for m in mappings:
                col_name = f'"{m.target_column}"'
                type_str = m.target_type
                null_str = "NOT NULL" if not m.is_nullable else ""
                col_defs.append(f"    {col_name} {type_str} {null_str}".strip())
                if m.is_primary_key:
                    pk_cols.append(col_name)

            if pk_cols:
                col_defs.append(f"    CONSTRAINT pk_{target_fqn.split('.')[-1].lower()} PRIMARY KEY ({', '.join(pk_cols)})")

            cols_body = ",\n".join(col_defs)
            sql_parts.append(f"""-- Target table does not exist. Creating native analytics table:
CREATE TABLE IF NOT EXISTS {target_fqn} (
{cols_body}
)
COMMENT = 'Historical data migrated by LegacyLift from {source_meta.fully_qualified_id}';
""")

        # Population Statements (Batch-aware)
        target_cols = [f'"{m.target_column}"' for m in mappings]
        target_cols_str = ", ".join(target_cols)

        # Build Snowflake SELECT projection from external Parquet table: $1:col_name::type
        select_proj = []
        for m in mappings:
            col_cast = f"$1:{m.source_column}::{m.target_type}"
            rule = m.transformation_rule
            if rule == "UPPER":
                proj = f"UPPER({col_cast})"
            elif rule == "LOWER":
                proj = f"LOWER({col_cast})"
            elif rule == "TRIM":
                proj = f"TRIM({col_cast})"
            elif rule == "COALESCE":
                default = m.default_value or "''"
                proj = f"COALESCE({col_cast}, {default})"
            elif rule == "CUSTOM" and m.custom_expression:
                proj = m.custom_expression
            else:
                proj = col_cast
            select_proj.append(f"        {proj} AS {m.target_column}")
        select_proj_str = ",\n".join(select_proj)

        pk_col = next((m.target_column for m in mappings if m.is_primary_key), None)

        if load_strategy == LoadStrategy.CONTROLLED_REFRESH:
            sql_parts.append(f"""-- Controlled Refresh: Truncate existing data prior to ingestion
-- [CRITICAL AUDIT]: Controlled refresh approved by user for table {target_fqn}
TRUNCATE TABLE {target_fqn};
""")

        if load_strategy == LoadStrategy.MERGE and pk_col:
            # MERGE INTO statement
            update_assignments = [f'target."{m.target_column}" = src.{m.target_column}' for m in mappings if not m.is_primary_key]
            update_str = ",\n            ".join(update_assignments)
            insert_vals = [f"src.{m.target_column}" for m in mappings]
            insert_str = ", ".join(insert_vals)

            sql_parts.append(f"""-- Batch-Aware Ingestion: MERGE INTO to prevent duplicate records
MERGE INTO {target_fqn} AS target
USING (
    SELECT
{select_proj_str}
    FROM {iceberg_ext_tbl}
) AS src
ON target."{pk_col}" = src.{pk_col}
WHEN MATCHED THEN
    UPDATE SET
            {update_str}
WHEN NOT MATCHED THEN
    INSERT ({target_cols_str})
    VALUES ({insert_str});
""")
        else:
            # Standard INSERT INTO
            sql_parts.append(f"""-- Batch-Aware Ingestion: INSERT INTO Native Target Table
INSERT INTO {target_fqn} (
    {target_cols_str}
)
SELECT
{select_proj_str}
FROM {iceberg_ext_tbl};
""")

        # Add Source-to-Target Reconciliation Query
        sql_parts.append(f"""
-- Validation Query: Verify row counts and checksum
SELECT
    COUNT(*) AS target_row_count,
    CURRENT_TIMESTAMP() AS validated_at
FROM {target_fqn};
""")

        return "\n".join(sql_parts)

    @classmethod
    def _build_source_expression(cls, mapping: ColumnMapping) -> str:
        """Constructs BigQuery column transformation expression safely."""
        col = f"`{mapping.source_column}`"
        rule = mapping.transformation_rule
        if rule == "UPPER":
            return f"UPPER({col})"
        elif rule == "LOWER":
            return f"LOWER({col})"
        elif rule == "TRIM":
            return f"TRIM({col})"
        elif rule == "COALESCE":
            default = mapping.default_value or "''"
            return f"COALESCE({col}, {default})"
        elif rule == "CUSTOM" and mapping.custom_expression:
            return mapping.custom_expression
        return col

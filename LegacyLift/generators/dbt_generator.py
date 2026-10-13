"""
dbt Project Generator for LegacyLift.
Generates complete dbt project artifacts for downstream Snowflake modeling:
dbt_project.yml, staging models, marts models, sources.yml, and schema tests (unique, not_null).
"""
from typing import Dict, Any
from core.models import MigrationPlan


class DbtGenerator:
    @classmethod
    def generate_dbt_project(cls, plan: MigrationPlan) -> Dict[str, str]:
        table_name = plan.source_metadata.table_name.lower()
        target_parts = plan.target_table_id.split(".")
        db = target_parts[0] if len(target_parts) > 0 else "ANALYTICS_DW"
        schema = target_parts[1] if len(target_parts) > 1 else "HISTORICAL"
        table = target_parts[2] if len(target_parts) > 2 else table_name.upper()

        # 1. dbt_project.yml
        dbt_project_yml = f"""name: 'legacylift_transformations'
version: '1.0.0'
config-version: 2

profile: 'snowflake_profile'

model-paths: ["models"]
test-paths: ["tests"]
seed-paths: ["seeds"]

models:
  legacylift_transformations:
    staging:
      +materialized: view
    marts:
      +materialized: table
"""

        # 2. sources.yml
        sources_yml = f"""version: 2

sources:
  - name: historical_raw
    database: {db}
    schema: {schema}
    tables:
      - name: {table}
        description: "Raw historical table migrated from BigQuery by LegacyLift"
"""

        # 3. stg_<table_name>.sql
        select_cols = []
        for m in plan.mappings:
            col_sql = f'"{m.target_column}"'
            rule = m.transformation_rule
            if rule == "UPPER":
                expr = f"UPPER({col_sql}) AS {m.target_column.lower()}"
            elif rule == "LOWER":
                expr = f"LOWER({col_sql}) AS {m.target_column.lower()}"
            elif rule == "TRIM":
                expr = f"TRIM({col_sql}) AS {m.target_column.lower()}"
            elif rule == "COALESCE":
                default_val = m.default_value or "''"
                expr = f"COALESCE({col_sql}, {default_val}) AS {m.target_column.lower()}"
            else:
                expr = f"{col_sql} AS {m.target_column.lower()}"
            select_cols.append(f"        {expr}")

        cols_str = ",\n".join(select_cols)

        staging_sql = f"""-- Staging Model: stg_{table_name}.sql
WITH source_data AS (
    SELECT * FROM {{{{ source('historical_raw', '{table}') }}}}
)

SELECT
{cols_str},
    CURRENT_TIMESTAMP() AS dbt_loaded_at
FROM source_data
"""

        # 4. dim_<table_name>.sql
        marts_sql = f"""-- Production Mart Model: dim_{table_name}.sql
WITH staging AS (
    SELECT * FROM {{{{ ref('stg_{table_name}') }}}}
)

SELECT
    *
FROM staging
"""

        # 5. schema.yml with tests
        pk_col = next((m.target_column.lower() for m in plan.mappings if m.is_primary_key), None)
        tests_block = ""
        if pk_col:
            tests_block = f"""        columns:
          - name: {pk_col}
            description: "Primary key identifier"
            tests:
              - unique
              - not_null
"""

        schema_yml = f"""version: 2

models:
  - name: stg_{table_name}
    description: "Standardized staging layer for {table_name}"
{tests_block}
  - name: dim_{table_name}
    description: "Curated analytics dimension table"
"""

        return {
            "dbt_project.yml": dbt_project_yml,
            "models/staging/sources.yml": sources_yml,
            f"models/staging/stg_{table_name}.sql": staging_sql,
            f"models/marts/dim_{table_name}.sql": marts_sql,
            "models/staging/schema.yml": schema_yml,
        }

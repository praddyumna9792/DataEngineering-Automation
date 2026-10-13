"""
Unit tests for Pipeline Generators: Airflow DAG, Dataproc PySpark, and dbt.
"""
import pytest
from core.migration_planner import MigrationPlanner
from generators.airflow_generator import AirflowGenerator
from generators.dataproc_generator import DataprocGenerator
from generators.dbt_generator import DbtGenerator


@pytest.fixture
def sample_plan():
    planner = MigrationPlanner()
    plan, _ = planner.create_plan(
        source_table_name="orders_archive",
        target_table_name="ORDERS_ARCHIVE",
    )
    return plan


def test_airflow_generator(sample_plan):
    dag_code = AirflowGenerator.generate_dag_code(sample_plan)
    assert "from airflow import DAG" in dag_code
    assert "legacylift_migration_orders_archive" in dag_code
    assert "export_bigquery_to_iceberg_gcs" in dag_code
    assert "materialize_snowflake_native_table" in dag_code
    assert ">>" in dag_code


def test_dataproc_generator(sample_plan):
    spark_code = DataprocGenerator.generate_pyspark_job(sample_plan)
    assert "from pyspark.sql import SparkSession" in spark_code
    assert "iceberg_catalog" in spark_code
    assert "orders_archive" in spark_code


def test_dbt_generator(sample_plan):
    dbt_files = DbtGenerator.generate_dbt_project(sample_plan)
    assert "dbt_project.yml" in dbt_files
    assert "models/staging/sources.yml" in dbt_files
    assert "models/staging/stg_orders_archive.sql" in dbt_files
    assert "models/marts/dim_orders_archive.sql" in dbt_files
    assert "models/staging/schema.yml" in dbt_files

    # Check schema tests
    schema_yml = dbt_files["models/staging/schema.yml"]
    assert "unique" in schema_yml
    assert "not_null" in schema_yml

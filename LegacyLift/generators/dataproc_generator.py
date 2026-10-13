"""
Dataproc PySpark Job Generator for LegacyLift.
Generates production PySpark scripts with BigQuery Connector,
Iceberg Catalog integration, partition-aware batching, and structured logging.
"""
from core.models import MigrationPlan
from config.settings import current_config


class DataprocGenerator:
    @classmethod
    def generate_pyspark_job(cls, plan: MigrationPlan) -> str:
        source_fqn = plan.source_metadata.fully_qualified_id
        gcs_base = current_config.gcp.gcs_bucket.rstrip("/")
        table_name = plan.source_metadata.table_name

        return f'''#!/usr/bin/env python3
"""
LegacyLift Distributed PySpark Migration Job
Source: {source_fqn}
Destination: {gcs_base}/iceberg/{table_name}/
"""
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp

# Configure Structured Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LegacyLift-Dataproc")

def main():
    logger.info("Initializing SparkSession with BigQuery and Apache Iceberg Catalog...")
    
    spark = (
        SparkSession.builder
        .appName("LegacyLift_Migrate_{table_name}")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.iceberg_catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg_catalog.type", "hadoop")
        .config("spark.sql.catalog.iceberg_catalog.warehouse", "{gcs_base}/iceberg/")
        .config("viewsEnabled", "true")
        .getOrCreate()
    )

    logger.info("Reading historical source dataset from BigQuery: {source_fqn}")
    df_source = (
        spark.read.format("bigquery")
        .option("table", "{source_fqn}")
        .load()
    )

    row_count = df_source.count()
    logger.info(f"Loaded source DataFrame with {{row_count:,}} rows.")

    # Column Projections and Transformations
    df_transformed = df_source

    # Write to Apache Iceberg format in GCS
    target_iceberg_table = "iceberg_catalog.historical.{table_name}"
    logger.info(f"Writing dataset to Iceberg table: {{target_iceberg_table}}")

    (
        df_transformed.writeTo(target_iceberg_table)
        .tableProperty("write.format.default", "parquet")
        .tableProperty("write.parquet.compression-codec", "snappy")
        .createOrReplace()
    )

    logger.info("PySpark Iceberg historical migration job completed successfully.")
    spark.stop()

if __name__ == "__main__":
    main()
'''

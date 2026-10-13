"""
Settings and configuration management for LegacyLift.
Supports both Simulation mode and Live Cloud mode.
"""
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Dict, Any

# Root paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
RUNS_DIR = ARTIFACTS_DIR / "runs"
DEFAULT_DB_PATH = ARTIFACTS_DIR / "legacylift.db"

# Ensure directories exist
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class GCPConfig:
    project_id: str = "acme-analytics-prod"
    default_dataset: str = "legacy_dw"
    location: str = "US"
    gcs_bucket: str = "gs://legacylift-iceberg-prod-us"
    iceberg_metadata_prefix: str = "iceberg/metadata"
    iceberg_catalog: str = "legacylift_iceberg_catalog"
    dataproc_cluster: str = "legacylift-spark-cluster"
    dataproc_region: str = "us-central1"
    service_account_key_path: str = ""


@dataclass
class SnowflakeConfig:
    account: str = "xy12345.us-east-1"
    user: str = "MIGRATION_ADMIN"
    password: str = ""
    role: str = "SYSADMIN"
    warehouse: str = "COMPUTE_WH"
    default_database: str = "ANALYTICS_DW"
    default_schema: str = "HISTORICAL"
    storage_integration: str = "GCS_LEGACYLIFT_STORAGE_INT"
    external_volume: str = "EXVOL_LEGACYLIFT_ICEBERG"
    catalog_integration: str = "CATALOG_LEGACYLIFT_GCS"


@dataclass
class ExecutionConfig:
    mode: str = "SIMULATION"  # "SIMULATION" or "LIVE"
    default_batch_size: int = 500_000
    max_concurrency: int = 3
    retry_limit: int = 3
    retry_backoff_base: float = 1.0  # seconds
    timeout_seconds: int = 3600
    validate_row_counts: bool = True
    validate_checksums: bool = True
    stop_on_first_error: bool = False


@dataclass
class AppConfig:
    gcp: GCPConfig = field(default_factory=GCPConfig)
    snowflake: SnowflakeConfig = field(default_factory=SnowflakeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    db_path: Path = DEFAULT_DB_PATH
    runs_dir: Path = RUNS_DIR

    @classmethod
    def load_from_env(cls) -> "AppConfig":
        """Loads configuration from environment variables with sensible defaults."""
        gcp = GCPConfig(
            project_id=os.getenv("GCP_PROJECT_ID", "acme-analytics-prod"),
            default_dataset=os.getenv("GCP_DEFAULT_DATASET", "legacy_dw"),
            location=os.getenv("GCP_LOCATION", "US"),
            gcs_bucket=os.getenv("GCS_BUCKET", "gs://legacylift-iceberg-prod-us"),
            iceberg_catalog=os.getenv("ICEBERG_CATALOG", "legacylift_iceberg_catalog"),
            dataproc_cluster=os.getenv("DATAPROC_CLUSTER", "legacylift-spark-cluster"),
            dataproc_region=os.getenv("DATAPROC_REGION", "us-central1"),
            service_account_key_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        )
        snowflake = SnowflakeConfig(
            account=os.getenv("SNOWFLAKE_ACCOUNT", "xy12345.us-east-1"),
            user=os.getenv("SNOWFLAKE_USER", "MIGRATION_ADMIN"),
            password=os.getenv("SNOWFLAKE_PASSWORD", ""),
            role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
            default_database=os.getenv("SNOWFLAKE_DATABASE", "ANALYTICS_DW"),
            default_schema=os.getenv("SNOWFLAKE_SCHEMA", "HISTORICAL"),
            storage_integration=os.getenv("SNOWFLAKE_STORAGE_INTEGRATION", "GCS_LEGACYLIFT_STORAGE_INT"),
            external_volume=os.getenv("SNOWFLAKE_EXTERNAL_VOLUME", "EXVOL_LEGACYLIFT_ICEBERG"),
            catalog_integration=os.getenv("SNOWFLAKE_CATALOG_INTEGRATION", "CATALOG_LEGACYLIFT_GCS")
        )
        mode = os.getenv("LEGACYLIFT_MODE", "SIMULATION")
        execution = ExecutionConfig(
            mode=mode,
            default_batch_size=int(os.getenv("DEFAULT_BATCH_SIZE", "500000")),
            max_concurrency=int(os.getenv("MAX_CONCURRENCY", "3")),
            retry_limit=int(os.getenv("RETRY_LIMIT", "3")),
            retry_backoff_base=float(os.getenv("RETRY_BACKOFF_BASE", "1.0")),
            timeout_seconds=int(os.getenv("TIMEOUT_SECONDS", "3600")),
            validate_row_counts=os.getenv("VALIDATE_ROW_COUNTS", "true").lower() == "true",
            validate_checksums=os.getenv("VALIDATE_CHECKSUMS", "true").lower() == "true"
        )
        return cls(gcp=gcp, snowflake=snowflake, execution=execution)


# Global configuration singleton instance
current_config = AppConfig.load_from_env()

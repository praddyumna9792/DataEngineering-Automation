"""
Base interfaces and abstract connector classes for cloud services.
Provides consistent contract for both Simulation and Live adapters.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from core.models import TableMetadata, TargetTableStatus


class BaseBigQueryConnector(ABC):
    @abstractmethod
    def search_tables(self, table_name: str, search_scope: Optional[str] = None) -> List[TableMetadata]:
        """Searches authorized projects and datasets for tables matching table_name."""
        pass

    @abstractmethod
    def get_table_metadata(self, fully_qualified_id: str) -> Optional[TableMetadata]:
        """Retrieves complete metadata for a fully qualified BigQuery table."""
        pass

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Tests live GCP credentials and BigQuery API access."""
        pass

    @abstractmethod
    def execute_export(self, query: str, destination_uri: str) -> Dict[str, Any]:
        """Executes a BigQuery export job or query."""
        pass


class BaseSnowflakeConnector(ABC):
    @abstractmethod
    def search_tables(self, table_name: str, search_scope: Optional[str] = None) -> List[TableMetadata]:
        """Searches accessible databases and schemas for tables matching table_name."""
        pass

    @abstractmethod
    def get_table_metadata(self, fully_qualified_id: str) -> Optional[TableMetadata]:
        """Retrieves complete metadata for an existing Snowflake table."""
        pass

    @abstractmethod
    def check_table_exists(self, fully_qualified_id_or_name: str) -> TargetTableStatus:
        """Determines if target table exists, does not exist, or is ambiguous."""
        pass

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Tests live Snowflake connection, warehouse, and privileges."""
        pass

    @abstractmethod
    def execute_query(self, query: str) -> Dict[str, Any]:
        """Executes a Snowflake DDL or DML query."""
        pass


class BaseGCSConnector(ABC):
    @abstractmethod
    def check_bucket_access(self, bucket_uri: str) -> Dict[str, Any]:
        """Validates existence and read/write IAM permissions on GCS bucket."""
        pass

    @abstractmethod
    def list_objects(self, prefix: str) -> List[str]:
        """Lists objects at given prefix."""
        pass


class BaseAirflowConnector(ABC):
    @abstractmethod
    def validate_environment(self) -> Dict[str, Any]:
        """Checks Airflow/Cloud Composer API connectivity and DAG folder access."""
        pass

    @abstractmethod
    def deploy_dag(self, dag_id: str, dag_code: str) -> Dict[str, Any]:
        """Deploys a generated DAG to the Airflow environment."""
        pass


class BaseDataprocConnector(ABC):
    @abstractmethod
    def validate_cluster(self) -> Dict[str, Any]:
        """Checks Dataproc cluster health and PySpark environment."""
        pass

    @abstractmethod
    def submit_spark_job(self, job_script: str, args: List[str]) -> Dict[str, Any]:
        """Submits a PySpark Iceberg migration job."""
        pass

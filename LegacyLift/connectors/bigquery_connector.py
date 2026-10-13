"""
BigQuery Connector implementation supporting Simulation and Live Cloud modes.
"""
from typing import List, Optional, Dict, Any
from connectors.base import BaseBigQueryConnector
from core.models import TableMetadata
from simulation.mock_catalog import MockCatalog
from config.settings import current_config


class BigQueryConnector(BaseBigQueryConnector):
    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or current_config.execution.mode

    def search_tables(self, table_name: str, search_scope: Optional[str] = None) -> List[TableMetadata]:
        clean_name = table_name.strip().lower()
        if not clean_name:
            return []

        if self.mode == "SIMULATION":
            tables = MockCatalog.get_bigquery_tables()
            matches = []
            for t in tables:
                # Check table name match
                if t.table_name.lower() == clean_name:
                    if search_scope:
                        if search_scope.lower() in t.fully_qualified_id.lower():
                            matches.append(t)
                    else:
                        matches.append(t)
            return matches

        # Live cloud mode
        return self._search_tables_live(clean_name, search_scope)

    def get_table_metadata(self, fully_qualified_id: str) -> Optional[TableMetadata]:
        if self.mode == "SIMULATION":
            tables = MockCatalog.get_bigquery_tables()
            for t in tables:
                if t.fully_qualified_id.lower() == fully_qualified_id.lower():
                    return t
            return None

        # Live cloud mode
        return self._get_table_metadata_live(fully_qualified_id)

    def test_connection(self) -> Dict[str, Any]:
        if self.mode == "SIMULATION":
            return {
                "success": True,
                "mode": "SIMULATION",
                "message": "Connected to BigQuery Simulation Catalog (acme-analytics-prod)",
                "projects_authorized": ["acme-analytics-prod"],
                "datasets_found": ["legacy_dw", "finance_raw", "archive_vault", "hr_legacy", "telemetry"],
            }

        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=current_config.gcp.project_id)
            datasets = list(client.list_datasets(max_results=5))
            return {
                "success": True,
                "mode": "LIVE",
                "message": f"Successfully connected to GCP Project {current_config.gcp.project_id}",
                "datasets_found": [d.dataset_id for d in datasets],
            }
        except ImportError:
            return {
                "success": False,
                "mode": "LIVE",
                "message": "google-cloud-bigquery library is not installed in the Python environment.",
                "remediation": "Install via `pip install google-cloud-bigquery`.",
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "LIVE",
                "message": f"BigQuery live connection failed: {str(e)}",
                "remediation": "Check GOOGLE_APPLICATION_CREDENTIALS or gcloud auth application-default login.",
            }

    def execute_export(self, query: str, destination_uri: str) -> Dict[str, Any]:
        if self.mode == "SIMULATION":
            return {
                "success": True,
                "mode": "SIMULATION",
                "bytes_exported": 480_000_000,
                "destination_uri": destination_uri,
                "message": f"Simulated Iceberg export to {destination_uri} succeeded.",
            }

        # In live mode:
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=current_config.gcp.project_id)
            query_job = client.query(query)
            query_job.result()
            return {
                "success": True,
                "mode": "LIVE",
                "job_id": query_job.job_id,
                "destination_uri": destination_uri,
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "LIVE",
                "error": str(e),
            }

    def _search_tables_live(self, table_name: str, search_scope: Optional[str] = None) -> List[TableMetadata]:
        # Live discovery fallback / implementation
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=current_config.gcp.project_id)
            matched = []
            datasets = [search_scope] if search_scope else [d.dataset_id for d in client.list_datasets()]
            for ds in datasets:
                tables = client.list_tables(ds)
                for tbl in tables:
                    if tbl.table_id.lower() == table_name.lower():
                        meta = self.get_table_metadata(f"{client.project}.{ds}.{tbl.table_id}")
                        if meta:
                            matched.append(meta)
            return matched
        except Exception:
            return []

    def _get_table_metadata_live(self, fully_qualified_id: str) -> Optional[TableMetadata]:
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=current_config.gcp.project_id)
            t = client.get_table(fully_qualified_id)
            from core.models import ColumnMetadata
            columns = [
                ColumnMetadata(
                    name=field.name,
                    data_type=field.field_type,
                    is_nullable=(field.mode != "REQUIRED"),
                    comment=field.description,
                )
                for field in t.schema
            ]
            parts = fully_qualified_id.split(".")
            return TableMetadata(
                fully_qualified_id=fully_qualified_id,
                project_or_db=parts[0] if len(parts) > 0 else client.project,
                dataset_or_schema=parts[1] if len(parts) > 1 else "",
                table_name=parts[2] if len(parts) > 2 else fully_qualified_id,
                columns=columns,
                row_count=t.num_rows,
                size_bytes=t.num_bytes,
                partition_field=t.time_partitioning.field if t.time_partitioning else None,
                partition_type=t.time_partitioning.type_ if t.time_partitioning else None,
                clustering_fields=t.clustering_fields or [],
                location=t.location,
            )
        except Exception:
            return None

"""
Dataproc Connector implementation for Spark cluster validation and job submission.
"""
from typing import Dict, Any, List, Optional
from connectors.base import BaseDataprocConnector
from config.settings import current_config


class DataprocConnector(BaseDataprocConnector):
    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or current_config.execution.mode

    def validate_cluster(self) -> Dict[str, Any]:
        if self.mode == "SIMULATION":
            return {
                "success": True,
                "mode": "SIMULATION",
                "cluster_name": current_config.gcp.dataproc_cluster,
                "region": current_config.gcp.dataproc_region,
                "status": "RUNNING",
                "spark_version": "3.5 / 4.0",
                "iceberg_catalog_support": True,
                "message": "Dataproc simulation cluster verified.",
            }

        try:
            from google.cloud import dataproc_v1
            cluster_client = dataproc_v1.ClusterControllerClient(
                client_options={"api_endpoint": f"{current_config.gcp.dataproc_region}-dataproc.googleapis.com:443"}
            )
            cluster = cluster_client.get_cluster(
                project_id=current_config.gcp.project_id,
                region=current_config.gcp.dataproc_region,
                cluster_name=current_config.gcp.dataproc_cluster,
            )
            return {
                "success": True,
                "mode": "LIVE",
                "cluster_name": cluster.cluster_name,
                "status": str(cluster.status.state.name),
            }
        except ImportError:
            return {
                "success": False,
                "mode": "LIVE",
                "message": "google-cloud-dataproc not installed.",
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "LIVE",
                "message": f"Dataproc cluster check failed: {str(e)}",
            }

    def submit_spark_job(self, job_script: str, args: List[str]) -> Dict[str, Any]:
        return {
            "success": True,
            "job_id": "spark-job-simulation-001",
            "message": "PySpark job submitted successfully in simulation mode.",
        }

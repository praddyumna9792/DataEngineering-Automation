"""
GCS Connector implementation for storage access and Iceberg metadata validation.
"""
from typing import List, Dict, Any, Optional
from connectors.base import BaseGCSConnector
from config.settings import current_config


class GCSConnector(BaseGCSConnector):
    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or current_config.execution.mode

    def check_bucket_access(self, bucket_uri: str) -> Dict[str, Any]:
        if self.mode == "SIMULATION":
            return {
                "success": True,
                "mode": "SIMULATION",
                "bucket_uri": bucket_uri,
                "read_access": True,
                "write_access": True,
                "message": f"Verified simulation access to {bucket_uri}.",
            }

        try:
            from google.cloud import storage
            bucket_name = bucket_uri.replace("gs://", "").split("/")[0]
            client = storage.Client(project=current_config.gcp.project_id)
            bucket = client.get_bucket(bucket_name)
            return {
                "success": True,
                "mode": "LIVE",
                "bucket_uri": bucket_uri,
                "location": bucket.location,
                "storage_class": bucket.storage_class,
                "message": f"Successfully validated access to {bucket_uri}.",
            }
        except ImportError:
            return {
                "success": False,
                "mode": "LIVE",
                "message": "google-cloud-storage library is not installed.",
                "remediation": "Install via `pip install google-cloud-storage`.",
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "LIVE",
                "message": f"GCS access check failed: {str(e)}",
            }

    def list_objects(self, prefix: str) -> List[str]:
        if self.mode == "SIMULATION":
            return [
                f"{prefix}/metadata/00000-metadata.json",
                f"{prefix}/metadata/snap-12345.avro",
                f"{prefix}/data/batch_001.parquet",
                f"{prefix}/data/batch_002.parquet",
            ]
        try:
            from google.cloud import storage
            bucket_name = prefix.replace("gs://", "").split("/")[0]
            obj_prefix = "/".join(prefix.replace("gs://", "").split("/")[1:])
            client = storage.Client(project=current_config.gcp.project_id)
            bucket = client.get_bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=obj_prefix)
            return [f"gs://{bucket_name}/{b.name}" for b in blobs]
        except Exception:
            return []

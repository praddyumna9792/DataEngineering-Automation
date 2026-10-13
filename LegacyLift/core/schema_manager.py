"""
Schema Manager service for parsing, normalising, comparing, and validating schemas.
Handles JSON and CSV schema uploads, BigQuery to Snowflake type mappings, and compatibility analysis.
"""
import json
import csv
import io
from typing import List, Dict, Any, Tuple, Optional
from core.models import (
    ColumnMetadata,
    TableMetadata,
    SchemaDiff,
    SchemaCompatibilityStatus,
)

# Canonical type conversion mapping from BigQuery to Snowflake
BQ_TO_SNOWFLAKE_TYPE_MAP = {
    "INT64": "NUMBER(38,0)",
    "INTEGER": "NUMBER(38,0)",
    "FLOAT64": "FLOAT",
    "FLOAT": "FLOAT",
    "NUMERIC": "NUMBER(38,9)",
    "BIGNUMERIC": "NUMBER(38,38)",
    "STRING": "VARCHAR",
    "BYTES": "BINARY",
    "BOOL": "BOOLEAN",
    "BOOLEAN": "BOOLEAN",
    "TIMESTAMP": "TIMESTAMP_NTZ",
    "DATE": "DATE",
    "TIME": "TIME",
    "DATETIME": "TIMESTAMP_NTZ",
    "GEOGRAPHY": "GEOGRAPHY",
    "JSON": "VARIANT",
    "RECORD": "OBJECT",
    "STRUCT": "OBJECT",
    "ARRAY": "ARRAY",
}


class SchemaManager:
    @staticmethod
    def map_bq_to_snowflake_type(bq_type: str, precision: Optional[int] = None, scale: Optional[int] = None) -> str:
        """Converts BigQuery data type to standard Snowflake SQL type."""
        base_type = bq_type.upper().strip()

        # Handle parameterized NUMERIC
        if base_type == "NUMERIC":
            p = precision or 38
            s = scale if scale is not None else 9
            return f"NUMBER({p},{s})"
        if base_type == "BIGNUMERIC":
            return "NUMBER(38,38)"

        # Handle ARRAY<T>
        if base_type.startswith("ARRAY"):
            return "ARRAY"

        return BQ_TO_SNOWFLAKE_TYPE_MAP.get(base_type, "VARCHAR")

    @classmethod
    def parse_schema_file(cls, file_content: str, filename: str) -> List[ColumnMetadata]:
        """Parses an uploaded schema file (JSON or CSV) into ColumnMetadata list."""
        clean_name = filename.lower()
        if clean_name.endswith(".json"):
            return cls._parse_json_schema(file_content)
        elif clean_name.endswith(".csv"):
            return cls._parse_csv_schema(file_content)
        else:
            # Attempt JSON first, then CSV
            try:
                return cls._parse_json_schema(file_content)
            except Exception:
                return cls._parse_csv_schema(file_content)

    @classmethod
    def _parse_json_schema(cls, text: str) -> List[ColumnMetadata]:
        data = json.loads(text)
        columns = []
        # Case 1: BigQuery CLI schema array: [{"name": "col", "type": "STRING", "mode": "NULLABLE"}]
        if isinstance(data, list):
            for item in data:
                name = item.get("name") or item.get("column_name")
                datatype = item.get("type") or item.get("data_type", "STRING")
                mode = item.get("mode", "NULLABLE").upper()
                is_nullable = mode != "REQUIRED"
                is_pk = bool(item.get("is_primary_key", False))
                columns.append(ColumnMetadata(
                    name=name,
                    data_type=datatype,
                    is_nullable=is_nullable,
                    is_primary_key=is_pk,
                    comment=item.get("description"),
                ))
        # Case 2: JSON Schema object format: {"properties": {"col1": {"type": "string"}}}
        elif isinstance(data, dict) and "properties" in data:
            required_cols = set(data.get("required", []))
            for col_name, prop in data["properties"].items():
                prop_type = prop.get("type", "string").upper()
                columns.append(ColumnMetadata(
                    name=col_name,
                    data_type=prop_type,
                    is_nullable=(col_name not in required_cols),
                    comment=prop.get("description"),
                ))
        return columns

    @classmethod
    def _parse_csv_schema(cls, text: str) -> List[ColumnMetadata]:
        reader = csv.DictReader(io.StringIO(text))
        columns = []
        for row in reader:
            normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            name = (
                normalized.get("column_name")
                or normalized.get("name")
                or normalized.get("column")
                or normalized.get("field_name")
            )
            if not name:
                continue
            data_type = (
                normalized.get("data_type")
                or normalized.get("type")
                or "STRING"
            )
            nullable_val = normalized.get("is_nullable", "true").lower()
            is_nullable = nullable_val in ("true", "yes", "1", "y")
            pk_val = normalized.get("is_primary_key", normalized.get("primary_key", "false")).lower()
            is_pk = pk_val in ("true", "yes", "1", "y")

            columns.append(ColumnMetadata(
                name=name,
                data_type=data_type,
                is_nullable=is_nullable,
                is_primary_key=is_pk,
                comment=normalized.get("description") or normalized.get("comment"),
            ))
        return columns

    @classmethod
    def compare_schemas(
        cls,
        source_cols: List[ColumnMetadata],
        target_cols: List[ColumnMetadata],
    ) -> SchemaDiff:
        """
        Compares BigQuery source schema columns against Snowflake target schema columns.
        Returns a detailed SchemaDiff with compatibility analysis.
        """
        source_map = {c.name.upper(): c for c in source_cols}
        target_map = {c.name.upper(): c for c in target_cols}

        missing_in_target = []
        extra_in_target = []
        mismatched_types = []
        notes = []

        # Check source columns against target
        for name, s_col in source_map.items():
            if name not in target_map:
                missing_in_target.append(s_col.name)
            else:
                t_col = target_map[name]
                expected_sf_type = cls.map_bq_to_snowflake_type(s_col.data_type, s_col.precision, s_col.scale)
                # Check compatibility of type
                if not cls._are_types_compatible(expected_sf_type, t_col.data_type):
                    mismatched_types.append({
                        "column": s_col.name,
                        "source_bq_type": s_col.data_type,
                        "expected_snowflake_type": expected_sf_type,
                        "target_actual_type": t_col.data_type,
                        "severity": "ERROR",
                    })

        # Check target columns not present in source
        for name, t_col in target_map.items():
            if name not in source_map:
                extra_in_target.append(t_col.name)
                if not t_col.is_nullable:
                    notes.append(f"Target column '{t_col.name}' is NOT NULL but missing in source data.")

        # Determine overall compatibility status
        if not missing_in_target and not extra_in_target and not mismatched_types:
            status = SchemaCompatibilityStatus.EXACT_MATCH
            is_safe = True
            notes.append("Schemas match identically.")
        elif not mismatched_types and not missing_in_target:
            status = SchemaCompatibilityStatus.COMPATIBLE
            is_safe = True
            notes.append(f"Target has {len(extra_in_target)} additional nullable columns. Safe to load.")
        elif mismatched_types or missing_in_target:
            status = SchemaCompatibilityStatus.INCOMPATIBLE
            is_safe = False
            if missing_in_target:
                notes.append(f"Target table is missing {len(missing_in_target)} columns present in source.")
            if mismatched_types:
                notes.append(f"Target table contains {len(mismatched_types)} incompatible column data types.")
        else:
            status = SchemaCompatibilityStatus.COMPATIBLE
            is_safe = True

        return SchemaDiff(
            status=status,
            missing_columns_in_target=missing_in_target,
            extra_columns_in_target=extra_in_target,
            mismatched_types=mismatched_types,
            compatibility_notes=notes,
            is_safe_to_load=is_safe,
        )

    @classmethod
    def _are_types_compatible(cls, expected_sf: str, actual_sf: str) -> bool:
        """Determines if actual Snowflake column type can safely hold expected source data."""
        e = expected_sf.upper()
        a = actual_sf.upper()

        if e == a:
            return True

        # Number / Integer compatibility
        if "NUMBER" in e or "INT" in e:
            if "NUMBER" in a or "INT" in a or "FLOAT" in a or "NUMERIC" in a:
                return True

        # String / Varchar compatibility
        if "VARCHAR" in e or "STRING" in e or "TEXT" in e:
            if "VARCHAR" in a or "STRING" in a or "TEXT" in a:
                return True

        # Variant / Object / JSON compatibility
        if e in ("VARIANT", "OBJECT", "ARRAY") and a in ("VARIANT", "OBJECT", "ARRAY"):
            return True

        # Date / Timestamp compatibility
        if "TIMESTAMP" in e and "TIMESTAMP" in a:
            return True

        # Incompatible narrowing (e.g. NUMBER into VARCHAR or vice versa without explicit cast)
        return False

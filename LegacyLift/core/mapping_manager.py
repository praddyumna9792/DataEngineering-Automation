"""
Mapping Manager service for parsing, inspecting, validating, and generating column mappings.
Supports CSV, XLSX, dynamic column matching, transformations, and duplicate detection.
"""
import io
import csv
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

from core.models import ColumnMapping, ColumnMetadata
from core.schema_manager import SchemaManager

SUPPORTED_TRANSFORMATIONS = {
    "DIRECT",
    "UPPER",
    "LOWER",
    "TRIM",
    "COALESCE",
    "CAST",
    "CUSTOM",
}


class MappingManager:
    @classmethod
    def generate_default_mappings(
        cls,
        source_cols: List[ColumnMetadata],
        target_cols: Optional[List[ColumnMetadata]] = None,
    ) -> List[ColumnMapping]:
        """
        Generates 1-to-1 default mappings from source metadata.
        If target metadata is available, matches columns case-insensitively.
        """
        target_map = {c.name.upper(): c for c in target_cols} if target_cols else {}
        mappings = []

        for s_col in source_cols:
            tgt_col_name = s_col.name.upper()
            if tgt_col_name in target_map:
                t_col = target_map[tgt_col_name]
                tgt_type = t_col.data_type
            else:
                tgt_type = SchemaManager.map_bq_to_snowflake_type(
                    s_col.data_type, s_col.precision, s_col.scale
                )

            mappings.append(ColumnMapping(
                source_column=s_col.name,
                target_column=tgt_col_name,
                source_type=s_col.data_type,
                target_type=tgt_type,
                transformation_rule="DIRECT",
                is_primary_key=s_col.is_primary_key,
                is_nullable=s_col.is_nullable,
            ))
        return mappings

    @classmethod
    def parse_mapping_file(cls, file_bytes: bytes, filename: str) -> Tuple[List[ColumnMapping], Dict[str, Any]]:
        """
        Parses an uploaded CSV or XLSX file, auto-detects header aliases,
        and returns parsed ColumnMappings with a validation report.
        """
        clean_name = filename.lower()
        if clean_name.endswith(".xlsx") or clean_name.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.BytesIO(file_bytes), index_col=False)

        # Normalize column header names
        header_map = cls._detect_header_mapping(df.columns.tolist())

        mappings: List[ColumnMapping] = []
        errors = []
        warnings = []
        seen_sources = set()
        seen_targets = set()

        for i, (_, row) in enumerate(df.iterrows()):
            row_num = i + 2  # 1-indexed header is line 1

            src_col = str(row.get(header_map.get("source_column", ""), "")).strip()
            tgt_col = str(row.get(header_map.get("target_column", ""), "")).strip()

            if not src_col or src_col.lower() in ("nan", "none", ""):
                errors.append(f"Row {row_num}: Missing source column name.")
                continue

            if not tgt_col or tgt_col.lower() in ("nan", "none", ""):
                tgt_col = src_col.upper()

            # Duplicate detection
            if src_col.lower() in seen_sources:
                warnings.append(f"Row {row_num}: Source column '{src_col}' is mapped multiple times.")
            seen_sources.add(src_col.lower())

            if tgt_col.upper() in seen_targets:
                errors.append(f"Row {row_num}: Target column '{tgt_col}' is targeted by multiple source columns.")
            seen_targets.add(tgt_col.upper())

            src_type = str(row.get(header_map.get("source_type", ""), "STRING")).strip().upper()
            if src_type in ("NAN", "NONE", ""):
                src_type = "STRING"

            tgt_type = str(row.get(header_map.get("target_type", ""), "")).strip().upper()
            if not tgt_type or tgt_type in ("NAN", "NONE", ""):
                tgt_type = SchemaManager.map_bq_to_snowflake_type(src_type)

            rule = str(row.get(header_map.get("transformation_rule", ""), "DIRECT")).strip().upper()
            if rule not in SUPPORTED_TRANSFORMATIONS:
                warnings.append(f"Row {row_num}: Unsupported transformation '{rule}', defaulting to DIRECT.")
                rule = "DIRECT"

            is_pk = False
            pk_val = str(row.get(header_map.get("is_primary_key", ""), "")).strip().lower()
            if pk_val in ("true", "1", "yes", "y", "pk"):
                is_pk = True

            is_null = True
            null_val = str(row.get(header_map.get("is_nullable", ""), "")).strip().lower()
            if null_val in ("false", "0", "no", "n", "required"):
                is_null = False

            default_val = row.get(header_map.get("default_value", ""), None)
            if pd.isna(default_val):
                default_val = None
            else:
                default_val = str(default_val).strip()

            custom_expr = row.get(header_map.get("custom_expression", ""), None)
            if pd.isna(custom_expr):
                custom_expr = None
            else:
                custom_expr = str(custom_expr).strip()

            mappings.append(ColumnMapping(
                source_column=src_col,
                target_column=tgt_col.upper(),
                source_type=src_type,
                target_type=tgt_type,
                transformation_rule=rule,
                custom_expression=custom_expr,
                is_primary_key=is_pk,
                is_nullable=is_null,
                default_value=default_val,
            ))

        validation_report = {
            "total_mapped": len(mappings),
            "errors": errors,
            "warnings": warnings,
            "is_valid": len(errors) == 0,
        }

        return mappings, validation_report

    @classmethod
    def _detect_header_mapping(cls, headers: List[str]) -> Dict[str, str]:
        """Dynamically matches flexible user headers to standard mapping attributes."""
        res = {}
        for h in headers:
            clean = h.strip().lower().replace(" ", "_").replace("-", "_")
            if clean in ("source_column", "source_col", "src_col", "source", "source_field", "bq_column"):
                res["source_column"] = h
            elif clean in ("target_column", "target_col", "tgt_col", "target", "target_field", "snowflake_column", "destination"):
                res["target_column"] = h
            elif clean in ("source_type", "src_type", "bq_type", "source_datatype", "input_type"):
                res["source_type"] = h
            elif clean in ("target_type", "tgt_type", "snowflake_type", "target_datatype", "output_type"):
                res["target_type"] = h
            elif clean in ("transformation_rule", "transformation", "transform", "rule", "logic"):
                res["transformation_rule"] = h
            elif clean in ("custom_expression", "expression", "sql_expression"):
                res["custom_expression"] = h
            elif clean in ("is_primary_key", "primary_key", "pk", "is_pk"):
                res["is_primary_key"] = h
            elif clean in ("is_nullable", "nullable", "null"):
                res["is_nullable"] = h
            elif clean in ("default_value", "default", "default_val"):
                res["default_value"] = h
        return res

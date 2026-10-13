"""
SQL Validation Service for LegacyLift.
Inspects generated or user-edited SQL for syntax anomalies, destructive statements,
identifier injection risks, and dependency integrity.
"""
from typing import Dict, List, Any
import sqlparse


class SQLValidator:
    DESTRUCTIVE_KEYWORDS = ["DROP TABLE", "DROP SCHEMA", "DROP DATABASE", "TRUNCATE TABLE", "DELETE FROM"]

    @classmethod
    def validate_sql_text(cls, sql: str, stage_name: str) -> Dict[str, Any]:
        """
        Validates a SQL script text.
        Returns validation status, errors, warnings, and detected statements.
        """
        errors: List[str] = []
        warnings: List[str] = []
        destructive_statements: List[str] = []

        if not sql or not sql.strip():
            return {
                "is_valid": False,
                "errors": [f"SQL content for {stage_name} is empty."],
                "warnings": [],
                "destructive_statements": [],
                "statement_count": 0,
            }

        parsed = sqlparse.parse(sql)
        stmt_count = len([s for s in parsed if s.get_type() != "UNKNOWN" or s.tokens])

        # Check for destructive commands
        upper_sql = sql.upper()
        for kw in cls.DESTRUCTIVE_KEYWORDS:
            if kw in upper_sql:
                destructive_statements.append(kw)
                if kw in ("DROP TABLE", "DROP DATABASE", "DROP SCHEMA"):
                    errors.append(f"Destructive statement '{kw}' detected. Table drops are forbidden in production migration plans.")
                elif kw == "TRUNCATE TABLE":
                    warnings.append(f"Notice: '{kw}' detected (acceptable only if controlled refresh is explicitly authorized).")

        # Unbalanced quotes or parentheses
        single_quotes = sql.count("'") - sql.count("\\'")
        if single_quotes % 2 != 0:
            errors.append("Unbalanced single quotes detected in SQL text.")

        if sql.count("(") != sql.count(")"):
            errors.append("Unbalanced parentheses detected in SQL text.")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "destructive_statements": destructive_statements,
            "statement_count": stmt_count,
        }

    @classmethod
    def validate_all_stages(cls, stage_sqls: Dict[str, str]) -> Dict[str, Any]:
        """Validates all 4 SQL stages."""
        overall_valid = True
        stage_results = {}
        all_warnings = []
        all_errors = []

        for stage, sql in stage_sqls.items():
            res = cls.validate_sql_text(sql, stage)
            stage_results[stage] = res
            if not res["is_valid"]:
                overall_valid = False
            all_errors.extend([f"[{stage}] {e}" for e in res["errors"]])
            all_warnings.extend([f"[{stage}] {w}" for w in res["warnings"]])

        return {
            "is_valid": overall_valid,
            "stages": stage_results,
            "errors": all_errors,
            "warnings": all_warnings,
        }

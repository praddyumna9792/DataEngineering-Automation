"""
Repository abstractions for persisting plans, runs, checkpoints, and settings.
"""
import json
import sqlite3
import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from config.settings import DEFAULT_DB_PATH
from core.models import (
    MigrationPlan,
    MigrationRun,
    BatchDefinition,
    RunStatus,
    BatchStatus,
    LoadStrategy,
)
from persistence.db import get_db_connection


class PlanRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def save_plan(self, plan: MigrationPlan) -> None:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        plan_dict = plan.to_dict()

        cursor.execute("""
        INSERT INTO migration_plans (
            plan_id, source_table_id, target_table_id,
            source_metadata_json, target_metadata_json,
            target_exists, schema_diff_json, mappings_json,
            stage1_sql, stage2_sql, stage3_sql, stage4_sql,
            batches_json, readiness_report_json, load_strategy,
            is_approved, approved_at, approved_by,
            sql_modified_since_approval, version, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(plan_id) DO UPDATE SET
            source_table_id=excluded.source_table_id,
            target_table_id=excluded.target_table_id,
            source_metadata_json=excluded.source_metadata_json,
            target_metadata_json=excluded.target_metadata_json,
            target_exists=excluded.target_exists,
            schema_diff_json=excluded.schema_diff_json,
            mappings_json=excluded.mappings_json,
            stage1_sql=excluded.stage1_sql,
            stage2_sql=excluded.stage2_sql,
            stage3_sql=excluded.stage3_sql,
            stage4_sql=excluded.stage4_sql,
            batches_json=excluded.batches_json,
            readiness_report_json=excluded.readiness_report_json,
            load_strategy=excluded.load_strategy,
            is_approved=excluded.is_approved,
            approved_at=excluded.approved_at,
            approved_by=excluded.approved_by,
            sql_modified_since_approval=excluded.sql_modified_since_approval,
            version=excluded.version,
            created_at=excluded.created_at
        """, (
            plan.plan_id,
            plan.source_table_id,
            plan.target_table_id,
            json.dumps(plan_dict["source_metadata"]),
            json.dumps(plan_dict["target_metadata"]) if plan_dict["target_metadata"] else None,
            1 if plan.target_exists else 0,
            json.dumps(plan_dict["schema_diff"]) if plan_dict["schema_diff"] else None,
            json.dumps(plan_dict["mappings"]),
            plan.stage1_sql,
            plan.stage2_sql,
            plan.stage3_sql,
            plan.stage4_sql,
            json.dumps(plan_dict["batches"]),
            json.dumps(plan_dict["readiness_report"]),
            plan.load_strategy.value,
            1 if plan.is_approved else 0,
            plan.approved_at,
            plan.approved_by,
            1 if plan.sql_modified_since_approval else 0,
            plan.version,
            plan.created_at,
        ))
        conn.commit()
        conn.close()

    def get_plan(self, plan_id: str) -> Optional[MigrationPlan]:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM migration_plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        data = {
            "plan_id": row["plan_id"],
            "source_table_id": row["source_table_id"],
            "target_table_id": row["target_table_id"],
            "source_metadata": json.loads(row["source_metadata_json"]),
            "target_metadata": json.loads(row["target_metadata_json"]) if row["target_metadata_json"] else None,
            "target_exists": bool(row["target_exists"]),
            "schema_diff": json.loads(row["schema_diff_json"]) if row["schema_diff_json"] else None,
            "mappings": json.loads(row["mappings_json"]),
            "stage1_sql": row["stage1_sql"],
            "stage2_sql": row["stage2_sql"],
            "stage3_sql": row["stage3_sql"],
            "stage4_sql": row["stage4_sql"],
            "batches": json.loads(row["batches_json"]),
            "readiness_report": json.loads(row["readiness_report_json"]),
            "load_strategy": row["load_strategy"],
            "is_approved": bool(row["is_approved"]),
            "approved_at": row["approved_at"],
            "approved_by": row["approved_by"],
            "sql_modified_since_approval": bool(row["sql_modified_since_approval"]),
            "version": row["version"],
            "created_at": row["created_at"],
        }
        return MigrationPlan.from_dict(data)

    def list_plans(self, limit: int = 50) -> List[MigrationPlan]:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT plan_id FROM migration_plans ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        plans = []
        for r in rows:
            p = self.get_plan(r["plan_id"])
            if p:
                plans.append(p)
        return plans


class RunRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def save_run(self, run: MigrationRun) -> None:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        run_dict = run.to_dict()

        cursor.execute("""
        INSERT INTO migration_runs (
            run_id, plan_id, source_table_id, target_table_id,
            mode, status, started_at, completed_at, current_stage,
            stage_statuses_json, batches_json, total_rows_expected,
            total_rows_migrated, logs_json, reconciliation_report_json,
            error_summary
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(run_id) DO UPDATE SET
            plan_id=excluded.plan_id,
            source_table_id=excluded.source_table_id,
            target_table_id=excluded.target_table_id,
            mode=excluded.mode,
            status=excluded.status,
            started_at=excluded.started_at,
            completed_at=excluded.completed_at,
            current_stage=excluded.current_stage,
            stage_statuses_json=excluded.stage_statuses_json,
            batches_json=excluded.batches_json,
            total_rows_expected=excluded.total_rows_expected,
            total_rows_migrated=excluded.total_rows_migrated,
            logs_json=excluded.logs_json,
            reconciliation_report_json=excluded.reconciliation_report_json,
            error_summary=excluded.error_summary
        """, (
            run.run_id,
            run.plan_id,
            run.source_table_id,
            run.target_table_id,
            run.mode,
            run.status.value,
            run.started_at,
            run.completed_at,
            run.current_stage,
            json.dumps(run.stage_statuses),
            json.dumps([b.to_dict() for b in run.batches]),
            run.total_rows_expected,
            run.total_rows_migrated,
            json.dumps(run.logs),
            json.dumps(run.reconciliation_report) if run.reconciliation_report else None,
            run.error_summary,
        ))

        # Save individual batch checkpoints
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for b in run.batches:
            cursor.execute("""
            INSERT INTO batch_checkpoints (
                run_id, batch_id, batch_number, total_batches,
                partition_start, partition_end, filter_expression,
                status, rows_expected, rows_migrated, attempts,
                last_error, duration_seconds, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(run_id, batch_id) DO UPDATE SET
                status=excluded.status,
                rows_expected=excluded.rows_expected,
                rows_migrated=excluded.rows_migrated,
                attempts=excluded.attempts,
                last_error=excluded.last_error,
                duration_seconds=excluded.duration_seconds,
                updated_at=excluded.updated_at
            """, (
                run.run_id,
                b.batch_id,
                b.batch_number,
                b.total_batches,
                b.partition_start,
                b.partition_end,
                b.filter_expression,
                b.status.value,
                b.rows_expected,
                b.rows_migrated,
                b.attempts,
                b.last_error,
                b.duration_seconds,
                now,
            ))

        conn.commit()
        conn.close()

    def get_run(self, run_id: str) -> Optional[MigrationRun]:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM migration_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        batches_data = json.loads(row["batches_json"])
        batches = [BatchDefinition.from_dict(b) for b in batches_data]

        data = {
            "run_id": row["run_id"],
            "plan_id": row["plan_id"],
            "source_table_id": row["source_table_id"],
            "target_table_id": row["target_table_id"],
            "mode": row["mode"],
            "status": RunStatus(row["status"]),
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "current_stage": row["current_stage"],
            "stage_statuses": json.loads(row["stage_statuses_json"]),
            "batches": batches,
            "total_rows_expected": row["total_rows_expected"],
            "total_rows_migrated": row["total_rows_migrated"],
            "logs": json.loads(row["logs_json"]),
            "reconciliation_report": json.loads(row["reconciliation_report_json"]) if row["reconciliation_report_json"] else None,
            "error_summary": row["error_summary"],
        }
        return MigrationRun(**data)

    def list_runs(self, limit: int = 50) -> List[MigrationRun]:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT run_id FROM migration_runs ORDER BY started_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        runs = []
        for r in rows:
            run = self.get_run(r["run_id"])
            if run:
                runs.append(run)
        return runs

    def get_batch_checkpoints(self, run_id: str) -> List[BatchDefinition]:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM batch_checkpoints WHERE run_id = ? ORDER BY batch_number ASC", (run_id,))
        rows = cursor.fetchall()
        conn.close()

        checkpoints = []
        for r in rows:
            b = BatchDefinition(
                batch_id=r["batch_id"],
                batch_number=r["batch_number"],
                total_batches=r["total_batches"],
                partition_start=r["partition_start"],
                partition_end=r["partition_end"],
                filter_expression=r["filter_expression"],
                status=BatchStatus(r["status"]),
                rows_expected=r["rows_expected"],
                rows_migrated=r["rows_migrated"],
                attempts=r["attempts"],
                last_error=r["last_error"],
                duration_seconds=r["duration_seconds"],
            )
            checkpoints.append(b)
        return checkpoints


class SettingsRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def get_setting(self, key: str, default: Any = None) -> Any:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_val FROM system_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return default
        try:
            return json.loads(row["setting_val"])
        except Exception:
            return row["setting_val"]

    def set_setting(self, key: str, value: Any) -> None:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        val_str = json.dumps(value)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
        INSERT INTO system_settings (setting_key, setting_val, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET setting_val=excluded.setting_val, updated_at=excluded.updated_at
        """, (key, val_str, now))
        conn.commit()
        conn.close()

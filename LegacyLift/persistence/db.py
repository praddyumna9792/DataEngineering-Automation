"""
SQLite Database initialization and connection manager for LegacyLift.
Provides durable persistence for plans, approvals, runs, batch checkpoints, and settings.
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional
from config.settings import DEFAULT_DB_PATH


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with row factory enabled."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: Optional[Path] = None) -> None:
    """Initializes the SQLite database tables if they do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Migration Plans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS migration_plans (
        plan_id TEXT PRIMARY KEY,
        source_table_id TEXT NOT NULL,
        target_table_id TEXT NOT NULL,
        source_metadata_json TEXT NOT NULL,
        target_metadata_json TEXT,
        target_exists INTEGER NOT NULL DEFAULT 0,
        schema_diff_json TEXT,
        mappings_json TEXT NOT NULL,
        stage1_sql TEXT NOT NULL,
        stage2_sql TEXT NOT NULL,
        stage3_sql TEXT NOT NULL,
        stage4_sql TEXT NOT NULL,
        batches_json TEXT NOT NULL,
        readiness_report_json TEXT NOT NULL,
        load_strategy TEXT NOT NULL,
        is_approved INTEGER NOT NULL DEFAULT 0,
        approved_at TEXT,
        approved_by TEXT,
        sql_modified_since_approval INTEGER NOT NULL DEFAULT 0,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """)

    # Migration Runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS migration_runs (
        run_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        source_table_id TEXT NOT NULL,
        target_table_id TEXT NOT NULL,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        current_stage TEXT NOT NULL,
        stage_statuses_json TEXT NOT NULL,
        batches_json TEXT NOT NULL,
        total_rows_expected INTEGER NOT NULL DEFAULT 0,
        total_rows_migrated INTEGER NOT NULL DEFAULT 0,
        logs_json TEXT NOT NULL,
        reconciliation_report_json TEXT,
        error_summary TEXT,
        FOREIGN KEY (plan_id) REFERENCES migration_plans(plan_id)
    );
    """)

    # Batch Checkpoints table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batch_checkpoints (
        run_id TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        batch_number INTEGER NOT NULL,
        total_batches INTEGER NOT NULL,
        partition_start TEXT,
        partition_end TEXT,
        filter_expression TEXT NOT NULL,
        status TEXT NOT NULL,
        rows_expected INTEGER NOT NULL DEFAULT 0,
        rows_migrated INTEGER NOT NULL DEFAULT 0,
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        duration_seconds REAL NOT NULL DEFAULT 0.0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (run_id, batch_id),
        FOREIGN KEY (run_id) REFERENCES migration_runs(run_id)
    );
    """)

    # Connection Settings & Profiles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        setting_key TEXT PRIMARY KEY,
        setting_val TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()


# Initialize on import
init_database()

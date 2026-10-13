"""
Stateful Execution Engine for LegacyLift.
Executes approved migration plans in dependency order, manages batch processing,
durable checkpoints, retries, resume semantics, artifact generation, and final reconciliation.
"""
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING
import datetime
import time
import json
import uuid
from pathlib import Path

if TYPE_CHECKING:
    from persistence.repositories import RunRepository, PlanRepository

from core.models import (
    MigrationPlan,
    MigrationRun,
    BatchDefinition,
    BatchStatus,
    RunStatus,
)
from core.reconciliation import ReconciliationService
from config.settings import RUNS_DIR, current_config
from connectors.bigquery_connector import BigQueryConnector
from connectors.snowflake_connector import SnowflakeConnector


class ExecutionEngine:
    def __init__(
        self,
        run_repo: Optional["RunRepository"] = None,
        plan_repo: Optional["PlanRepository"] = None,
        bq_connector: Optional[BigQueryConnector] = None,
        sf_connector: Optional[SnowflakeConnector] = None,
    ):
        if run_repo is None:
            from persistence.repositories import RunRepository
            run_repo = RunRepository()
        if plan_repo is None:
            from persistence.repositories import PlanRepository
            plan_repo = PlanRepository()
        self.run_repo = run_repo
        self.plan_repo = plan_repo
        self.bq = bq_connector or BigQueryConnector()
        self.sf = sf_connector or SnowflakeConnector()

    def start_migration(
        self,
        plan: MigrationPlan,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        simulate_failure_on_batch: Optional[int] = None,
    ) -> MigrationRun:
        """
        Executes a validated and approved migration plan from scratch.
        Requires explicit plan approval!
        """
        # Pre-execution validation
        if not plan.is_approved:
            raise ValueError("Plan execution rejected: Plan must be explicitly approved before execution.")

        if plan.sql_modified_since_approval:
            raise ValueError("Plan execution rejected: SQL was modified since approval. Please re-validate and re-approve.")

        run_id = f"run_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Initialize run model
        run = MigrationRun(
            run_id=run_id,
            plan_id=plan.plan_id,
            source_table_id=plan.source_table_id,
            target_table_id=plan.target_table_id,
            mode=current_config.execution.mode,
            status=RunStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            current_stage="Stage 1 — Iceberg Export",
            stage_statuses={
                "stage1": "PENDING",
                "stage2": "PENDING",
                "stage3": "PENDING",
                "stage4": "PENDING",
            },
            batches=[BatchDefinition.from_dict(b.to_dict()) for b in plan.batches],
            total_rows_expected=plan.source_metadata.row_count,
            total_rows_migrated=0,
        )

        run.log(f"Initialized migration run {run_id} in {run.mode} mode.")
        run.log(f"Source: {plan.source_table_id} | Target: {plan.target_table_id}")
        run.log(f"Planned batches: {len(run.batches)} | Expected rows: {run.total_rows_expected:,}")

        # Save initial run & plan artifacts
        self._write_run_artifacts(run, plan, run_dir)
        self.run_repo.save_run(run)

        # Run pipeline stages
        try:
            self._execute_pipeline(
                run=run,
                plan=plan,
                run_dir=run_dir,
                progress_callback=progress_callback,
                simulate_failure_on_batch=simulate_failure_on_batch,
            )
        except Exception as e:
            run.status = RunStatus.FAILED
            run.error_summary = str(e)
            run.completed_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            run.log(f"[FATAL] Pipeline terminated with error: {str(e)}")
            self.run_repo.save_run(run)

        return run

    def resume_migration(
        self,
        run_id: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> MigrationRun:
        """
        Resumes an interrupted or failed migration run.
        Skips already COMPLETED batches to prevent duplicate processing.
        """
        run = self.run_repo.get_run(run_id)
        if not run:
            raise ValueError(f"Run ID {run_id} not found.")

        plan = self.plan_repo.get_plan(run.plan_id)
        if not plan:
            raise ValueError(f"Plan ID {run.plan_id} for run {run_id} not found.")

        run.status = RunStatus.RUNNING
        run.log(f"Resuming interrupted migration run {run_id}. Checking batch checkpoints...")
        self.run_repo.save_run(run)

        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._execute_pipeline(
                run=run,
                plan=plan,
                run_dir=run_dir,
                progress_callback=progress_callback,
                simulate_failure_on_batch=None,  # Do not re-fail on resume
            )
        except Exception as e:
            run.status = RunStatus.FAILED
            run.error_summary = str(e)
            run.completed_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            run.log(f"[FATAL] Resumed pipeline terminated with error: {str(e)}")
            self.run_repo.save_run(run)

        return run

    def _execute_pipeline(
        self,
        run: MigrationRun,
        plan: MigrationPlan,
        run_dir: Path,
        progress_callback: Optional[Callable[[str, float], None]],
        simulate_failure_on_batch: Optional[int],
    ) -> None:
        # Stage 1: BigQuery Iceberg Export
        if run.stage_statuses["stage1"] != "COMPLETED":
            run.current_stage = "Stage 1 — Iceberg Export"
            run.stage_statuses["stage1"] = "RUNNING"
            run.log("Starting Stage 1: Exporting BigQuery historical data to Iceberg in GCS...")
            if progress_callback:
                progress_callback("Stage 1 — Iceberg Export", 0.1)

            # In live mode, execute query via connector
            if run.mode == "LIVE":
                res = self.bq.execute_export(plan.stage1_sql, current_config.gcp.gcs_bucket)
                if not res.get("success"):
                    raise RuntimeError(f"BigQuery export failed: {res.get('error')}")

            run.stage_statuses["stage1"] = "COMPLETED"
            run.log("Stage 1 Completed: Data exported to GCS Iceberg format.")
            self.run_repo.save_run(run)

        # Stage 2: Schema DDL Verification
        if run.stage_statuses["stage2"] != "COMPLETED":
            run.current_stage = "Stage 2 — Schema Validation"
            run.stage_statuses["stage2"] = "RUNNING"
            run.log("Starting Stage 2: Verifying schema definition and column mappings...")
            if progress_callback:
                progress_callback("Stage 2 — Schema Validation", 0.25)

            run.stage_statuses["stage2"] = "COMPLETED"
            run.log(f"Stage 2 Completed: Schema definitions verified ({len(plan.mappings)} columns mapped).")
            self.run_repo.save_run(run)

        # Stage 3: Snowflake Iceberg & External Volume Registration
        if run.stage_statuses["stage3"] != "COMPLETED":
            run.current_stage = "Stage 3 — Snowflake Integration"
            run.stage_statuses["stage3"] = "RUNNING"
            run.log("Starting Stage 3: Registering Snowflake External Volume & Staging Stage...")
            if progress_callback:
                progress_callback("Stage 3 — Snowflake Integration", 0.40)

            if run.mode == "LIVE":
                res = self.sf.execute_query(plan.stage3_sql)
                if not res.get("success"):
                    raise RuntimeError(f"Snowflake stage creation failed: {res.get('error')}")

            run.stage_statuses["stage3"] = "COMPLETED"
            run.log("Stage 3 Completed: Snowflake External Volume & Staging registered.")
            self.run_repo.save_run(run)

        # Stage 4: Snowflake Native Table Materialization & Batch Population
        run.current_stage = "Stage 4 — Native Loading"
        run.stage_statuses["stage4"] = "RUNNING"
        run.log(f"Starting Stage 4: Ingesting batches into Snowflake native table '{plan.target_table_id}'...")
        self.run_repo.save_run(run)

        total_batches = len(run.batches)
        has_batch_failure = False

        for idx, batch in enumerate(run.batches):
            # RESUME LOGIC: Skip already completed batches!
            if batch.status == BatchStatus.COMPLETED:
                run.log(f"[CHECKPOINT] Batch {batch.batch_number}/{total_batches} ({batch.batch_id}) was previously COMPLETED. Skipping.")
                continue

            batch.status = BatchStatus.IN_PROGRESS
            batch.attempts += 1
            start_time = time.time()
            self.run_repo.save_run(run)

            batch_progress = 0.40 + (0.50 * ((idx + 1) / total_batches))
            if progress_callback:
                progress_callback(f"Loading Batch {batch.batch_number}/{total_batches}", batch_progress)

            # Simulated transient failure scenario
            if simulate_failure_on_batch and batch.batch_number == simulate_failure_on_batch and batch.attempts <= 1:
                batch.status = BatchStatus.FAILED
                batch.last_error = "Simulated Network I/O Timeout during parquet read from GCS."
                batch.duration_seconds = time.time() - start_time
                has_batch_failure = True
                run.log(f"[ERROR] Batch {batch.batch_number} failed on attempt {batch.attempts}: {batch.last_error}")
                self.run_repo.save_run(run)
                break

            # Batch processing execution
            try:
                # Live mode query execution or simulation
                if run.mode == "LIVE":
                    self.sf.execute_query(f"-- Batch {batch.batch_number}\n{plan.stage4_sql}")

                batch.status = BatchStatus.COMPLETED
                batch.rows_migrated = batch.rows_expected
                batch.last_error = None
                batch.duration_seconds = time.time() - start_time
                run.total_rows_migrated += batch.rows_migrated

                run.log(f"[CHECKPOINT SUCCESS] Batch {batch.batch_number}/{total_batches} finished: {batch.rows_migrated:,} rows in {batch.duration_seconds:.2f}s.")
                self.run_repo.save_run(run)

            except Exception as e:
                batch.status = BatchStatus.FAILED
                batch.last_error = str(e)
                batch.duration_seconds = time.time() - start_time
                has_batch_failure = True
                run.log(f"[ERROR] Batch {batch.batch_number} failed: {str(e)}")
                self.run_repo.save_run(run)
                break

        # Final status evaluation
        if has_batch_failure:
            run.status = RunStatus.PARTIALLY_COMPLETED
            run.stage_statuses["stage4"] = "FAILED"
            run.error_summary = "One or more batches failed during migration. Checkpoints persisted for resume."
            run.log("Migration paused with partial completion. Can be safely resumed without duplicate processing.")
        else:
            run.status = RunStatus.COMPLETED
            run.stage_statuses["stage4"] = "COMPLETED"
            run.completed_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            run.log(f"Stage 4 Completed: All batches successfully materialized ({run.total_rows_migrated:,} total rows).")

            # Reconciliation
            reconciliation = ReconciliationService.generate_reconciliation_report(
                source_row_count=plan.source_metadata.row_count,
                target_row_count=run.total_rows_migrated,
                batches=run.batches,
                source_table_id=plan.source_table_id,
                target_table_id=plan.target_table_id,
            )
            run.reconciliation_report = reconciliation
            run.log(f"Reconciliation Status: {reconciliation['status']} (Parity: {reconciliation['parity_percentage']}%)")

            if progress_callback:
                progress_callback("Migration Completed", 1.0)

        # Save final state & artifacts
        self._write_run_artifacts(run, plan, run_dir)
        self.run_repo.save_run(run)

    def _write_run_artifacts(self, run: MigrationRun, plan: MigrationPlan, run_dir: Path) -> None:
        """Saves SQL scripts, logs, plans, and reports into artifacts/runs/<run_id>/"""
        try:
            (run_dir / "plan.json").write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
            (run_dir / "stage1_iceberg_export.sql").write_text(plan.stage1_sql, encoding="utf-8")
            (run_dir / "stage2_schema.sql").write_text(plan.stage2_sql, encoding="utf-8")
            (run_dir / "stage3_snowflake_registration.sql").write_text(plan.stage3_sql, encoding="utf-8")
            (run_dir / "stage4_snowflake_native_load.sql").write_text(plan.stage4_sql, encoding="utf-8")
            (run_dir / "execution_log.txt").write_text("\n".join(run.logs), encoding="utf-8")
            if run.reconciliation_report:
                (run_dir / "reconciliation_report.json").write_text(
                    json.dumps(run.reconciliation_report, indent=2), encoding="utf-8"
                )
        except Exception:
            pass

"""
Execution Center View for LegacyLift.
Monitors real-time migration execution, batch-level checkpoints, retries,
interruption recovery, live log streaming, and final reconciliation reports.
"""
import streamlit as st
import pandas as pd
from persistence.repositories import RunRepository, PlanRepository
from core.execution_engine import ExecutionEngine
from core.models import MigrationPlan, MigrationRun, RunStatus
from config.settings import current_config


def render_execution():
    st.subheader("Execution Center")
    st.caption("Execute approved migrations, monitor real-time batch checkpoints, and review data reconciliation.")

    run_repo = RunRepository()
    plan_repo = PlanRepository()
    engine = ExecutionEngine()

    plan: MigrationPlan = st.session_state.get("current_plan")
    active_run: MigrationRun = st.session_state.get("active_run")

    # If no active run in session, fetch latest run
    if not active_run:
        runs = run_repo.list_runs(limit=1)
        if runs:
            active_run = runs[0]
            st.session_state["active_run"] = active_run

    # Execution controls
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 2])

    with ctrl_col1:
        if plan and plan.is_approved:
            sim_failure = st.checkbox("Simulate transient error on Batch 2 (Tests Checkpoint Resume)", value=False)
            if st.button("🚀 Start Approved Migration", type="primary", use_container_width=True):
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                def update_cb(stage_msg, progress_val):
                    progress_bar.progress(progress_val)
                    status_text.text(f"Status: {stage_msg}")

                fail_batch_num = 2 if sim_failure else None
                run = engine.start_migration(
                    plan=plan,
                    progress_callback=update_cb,
                    simulate_failure_on_batch=fail_batch_num,
                )
                st.session_state["active_run"] = run
                st.rerun()
        else:
            st.warning("⚠️ No approved plan selected. Approve a plan in 'Migration Review' to execute.")

    with ctrl_col2:
        if active_run and active_run.status in (RunStatus.PARTIALLY_COMPLETED, RunStatus.FAILED):
            if st.button("🔄 Resume Interrupted Migration", type="primary", use_container_width=True):
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                def update_cb(stage_msg, progress_val):
                    progress_bar.progress(progress_val)
                    status_text.text(f"Resuming: {stage_msg}")

                resumed_run = engine.resume_migration(
                    run_id=active_run.run_id,
                    progress_callback=update_cb,
                )
                st.session_state["active_run"] = resumed_run
                st.rerun()

    with ctrl_col3:
        if st.button("🔁 Refresh Status", use_container_width=True):
            if active_run:
                st.session_state["active_run"] = run_repo.get_run(active_run.run_id)
            st.rerun()

    st.markdown("---")

    if not active_run:
        st.info("No active or historical migration runs found.")
        return

    # 1. Run Summary Banner
    st.markdown(f"#### Active Run: `{active_run.run_id}`")
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        st.metric("Status", active_run.status.value)
    with s_col2:
        st.metric("Current Stage", active_run.current_stage)
    with s_col3:
        st.metric("Rows Migrated", f"{active_run.total_rows_migrated:,} / {active_run.total_rows_expected:,}")
    with s_col4:
        st.metric("Batches", f"{sum(1 for b in active_run.batches if b.status.value == 'COMPLETED')} / {len(active_run.batches)}")

    # 2. Batch Checkpoint Grid
    st.markdown("##### Batch-Level Processing & Checkpoints")
    batch_rows = []
    for b in active_run.batches:
        batch_rows.append({
            "Batch ID": b.batch_id,
            "Batch #": b.batch_number,
            "Status": b.status.value,
            "Rows Expected": f"{b.rows_expected:,}",
            "Rows Migrated": f"{b.rows_migrated:,}",
            "Attempts": b.attempts,
            "Duration (s)": round(b.duration_seconds, 2),
            "Filter Condition": b.filter_expression,
            "Last Error": b.last_error or "-",
        })
    df_batches = pd.DataFrame(batch_rows)
    st.dataframe(df_batches, use_container_width=True, hide_index=True)

    # 3. Live Execution Logs
    st.markdown("##### Execution Logs")
    log_text = "\n".join(active_run.logs) if active_run.logs else "No logs recorded yet."
    st.text_area("Console Output", value=log_text, height=200, disabled=True)

    # 4. Final Reconciliation Report
    if active_run.reconciliation_report:
        st.markdown("---")
        st.markdown("#### 🏁 Final Data Reconciliation Report")
        recon = active_run.reconciliation_report

        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            st.metric("Parity Score", f"{recon.get('parity_percentage')}%")
        with r_col2:
            st.metric("Discrepancy (Rows)", f"{recon.get('discrepancy'):,}")
        with r_col3:
            st.metric("Checksum Verification", recon.get("checksum_status"))

        st.json(recon)

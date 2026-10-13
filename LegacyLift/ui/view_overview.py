"""
Overview Dashboard View for LegacyLift.
Displays environment readiness, system KPIs, and recent historical migration runs.
"""
import streamlit as st
import pandas as pd
from persistence.repositories import RunRepository, PlanRepository
from config.settings import current_config
from ui.styles import render_metric_card, render_status_pill


def render_overview():
    st.subheader("Platform Overview")
    st.caption("Automated BigQuery to Snowflake historical data migration orchestrator.")

    run_repo = RunRepository()
    runs = run_repo.list_runs(limit=10)

    # 1. System Environment Status Pill Row
    mode_color = "🟢" if current_config.execution.mode == "SIMULATION" else "🔷"
    st.markdown(
        f"""
        <div style="background:#f1f5f9; padding:10px 16px; border-radius:8px; margin-bottom:20px; font-size:0.88rem; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <strong>Active Mode:</strong> {mode_color} <b>{current_config.execution.mode}</b>
                <span style="color:#64748b; margin-left:12px;">| Target Catalog: Apache Iceberg on GCS ({current_config.gcp.gcs_bucket})</span>
            </div>
            <div>
                <span style="color:#64748b;">Warehouse:</span> <b>{current_config.snowflake.warehouse}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. KPI Summary Cards
    col1, col2, col3, col4 = st.columns(4)
    total_runs = len(runs)
    completed_runs = sum(1 for r in runs if r.status.value == "COMPLETED")
    failed_runs = sum(1 for r in runs if r.status.value in ("FAILED", "PARTIALLY_COMPLETED"))
    total_rows = sum(r.total_rows_migrated for r in runs)
    success_rate = round((completed_runs / total_runs * 100), 1) if total_runs > 0 else 100.0

    with col1:
        st.markdown(render_metric_card("Total Migrations", f"{total_runs}", "Configured & Executed"), unsafe_allow_html=True)
    with col2:
        st.markdown(render_metric_card("Success Rate", f"{success_rate}%", f"{completed_runs} Successful"), unsafe_allow_html=True)
    with col3:
        st.markdown(render_metric_card("Historical Rows", f"{total_rows:,}", "Reconciled to Snowflake"), unsafe_allow_html=True)
    with col4:
        st.markdown(render_metric_card("Active Issues", f"{failed_runs}", "Checkpoints Persisted"), unsafe_allow_html=True)

    st.markdown("---")

    # 3. Recent Migrations Activity Table
    st.markdown("#### Recent Migration Runs")
    if not runs:
        st.info("No migration runs recorded yet. Start your first migration in the 'New Migration' tab.")
    else:
        table_data = []
        for r in runs:
            table_data.append({
                "Run ID": r.run_id,
                "Source Table": r.source_table_id,
                "Target Table": r.target_table_id,
                "Status": r.status.value,
                "Rows Migrated": f"{r.total_rows_migrated:,}",
                "Started At": r.started_at,
                "Completed At": r.completed_at or "In Progress",
            })
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # 4. Quick Architecture Guidance
    with st.expander("ℹ️ Supported Migration Path Architecture", expanded=False):
        st.markdown("""
        **LegacyLift End-to-End Migration Architecture:**
        1. **Stage 1 — Iceberg Staging:** BigQuery historical data is exported directly into Apache Iceberg / Parquet format inside Google Cloud Storage.
        2. **Stage 2 — Schema Contract:** Data types are normalized and mapped to target Snowflake equivalents with precision and nullability constraints.
        3. **Stage 3 — Snowflake External Integration:** Snowflake External Volume and GCS Storage Integration expose the historical Iceberg metadata without duplicating storage.
        4. **Stage 4 — Native Materialization:** Batch-aware SQL loads historical data into Snowflake native storage with duplicate prevention (`MERGE` / `INSERT`) and conditional DDL.
        """)

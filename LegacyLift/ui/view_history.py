"""
Migration History View for LegacyLift.
Lists persisted runs, batch checkpoints, audit timelines, and historical logs.
"""
import streamlit as st
import pandas as pd
from persistence.repositories import RunRepository


def render_history():
    st.subheader("Migration History & Audit Trail")
    st.caption("Review all historical migration runs, batch progress checkpoints, and final reconciliation reports.")

    run_repo = RunRepository()
    runs = run_repo.list_runs(limit=100)

    if not runs:
        st.info("No prior migration runs recorded in local database.")
        return

    # List of runs
    table_rows = []
    for r in runs:
        table_rows.append({
            "Run ID": r.run_id,
            "Source Table": r.source_table_id,
            "Target Table": r.target_table_id,
            "Mode": r.mode,
            "Status": r.status.value,
            "Rows Migrated": f"{r.total_rows_migrated:,}",
            "Batches": f"{sum(1 for b in r.batches if b.status.value == 'COMPLETED')}/{len(r.batches)}",
            "Started At": r.started_at,
        })

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Run Details & Checkpoint Inspection")
    run_ids = [r.run_id for r in runs]
    selected_run_id = st.selectbox("Select Run ID to Inspect", options=run_ids)

    selected_run = run_repo.get_run(selected_run_id)
    if selected_run:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Status", selected_run.status.value)
        with col2:
            st.metric("Total Migrated", f"{selected_run.total_rows_migrated:,} rows")
        with col3:
            st.metric("Completed At", selected_run.completed_at or "In Progress")

        # Batches table
        st.markdown("##### Batch Checkpoints")
        batch_data = [
            {
                "Batch ID": b.batch_id,
                "Batch #": b.batch_number,
                "Status": b.status.value,
                "Rows Expected": f"{b.rows_expected:,}",
                "Rows Migrated": f"{b.rows_migrated:,}",
                "Attempts": b.attempts,
                "Filter": b.filter_expression,
                "Error": b.last_error or "-",
            }
            for b in selected_run.batches
        ]
        st.dataframe(pd.DataFrame(batch_data), use_container_width=True, hide_index=True)

        with st.expander("📜 View Run Logs", expanded=False):
            st.code("\n".join(selected_run.logs))

"""
Migration Review View for LegacyLift.
Provides deep inspection of resolved metadata, existing target checks,
schema reconciliation, 4-stage SQL tabbed editors, and explicit approval workflow.
"""
import streamlit as st
import pandas as pd
from persistence.repositories import PlanRepository
from core.migration_planner import MigrationPlanner
from core.sql_validator import SQLValidator
from core.models import MigrationPlan


def render_review():
    st.subheader("Migration Plan Review & Approval")
    st.caption("Inspect resolved identifiers, target compatibility, and generated SQL stages before approving execution.")

    plan_repo = PlanRepository()
    planner = MigrationPlanner()

    # Load active plan from session or repository
    plan: MigrationPlan = st.session_state.get("current_plan")
    if not plan:
        recent_plans = plan_repo.list_plans(limit=1)
        if recent_plans:
            plan = recent_plans[0]
            st.session_state["current_plan"] = plan
        else:
            st.info("No active migration plan. Please create one in 'New Migration'.")
            return

    # 1. Header Information & Resolved Identifiers
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.markdown(f"**Source BigQuery Table:** `{plan.source_table_id}`")
        st.caption(f"Rows: {plan.source_metadata.row_count:,} | Partition: {plan.source_metadata.partition_field or 'None'} | Columns: {len(plan.source_metadata.columns)}")
    with res_col2:
        st.markdown(f"**Target Snowflake Table:** `{plan.target_table_id}`")
        st.caption(f"Strategy: **{plan.load_strategy.value}** | Batches Planned: **{len(plan.batches)}**")

    # 2. MANDATORY EXISTING-TARGET STATUS BANNER
    if plan.target_exists:
        st.info(
            f"🎯 **Target Table Detected:** Existing table `{plan.target_table_id}` was found in Snowflake. "
            f"**Redundant CREATE TABLE DDL has been suppressed** to preserve existing database object definitions. "
            f"Data will be loaded via `{plan.load_strategy.value}` strategy."
        )
    else:
        st.success(
            f"🆕 **New Target Table:** `{plan.target_table_id}` does not currently exist. "
            f"A native table creation statement has been included in Stage 4."
        )

    # 3. Schema Comparison & Diff Matrix
    if plan.schema_diff:
        with st.expander("🔍 Target Schema Reconciliation & Compatibility", expanded=not plan.schema_diff.is_safe_to_load):
            st.markdown(f"**Compatibility Status:** `{plan.schema_diff.status.value}`")
            for note in plan.schema_diff.compatibility_notes:
                st.write(f"• {note}")

            if plan.schema_diff.mismatched_types:
                st.error("Data Type Incompatibilities:")
                st.dataframe(pd.DataFrame(plan.schema_diff.mismatched_types), use_container_width=True)

    # 4. Tabbed 4-Stage SQL Review & In-Place Editor
    st.markdown("#### Four-Stage SQL Pipeline")
    tab1, tab2, tab3, tab4 = st.tabs([
        "Stage 1 — Iceberg Export (BQ)",
        "Stage 2 — Schema Blueprint",
        "Stage 3 — Snowflake Stage/Iceberg",
        "Stage 4 — Native Ingestion & Load",
    ])

    with tab1:
        st.caption("BigQuery SQL exporting historical segments into Apache Iceberg / Parquet format on GCS.")
        sql_s1 = st.text_area("Stage 1 SQL", value=plan.stage1_sql, height=260, key="sql_stage1_area")
        if sql_s1 != plan.stage1_sql:
            if st.button("Save & Update Stage 1 SQL"):
                plan = planner.update_plan_sql(plan, "stage1", sql_s1)
                st.session_state["current_plan"] = plan
                st.warning("SQL updated. Any earlier approval has been invalidated. Please re-validate and approve.")
                st.rerun()

    with tab2:
        st.caption("Schema definition DDL blueprint for target table contract.")
        sql_s2 = st.text_area("Stage 2 SQL", value=plan.stage2_sql, height=260, key="sql_stage2_area")
        if sql_s2 != plan.stage2_sql:
            if st.button("Save & Update Stage 2 SQL"):
                plan = planner.update_plan_sql(plan, "stage2", sql_s2)
                st.session_state["current_plan"] = plan
                st.warning("SQL updated. Any earlier approval has been invalidated. Please re-validate and approve.")
                st.rerun()

    with tab3:
        st.caption("Snowflake SQL registering External Volume, GCS Storage Integration, and Staging.")
        sql_s3 = st.text_area("Stage 3 SQL", value=plan.stage3_sql, height=260, key="sql_stage3_area")
        if sql_s3 != plan.stage3_sql:
            if st.button("Save & Update Stage 3 SQL"):
                plan = planner.update_plan_sql(plan, "stage3", sql_s3)
                st.session_state["current_plan"] = plan
                st.warning("SQL updated. Any earlier approval has been invalidated. Please re-validate and approve.")
                st.rerun()

    with tab4:
        st.caption("Snowflake SQL materializing native analytics table (conditional DDL) and loading batch partitions.")
        sql_s4 = st.text_area("Stage 4 SQL", value=plan.stage4_sql, height=260, key="sql_stage4_area")
        if sql_s4 != plan.stage4_sql:
            if st.button("Save & Update Stage 4 SQL"):
                plan = planner.update_plan_sql(plan, "stage4", sql_s4)
                st.session_state["current_plan"] = plan
                st.warning("SQL updated. Any earlier approval has been invalidated. Please re-validate and approve.")
                st.rerun()

    st.markdown("---")

    # 5. SQL Validation & Approval Workflow
    st.markdown("#### Governance & Execution Approval")
    
    if plan.sql_modified_since_approval:
        st.warning("⚠️ Plan SQL has been modified since approval. Approval is required before execution.")

    col_app1, col_app2, col_app3 = st.columns([2, 2, 2])

    with col_app1:
        if st.button("🔍 Validate Plan SQL", use_container_width=True):
            val_result = SQLValidator.validate_all_stages({
                "stage1": plan.stage1_sql,
                "stage2": plan.stage2_sql,
                "stage3": plan.stage3_sql,
                "stage4": plan.stage4_sql,
            })
            if val_result["is_valid"]:
                st.success("✅ All 4 SQL stages passed syntax, dependency, and safety checks.")
            else:
                st.error("Validation issues found:")
                for e in val_result["errors"]:
                    st.error(e)
            for w in val_result["warnings"]:
                st.warning(w)

    with col_app2:
        if not plan.is_approved:
            if st.button("🛡️ Approve Migration Plan", type="primary", use_container_width=True):
                approved, errors = planner.approve_plan(plan, approved_by="Data Engineering Lead")
                if approved:
                    st.success("✅ Plan approved for execution!")
                    st.rerun()
                else:
                    st.error("Approval rejected due to validation errors:")
                    for e in errors:
                        st.error(e)
        else:
            st.success(f"✅ Approved by {plan.approved_by} at {plan.approved_at}")

    with col_app3:
        if plan.is_approved:
            if st.button("⚡ Proceed to Execution Center", use_container_width=True):
                st.session_state["active_nav"] = "Execution Center"
                st.rerun()
        else:
            st.button("⚡ Proceed to Execution Center", disabled=True, use_container_width=True, help="Plan must be approved first.")

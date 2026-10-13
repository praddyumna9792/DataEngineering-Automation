"""
New Migration Form View for LegacyLift.
Enforces minimal input: only two mandatory table names, with optional mapping and schema uploads.
"""
import streamlit as st
from core.migration_planner import MigrationPlanner
from core.models import LoadStrategy
from config.settings import current_config


def render_new_migration():
    st.subheader("New Historical Migration")
    st.caption("Provide source and target table names. All infrastructure, schema, and storage details are automatically discovered.")

    planner = MigrationPlanner()

    # Form with 2 mandatory inputs
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            source_table_input = st.text_input(
                "BigQuery Source Table Name *",
                value=st.session_state.get("input_source_table", "customer_history"),
                help="Table name to search in configured BigQuery datasets (e.g., customer_history)",
            )
        with col2:
            target_table_input = st.text_input(
                "Snowflake Target Table Name *",
                value=st.session_state.get("input_target_table", "CUSTOMER_HISTORY"),
                help="Target table name in Snowflake (e.g., CUSTOMER_HISTORY)",
            )

    # Quick Sample Presets (for instant evaluation in simulation mode)
    if current_config.execution.mode == "SIMULATION":
        st.caption("Quick Test Presets (Simulation Catalog):")
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        if p_col1.button("Case B: Existing Target (customer_history)", use_container_width=True):
            st.session_state["input_source_table"] = "customer_history"
            st.session_state["input_target_table"] = "CUSTOMER_HISTORY"
            st.rerun()
        if p_col2.button("Case A: New Target (orders_archive)", use_container_width=True):
            st.session_state["input_source_table"] = "orders_archive"
            st.session_state["input_target_table"] = "ORDERS_ARCHIVE"
            st.rerun()
        if p_col3.button("Ambiguous Source (legacy_transactions)", use_container_width=True):
            st.session_state["input_source_table"] = "legacy_transactions"
            st.session_state["input_target_table"] = "LEGACY_TRANSACTIONS"
            st.rerun()
        if p_col4.button("Incompatible Target (employee_records)", use_container_width=True):
            st.session_state["input_source_table"] = "employee_records"
            st.session_state["input_target_table"] = "EMPLOYEE_RECORDS"
            st.rerun()

    st.markdown("---")

    # Optional Uploads Section
    st.markdown("#### Optional Specification Files")
    st.caption("Upload custom mapping or schema definitions if you want to override automated metadata discovery.")

    up_col1, up_col2 = st.columns(2)
    with up_col1:
        mapping_file = st.file_uploader(
            "Upload Mapping Sheet (CSV or XLSX)",
            type=["csv", "xlsx", "xls"],
            help="Custom source-to-target column mappings and transformation rules.",
        )
    with up_col2:
        schema_file = st.file_uploader(
            "Upload Schema Definition (JSON or CSV)",
            type=["json", "csv"],
            help="Pre-defined schema specification for column types and constraints.",
        )

    # Advanced Scope Overrides (Foldable)
    with st.expander("⚙️ Advanced Discovery Scopes & Options", expanded=False):
        adv_col1, adv_col2 = st.columns(2)
        with adv_col1:
            source_scope = st.text_input(
                "BigQuery Dataset Search Scope",
                value=st.session_state.get("adv_source_scope", ""),
                placeholder="Leave blank to search all authorized datasets",
            )
        with adv_col2:
            target_scope = st.text_input(
                "Snowflake Schema Search Scope",
                value=st.session_state.get("adv_target_scope", ""),
                placeholder=f"Default: {current_config.snowflake.default_database}.{current_config.snowflake.default_schema}",
            )
        strategy_override = st.selectbox(
            "Load Strategy Override (Default is Auto-Determined)",
            options=["AUTO", "INITIAL_LOAD", "APPEND", "MERGE", "CONTROLLED_REFRESH"],
            index=0,
        )
        confirm_refresh = False
        if strategy_override == "CONTROLLED_REFRESH":
            confirm_refresh = st.checkbox("⚠️ Explicitly confirm TRUNCATE / Controlled Refresh for target table", value=False)

    st.markdown("<br>", unsafe_allow_html=True)

    # Submit Action
    if st.button("🚀 Discover Metadata & Plan Migration", type="primary", use_container_width=True):
        if not source_table_input.strip() or not target_table_input.strip():
            st.error("Please enter both BigQuery source and Snowflake target table names.")
            return

        with st.spinner("Discovering metadata, analyzing existing targets, and compiling migration plan..."):
            # Read files if uploaded
            mapping_bytes = mapping_file.read() if mapping_file else None
            mapping_name = mapping_file.name if mapping_file else None

            schema_text = schema_file.read().decode("utf-8") if schema_file else None
            schema_name = schema_file.name if schema_file else None

            load_strat = None if strategy_override == "AUTO" else LoadStrategy(strategy_override)

            plan, diagnostics = planner.create_plan(
                source_table_name=source_table_input.strip(),
                target_table_name=target_table_input.strip(),
                source_scope=source_scope.strip() if source_scope else None,
                target_scope=target_scope.strip() if target_scope else None,
                uploaded_mapping_bytes=mapping_bytes,
                mapping_filename=mapping_name,
                uploaded_schema_text=schema_text,
                schema_filename=schema_name,
                load_strategy_override=load_strat,
                confirm_overwrite=confirm_refresh,
            )

            if plan:
                st.session_state["current_plan"] = plan
                st.session_state["current_plan_id"] = plan.plan_id
                st.success(f"Migration plan created successfully! (Plan ID: {plan.plan_id})")
                st.info("Navigating to 'Migration Review' tab...")
                st.session_state["active_nav"] = "Migration Review"
                st.rerun()
            else:
                st.error("Migration Planning Failed:")
                for err in diagnostics.get("errors", []):
                    st.error(f"• {err}")
                if diagnostics.get("source_status") == "AMBIGUOUS":
                    st.warning("Please specify the exact dataset scope above to resolve ambiguous table names.")

"""
Settings and Cloud Environment Setup View for LegacyLift.
Allows toggling between Simulation and Live Cloud modes, configuring connection profiles,
and executing live connection diagnostics.
"""
import streamlit as st
from config.settings import current_config
from connectors.bigquery_connector import BigQueryConnector
from connectors.snowflake_connector import SnowflakeConnector
from connectors.gcs_connector import GCSConnector


def render_settings():
    st.subheader("Environment Settings & Cloud Profiles")
    st.caption("Configure cloud credentials, discovery search scopes, storage integrations, and batch execution limits.")

    # 1. Mode Switcher
    st.markdown("#### Execution Mode")
    mode_options = ["SIMULATION", "LIVE"]
    selected_mode = st.radio(
        "Platform Execution Mode",
        options=mode_options,
        index=0 if current_config.execution.mode == "SIMULATION" else 1,
        help="SIMULATION mode uses deterministic offline catalogs. LIVE mode executes real queries on GCP and Snowflake.",
        horizontal=True,
    )
    if selected_mode != current_config.execution.mode:
        current_config.execution.mode = selected_mode
        st.success(f"Switched execution mode to {selected_mode}!")

    st.markdown("---")

    # 2. Connection Diagnostics
    st.markdown("#### Cloud Diagnostics & Connection Testing")
    diag_col1, diag_col2, diag_col3 = st.columns(3)

    with diag_col1:
        if st.button("🧪 Test BigQuery Access", use_container_width=True):
            bq = BigQueryConnector(mode=current_config.execution.mode)
            res = bq.test_connection()
            if res.get("success"):
                st.success(f"✅ {res.get('message')}")
            else:
                st.error(f"❌ {res.get('message')}")
                if "remediation" in res:
                    st.caption(f"Remediation: {res['remediation']}")

    with diag_col2:
        if st.button("🧪 Test Snowflake Access", use_container_width=True):
            sf = SnowflakeConnector(mode=current_config.execution.mode)
            res = sf.test_connection()
            if res.get("success"):
                st.success(f"✅ {res.get('message')}")
            else:
                st.error(f"❌ {res.get('message')}")
                if "remediation" in res:
                    st.caption(f"Remediation: {res['remediation']}")

    with diag_col3:
        if st.button("🧪 Test GCS Bucket Access", use_container_width=True):
            gcs = GCSConnector(mode=current_config.execution.mode)
            res = gcs.check_bucket_access(current_config.gcp.gcs_bucket)
            if res.get("success"):
                st.success(f"✅ {res.get('message')}")
            else:
                st.error(f"❌ {res.get('message')}")

    st.markdown("---")

    # 3. Cloud Profiles Configuration
    tab_gcp, tab_sf, tab_batch = st.tabs(["Google Cloud Platform", "Snowflake", "Batch & Engine Tuning"])

    with tab_gcp:
        st.markdown("##### GCP & BigQuery Identity")
        gcp_col1, gcp_col2 = st.columns(2)
        with gcp_col1:
            current_config.gcp.project_id = st.text_input("GCP Project ID", value=current_config.gcp.project_id)
            current_config.gcp.default_dataset = st.text_input("Default Search Dataset", value=current_config.gcp.default_dataset)
            current_config.gcp.location = st.text_input("BigQuery Location", value=current_config.gcp.location)
        with gcp_col2:
            current_config.gcp.gcs_bucket = st.text_input("GCS Staging Bucket URI", value=current_config.gcp.gcs_bucket)
            current_config.gcp.iceberg_catalog = st.text_input("Iceberg Catalog Identifier", value=current_config.gcp.iceberg_catalog)
            current_config.gcp.dataproc_cluster = st.text_input("Dataproc Cluster Name", value=current_config.gcp.dataproc_cluster)

    with tab_sf:
        st.markdown("##### Snowflake Connection & Integrations")
        sf_col1, sf_col2 = st.columns(2)
        with sf_col1:
            current_config.snowflake.account = st.text_input("Account Identifier", value=current_config.snowflake.account)
            current_config.snowflake.user = st.text_input("Username", value=current_config.snowflake.user)
            current_config.snowflake.role = st.text_input("Role", value=current_config.snowflake.role)
            current_config.snowflake.warehouse = st.text_input("Warehouse", value=current_config.snowflake.warehouse)
        with sf_col2:
            current_config.snowflake.default_database = st.text_input("Default Database", value=current_config.snowflake.default_database)
            current_config.snowflake.default_schema = st.text_input("Default Schema", value=current_config.snowflake.default_schema)
            current_config.snowflake.external_volume = st.text_input("External Volume Name", value=current_config.snowflake.external_volume)
            current_config.snowflake.storage_integration = st.text_input("Storage Integration Name", value=current_config.snowflake.storage_integration)

    with tab_batch:
        st.markdown("##### Batch Processing Limits & Checkpoint Intervals")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            current_config.execution.default_batch_size = st.number_input(
                "Default Batch Size (Rows)",
                value=current_config.execution.default_batch_size,
                step=50_000,
            )
            current_config.execution.max_concurrency = st.number_input(
                "Max Concurrent Batch Tasks",
                value=current_config.execution.max_concurrency,
                min_value=1,
                max_value=16,
            )
        with b_col2:
            current_config.execution.retry_limit = st.number_input(
                "Batch Retry Limit",
                value=current_config.execution.retry_limit,
                min_value=1,
                max_value=10,
            )
            current_config.execution.validate_row_counts = st.checkbox(
                "Enforce Strict End-of-Run Row Count Reconciliation",
                value=current_config.execution.validate_row_counts,
            )

    if st.button("Save Settings to Profile", type="primary"):
        st.success("Configuration settings updated successfully.")

"""
Generated Artifacts Explorer View for LegacyLift.
Allows inspection and download of SQL stages, Airflow DAGs, Dataproc scripts, dbt projects, and logs.
"""
import streamlit as st
import json
from core.models import MigrationPlan
from generators.airflow_generator import AirflowGenerator
from generators.dataproc_generator import DataprocGenerator
from generators.dbt_generator import DbtGenerator
from persistence.repositories import PlanRepository


def render_artifacts():
    st.subheader("Generated Pipeline Artifacts")
    st.caption("Inspect and export production pipeline definitions, DAGs, Spark jobs, dbt transformations, and execution reports.")

    plan_repo = PlanRepository()
    plan: MigrationPlan = st.session_state.get("current_plan")

    if not plan:
        plans = plan_repo.list_plans(limit=1)
        if plans:
            plan = plans[0]
        else:
            st.info("No migration plan available. Create and approve a plan in 'New Migration' first.")
            return

    # Tabs for artifact categories
    tab_sql, tab_airflow, tab_spark, tab_dbt, tab_reports = st.tabs([
        "📜 4-Stage SQL",
        "🌬️ Airflow DAG",
        "⚡ Dataproc PySpark",
        "🧱 dbt Project",
        "📊 Execution & Audit",
    ])

    with tab_sql:
        st.markdown("##### Consolidated 4-Stage SQL Pipeline")
        full_sql = f"""-- ============================================================================
-- LEGACYLIFT HISTORICAL MIGRATION SCRIPT
-- Plan ID: {plan.plan_id}
-- Source: {plan.source_table_id}
-- Target: {plan.target_table_id}
-- ============================================================================

{plan.stage1_sql}

{plan.stage2_sql}

{plan.stage3_sql}

{plan.stage4_sql}
"""
        st.code(full_sql, language="sql")
        st.download_button(
            label="💾 Download Full Migration SQL",
            data=full_sql,
            file_name=f"legacylift_{plan.source_metadata.table_name}_migration.sql",
            mime="text/plain",
        )

    with tab_airflow:
        st.markdown("##### Production Apache Airflow DAG")
        dag_code = AirflowGenerator.generate_dag_code(plan)
        st.code(dag_code, language="python")
        st.download_button(
            label="💾 Download Airflow DAG (.py)",
            data=dag_code,
            file_name=f"dag_migrate_{plan.source_metadata.table_name}.py",
            mime="text/x-python",
        )

    with tab_spark:
        st.markdown("##### Dataproc PySpark Iceberg Migration Job")
        spark_code = DataprocGenerator.generate_pyspark_job(plan)
        st.code(spark_code, language="python")
        st.download_button(
            label="💾 Download PySpark Script (.py)",
            data=spark_code,
            file_name=f"spark_iceberg_migrate_{plan.source_metadata.table_name}.py",
            mime="text/x-python",
        )

    with tab_dbt:
        st.markdown("##### Snowflake Downstream dbt Project")
        dbt_files = DbtGenerator.generate_dbt_project(plan)
        for path, content in dbt_files.items():
            with st.expander(f"📄 {path}", expanded=(path == "dbt_project.yml")):
                lang = "yaml" if path.endswith((".yml", ".yaml")) else "sql"
                st.code(content, language=lang)
                st.download_button(
                    label=f"Download {path.split('/')[-1]}",
                    data=content,
                    file_name=path.split('/')[-1],
                    mime="text/plain",
                    key=f"dl_dbt_{path}",
                )

    with tab_reports:
        st.markdown("##### Plan Specification & Metadata Manifest")
        plan_json_str = json.dumps(plan.to_dict(), indent=2)
        st.json(plan.to_dict())
        st.download_button(
            label="💾 Download Plan Specification (.json)",
            data=plan_json_str,
            file_name=f"plan_{plan.plan_id}.json",
            mime="application/json",
        )

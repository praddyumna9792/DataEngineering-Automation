"""
LegacyLift — Automated Historical Data Migration Platform
Primary Streamlit Application Entrypoint.
"""
import sys
from pathlib import Path

# Ensure application root is in Python module search path
APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import streamlit as st
from config.settings import current_config
from ui.styles import CUSTOM_CSS
from ui.view_overview import render_overview
from ui.view_new_migration import render_new_migration
from ui.view_review import render_review
from ui.view_execution import render_execution
from ui.view_artifacts import render_artifacts
from ui.view_history import render_history
from ui.view_settings import render_settings

# Page Config
st.set_page_config(
    page_title="LegacyLift — Historical Migration Platform",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom styles
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def main():
    # Sidebar Brand & Navigation
    with st.sidebar:
        st.markdown(
            """
            <div class="brand-container">
                <span style="font-size:2rem;">🚀</span>
                <div>
                    <h2 class="brand-title">LegacyLift</h2>
                    <p class="brand-tagline">Move Historical Data. Automate the Complexity.</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        nav_options = [
            "Overview",
            "New Migration",
            "Migration Review",
            "Execution Center",
            "Generated Artifacts",
            "Migration History",
            "Settings",
        ]

        active_nav = st.session_state.get("active_nav", "Overview")
        current_index = nav_options.index(active_nav) if active_nav in nav_options else 0

        selected_page = st.radio(
            "Navigation",
            options=nav_options,
            index=current_index,
            label_visibility="collapsed",
        )
        st.session_state["active_nav"] = selected_page

        st.markdown("---")

        # Sidebar Environment Badges
        st.markdown("##### Environment Status")
        if current_config.execution.mode == "SIMULATION":
            st.success("🟢 Mode: Simulation (Offline)")
        else:
            st.info("🔷 Mode: Live Cloud")

        st.caption(f"**GCP Project:** `{current_config.gcp.project_id}`")
        st.caption(f"**Snowflake WH:** `{current_config.snowflake.warehouse}`")
        st.caption(f"**GCS Iceberg:** `{current_config.gcp.gcs_bucket.split('//')[-1]}`")

        st.markdown("---")
        st.caption("LegacyLift v1.0.0 — Enterprise Data Migration")

    # Routing to selected view
    if selected_page == "Overview":
        render_overview()
    elif selected_page == "New Migration":
        render_new_migration()
    elif selected_page == "Migration Review":
        render_review()
    elif selected_page == "Execution Center":
        render_execution()
    elif selected_page == "Generated Artifacts":
        render_artifacts()
    elif selected_page == "Migration History":
        render_history()
    elif selected_page == "Settings":
        render_settings()


if __name__ == "__main__":
    main()

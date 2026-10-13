#!/usr/bin/env bash
set -e

echo "==================================================="
echo "Starting LegacyLift - Historical Migration Platform"
echo "==================================================="
echo "Mode: SIMULATION (Default) / LIVE (Configurable)"
echo ""

python -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false

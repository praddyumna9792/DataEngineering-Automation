@echo off
echo Starting LegacyLift from workspace root...
cd /d "%~dp0LegacyLift"
python -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
pause

@echo off
REM TuffWraps Marketing Attribution Dashboard
REM Run this to start the Streamlit dashboard

cd /d "E:\VS Code\Marketing Ads\dashboard"

echo Starting TuffWraps Attribution Dashboard...
echo.
echo Dashboard will open at: http://localhost:8501
echo.

python -m streamlit run app.py

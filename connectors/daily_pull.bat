@echo off
REM Daily Data Pull for TuffWraps Marketing Attribution
REM Schedule this to run at 8:00am EST daily

cd /d "E:\VS Code\Marketing Ads\connectors"

echo ============================================
echo TuffWraps Daily Data Pull - %date% %time%
echo ============================================

REM Pull all data
python pull_all_data.py

REM Generate CAM report
python data_aggregator.py

echo ============================================
echo Daily pull complete - %time%
echo ============================================

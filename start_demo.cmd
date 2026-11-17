@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B -X utf8 run_pipeline.py demo
) else (
  py -3.12 -B -X utf8 run_pipeline.py demo
)
pause

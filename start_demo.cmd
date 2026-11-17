@echo off
cd /d "%~dp0"
if exist ".runtime\python_embed\python.exe" (
  ".runtime\python_embed\python.exe" -B -X utf8 run_pipeline.py demo
) else (
  py -3 run_pipeline.py demo
)
pause

@echo off
REM TLL 에이전트를 30분마다 자동 수집(--watch). 이 창을 닫으면 멈춥니다.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m tll.loop.loop --watch
) else (
  python -m tll.loop.loop --watch
)

@echo off
REM 자동 시작 해제
schtasks /Delete /TN "TLL Agent" /F
echo 자동 시작 해제됨.
pause

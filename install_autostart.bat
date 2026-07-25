@echo off
REM 이 파일을 '더블클릭' 한 번 → 로그인할 때마다 TLL 에이전트가 백그라운드로 자동 시작됩니다.
schtasks /Create /TN "TLL Agent" /TR "\"%~dp0run_agent.bat\"" /SC ONLOGON /RL LIMITED /F
if %errorlevel%==0 (echo [완료] 자동 시작 등록됨. 다음 로그인부터 TLL 에이전트가 알아서 돕니다.) else (echo [실패] 관리자 권한으로 다시 시도해 보세요.)
pause

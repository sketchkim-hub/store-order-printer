@echo off
cd /d "%~dp0tests"
for %%f in (test_*.py) do (
  echo == %%f
  python %%f
  if errorlevel 1 goto fail
)
echo ALL TESTS PASSED
pause
exit /b 0
:fail
echo TEST FAILED
pause
exit /b 1

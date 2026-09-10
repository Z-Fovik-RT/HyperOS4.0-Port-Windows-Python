@echo off
setlocal
pushd "%~dp0"

set "PYTHON_EXE="
for %%P in ("%LocalAppData%\Programs\Python\Python312\python.exe" "%LocalAppData%\Programs\Python\Python314\python.exe" "%ProgramFiles%\Python312\python.exe" "%ProgramFiles%\Python314\python.exe") do (
  if not defined PYTHON_EXE if exist %%~P set "PYTHON_EXE=%%~P"
)
if not defined PYTHON_EXE for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE (
  echo Python 3.10+ was not found.
  echo Install it with: winget install Python.Python.3.12
  popd
  exit /b 9009
)

"%PYTHON_EXE%" --version
"%PYTHON_EXE%" main.py %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

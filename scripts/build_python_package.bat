@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
pushd "%ROOT_DIR%" || exit /b 1

where uv >nul 2>&1
if errorlevel 1 (
  echo error: uv is not on PATH ^(install from https://docs.astral.sh/uv/^)
  popd
  exit /b 1
)

if exist dist rmdir /s /q dist

uv build
set "EXITCODE=%ERRORLEVEL%"
popd
exit /b %EXITCODE%

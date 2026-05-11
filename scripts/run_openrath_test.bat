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

echo syncing dev dependency group...
uv sync --dev
if errorlevel 1 (
  set "EXITCODE=%ERRORLEVEL%"
  popd
  exit /b %EXITCODE%
)

echo running flake8...
uv run flake8 src tests
if errorlevel 1 (
  set "EXITCODE=%ERRORLEVEL%"
  popd
  exit /b %EXITCODE%
)

echo running mypy...
uv run mypy --no-incremental
if errorlevel 1 (
  set "EXITCODE=%ERRORLEVEL%"
  popd
  exit /b %EXITCODE%
)

echo running pytest...
uv run pytest %*
set "EXITCODE=%ERRORLEVEL%"
popd
exit /b %EXITCODE%

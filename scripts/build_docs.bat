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

echo syncing dev + docs dependency groups...
uv sync --group dev --group docs
if errorlevel 1 (
  set "EXITCODE=%ERRORLEVEL%"
  popd
  exit /b %EXITCODE%
)

echo building HTML under docs/_build/html ...
uv run sphinx-build -M html docs/source docs/_build %*
set "EXITCODE=%ERRORLEVEL%"
popd
exit /b %EXITCODE%

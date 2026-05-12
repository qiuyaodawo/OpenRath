@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Sanity-check optional OpenSandbox: Python extra imports and server /health endpoint.
rem Uses OPEN_SANDBOX_DOMAIN from the environment or .env (default 127.0.0.1:8080).

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." || exit /b 1

where uv >nul 2>&1
if errorlevel 1 (
  echo error: uv is not on PATH ^(https://docs.astral.sh/uv/^)
  popd
  exit /b 1
)

where curl >nul 2>&1
if errorlevel 1 (
  echo error: curl is not on PATH
  popd
  exit /b 1
)

for /f "delims=" %%D in ('uv run python -c "from pathlib import Path; import os; from dotenv import load_dotenv; p=Path('.env'); load_dotenv(p) if p.is_file() else None; print(os.getenv('OPEN_SANDBOX_DOMAIN','127.0.0.1:8080'))"') do set "OSB_DOMAIN=%%D"

set "BASE_URL=http://!OSB_DOMAIN!"
set "HEALTH_URL=!BASE_URL!/health"

echo repo root: %CD%
echo OpenSandbox API base: !BASE_URL!

if exist ".sandbox.toml" (
  echo found .sandbox.toml ^(server config; client uses OPEN_SANDBOX_DOMAIN^)
) else (
  echo note: no .sandbox.toml in repo root ^(optional for local server^)
)

echo.
echo [1/2] optional dependency: opensandbox ^(uv --extra opensandbox^)
uv run --extra opensandbox python -c "import opensandbox"
if errorlevel 1 (
  echo error: cannot import opensandbox. Try: uv sync --extra opensandbox
  popd
  exit /b 1
)
echo       ok

echo.
echo [2/2] HTTP GET !HEALTH_URL!
curl -sS -f -o "%TEMP%\opensandbox-health-body.txt" --connect-timeout 5 --max-time 15 "!HEALTH_URL!"
if errorlevel 1 (
  echo error: GET /health failed ^(is opensandbox-server running?^)
  echo hint: run scripts\launch_opensandbox.bat or set OPEN_SANDBOX_DOMAIN to a reachable host:port.
  popd
  exit /b 1
)
echo       ok ^(200^)
if exist "%TEMP%\opensandbox-health-body.txt" for %%F in ("%TEMP%\opensandbox-health-body.txt") do if %%~zF gtr 0 type "%TEMP%\opensandbox-health-body.txt"

echo.
echo OpenSandbox check passed.
popd
exit /b 0

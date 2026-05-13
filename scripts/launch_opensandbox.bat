@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
pushd "%ROOT_DIR%" || exit /b 1
set "CONFIG_PATH=%CD%\.sandbox.toml"
rem Packaged examples: docker ^| docker-zh ^| k8s ^| k8s-zh (default: docker).
if not defined SANDBOX_INIT_EXAMPLE set "SANDBOX_INIT_EXAMPLE=docker"

where docker >nul 2>&1
if errorlevel 1 (
  echo error: docker is not on PATH
  popd
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo error: Docker daemon is not running ^(or permission denied^).
  popd
  exit /b 1
)

echo Checking Docker containers using OpenSandbox images...
docker ps -a | findstr /i opensandbox
if errorlevel 1 (
  echo   ^(none found^)
)

where uv >nul 2>&1
if errorlevel 1 (
  echo error: uv is not on PATH ^(install from https://docs.astral.sh/uv/^)
  popd
  exit /b 1
)

echo syncing optional dependency opensandbox...
uv sync --extra opensandbox
if errorlevel 1 (
  set "EXITCODE=!ERRORLEVEL!"
  popd
  exit /b !EXITCODE!
)

if exist "%CONFIG_PATH%" (
  echo using existing config: %CONFIG_PATH%
) else (
  echo creating %CONFIG_PATH% from packaged example: %SANDBOX_INIT_EXAMPLE%
  uv run opensandbox-server init-config --example %SANDBOX_INIT_EXAMPLE% "%CONFIG_PATH%"
  if errorlevel 1 (
    set "EXITCODE=!ERRORLEVEL!"
    popd
    exit /b !EXITCODE!
  )
)

if not defined OPENSANDBOX_INSECURE_SERVER set "OPENSANDBOX_INSECURE_SERVER=YES"

echo starting opensandbox-server ^(Ctrl+C to stop^)...
uv run opensandbox-server --config "%CONFIG_PATH%"
set "EXITCODE=!ERRORLEVEL!"
popd
exit /b !EXITCODE!

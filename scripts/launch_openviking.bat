@echo off
setlocal enabledelayedexpansion
rem Launch a local OpenViking server for memory-plane integration tests.
rem Honors OPEN_VIKING_CONFIG (path to ov.conf; default %USERPROFILE%\.openviking\ov.conf).

pushd "%~dp0\.."

where uv >nul 2>&1
if errorlevel 1 (
    echo error: uv is not on PATH ^(install from https://docs.astral.sh/uv/^) 1>&2
    popd
    exit /b 1
)

if "%OPEN_VIKING_CONFIG%"=="" (
    set CONFIG_PATH=%USERPROFILE%\.openviking\ov.conf
) else (
    set CONFIG_PATH=%OPEN_VIKING_CONFIG%
)

echo syncing optional dependency openviking...
uv sync --extra openviking
if errorlevel 1 (
    popd
    exit /b 1
)

if not exist "%CONFIG_PATH%" (
    echo creating default config at %CONFIG_PATH%
    for %%I in ("%CONFIG_PATH%") do set CONFIG_DIR=%%~dpI
    if not exist "!CONFIG_DIR!" mkdir "!CONFIG_DIR!"
    > "%CONFIG_PATH%" echo # OpenViking minimal local config.
    >> "%CONFIG_PATH%" echo host = "127.0.0.1"
    >> "%CONFIG_PATH%" echo port = 1933
)

echo using config: %CONFIG_PATH%
echo starting openviking-server (Ctrl+C to stop)...

uv run --extra openviking openviking-server --config "%CONFIG_PATH%"
if errorlevel 1 (
    uv run --extra openviking python -m openviking.server --config "%CONFIG_PATH%"
)

popd
endlocal

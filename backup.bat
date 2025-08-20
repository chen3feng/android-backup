@echo off
setlocal enabledelayedexpansion

set HAS_ERROR=0

call :CheckInstall python3
call :CheckInstall adb
call :CheckInstall ffmpeg
call :CheckInstall exiftool

if "%HAS_ERROR%" == "1" (
    Missing required software packages.
    exit /b 1
)

:: Initialize
set PYTHON=

:: Define a helper function (label) to check files
for %%C in (python3 python) do (
    for /f "usebackq delims=" %%F in (`where %%C 2^>nul`) do (
        :: Get file size using PowerShell
        for /f "usebackq delims=" %%S in (`powershell -nologo -noprofile -command "(Get-Item '%%F').Length" 2^>nul`) do (
            if not "%%S"=="0" (
                set "PYTHON=%%F"
                goto :done
            )
        )
    )
)

:done
if defined PYTHON (
    echo Found Python: %PYTHON%
    %PYTHON% %~dp0%backup.py
) else (
    echo No valid python executable found.
)

endlocal & set "PYTHON=%PYTHON%"

goto :EOF

:CheckInstall
    where %1 >nul 2>nul
    if not %errorlevel%==0 (
        echo Not found %1, please run setup.bat or install manually.
        set HAS_ERROR=1
    )
exit /b 0

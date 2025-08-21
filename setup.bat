@echo off

setlocal enabledelayedexpansion

set "ERROR_PACKAGES="

call :CheckOrInstallPython3
call :CheckOrInstall adb --id=Google.PlatformTools  -e
call :CheckOrInstall ffmpeg
call :CheckOrInstall exiftool ExifTool

if "%ERROR_PACKAGES%" == "" (
    echo Setup success.
) else (
    echo Error install%ERROR_PACKAGES%.
)

endlocal
goto :EOF

:CheckOrInstall
    where %1 >nul 2>nul
    if %errorlevel%==0 (
        echo Found %1:
        where %1
    ) else (
        echo Install %1
        if  "%2"=="" (
            winget install %1
        ) else (
            shift
            winget install %*
        )
        if %errorlevel%==0 (
            echo %1 is installed
        ) else (
            echo Fail to install %1
            set "ERROR_PACKAGES=!ERROR_PACKAGES! %1"
            exit /b 1
        )
    )
exit /b 0

:CheckOrInstallPython3
    python3 --version >nul 2>nul
    if %errorlevel%==0 (
        echo Found %1:
        where %1
    ) else (
        echo Install python3
        winget install python3
        if "%errorlevel%" == "-1978335189" (
            echo python3 is already installed
        ) else if "%errorlevel%" == "9009" (
            echo python3 is already installed
        ) else if "%errorlevel%" == "0" (
            echo python3 is already installed
        ) else (
            echo Fail to install python3
            set "ERROR_PACKAGES=!ERROR_PACKAGES! python3"
            exit /b 1
        )
    )
exit /b 0

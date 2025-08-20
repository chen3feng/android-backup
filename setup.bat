@echo off

call :CheckOrInstall python3
call :CheckOrInstall ffmpeg
call :CheckOrInstall exiftool ExifTool

echo Success

goto :EOF

:CheckOrInstall
    where %1 >nul 2>nul
    if %errorlevel%==0 (
        echo Found %1:
        where %1
    ) else (
        if  "%2"=="" (
            winget install %1
        ) else {
            shift
            winget install %*
        }
        if %errorlevel%==0 (
            echo %1 is installed
        ) else {
            exit /b 1
        }
    )
exit /b 0

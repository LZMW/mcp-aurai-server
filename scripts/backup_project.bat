@echo off
REM Project Backup Script
REM Encoding: UTF-8 with BOM

chcp 65001 >nul

set YEAR=%date:~0,4%
set MONTH=%date:~5,2%
set DAY=%date:~8,2%
set HOUR=%time:~0,2%
set MINUTE=%time:~3,2%
set SECOND=%time:~6,2%
set TIMESTAMP=%YEAR%%MONTH%%DAY%-%HOUR%%MINUTE%%SECOND%

echo.
echo ========================================
echo    MCP Aurai Advisor Backup
echo ========================================
echo.

REM Create backup directory
if not exist "D:\backups" mkdir "D:\backups"

echo Creating project backup...
echo.

REM Change to project directory
cd /d D:\aimcpkaifa

REM Create temporary directory for excluded files
if exist ".backup_temp" rmdir /s /q ".backup_temp"
mkdir ".backup_temp"

REM Copy files to temp directory (excluding venv and cache)
xcopy /E /I /Q /Y src ".backup_temp\src" >nul 2>&1
xcopy /E /I /Q /Y tests ".backup_temp\tests" >nul 2>&1
xcopy /E /I /Q /Y tools ".backup_temp\tools" >nul 2>&1
xcopy /E /I /Q /Y scripts ".backup_temp\scripts" >nul 2>&1
xcopy /E /I /Q /Y docs ".backup_temp\docs" >nul 2>&1
xcopy /E /I /Q /Y build ".backup_temp\build" >nul 2>&1
copy /Y *.md ".backup_temp\" >nul 2>&1
copy /Y *.toml ".backup_temp\" >nul 2>&1
copy /Y *.ini ".backup_temp\" >nul 2>&1
copy /Y .env.example ".backup_temp\" >nul 2>&1

REM Create ZIP archive using PowerShell
powershell -Command "Compress-Archive -Path '.backup_temp' -DestinationPath 'D:\backups\mcp-aurai-advisor-%TIMESTAMP%.zip' -Force"

REM Cleanup temporary directory
rmdir /s /q ".backup_temp"

echo.
echo ========================================
echo    Backup Completed!
echo ========================================
echo.
echo Backup location: D:\backups\
echo File name: mcp-aurai-advisor-%TIMESTAMP%.zip
echo.

pause

@echo off
REM ========================================================================
REM Aurai Control Center - EXE 打包脚本
REM ========================================================================

echo.
echo ========================================
echo   Aurai Control Center Builder
echo ========================================
echo.

REM 检查 PyInstaller 是否已安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo [X] Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo [✓] PyInstaller found
echo.

REM 清理旧的构建
echo [*] Cleaning old build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "AuraiControlCenter.spec" del /f "AuraiControlCenter.spec"

echo [✓] Clean completed
echo.

REM 构建 EXE
echo [*] Building EXE...
echo.

pyinstaller ^
    --noconsole ^
    --onefile ^
    --name AuraiControlCenter ^
    --icon=NONE ^
    --add-data "src;src" ^
    --hidden-import=mcp_aurai.config ^
    --hidden-import=mcp_aurai.llm ^
    --hidden-import=mcp_aurai.server ^
    --hidden-import=mcp_aurai.prompts ^
    --hidden-import=tkinter ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=tkinter.scrolledtext ^
    --hidden-import=json ^
    --hidden-import=pathlib ^
    --hidden-import=subprocess ^
    --hidden-import=threading ^
    --hidden-import=datetime ^
    --hidden-import=typing ^
    --hidden-import=pydantic ^
    --hidden-import=zhipuai ^
    --hidden-import=openai ^
    --hidden-import=anthropic ^
    --hidden-import=google.generativeai ^
    --collect-all tkinter ^
    --collect-all submodules ^
    tools/control_center.py

if errorlevel 1 (
    echo.
    echo [X] Build failed!
    pause
    exit /b 1
)

echo.
echo [✓] Build completed!
echo.

REM 检查输出
if exist "dist\AuraiControlCenter.exe" (
    echo [✓] EXE created: dist\AuraiControlCenter.exe
    echo.
    echo [*] File size:
    dir "dist\AuraiControlCenter.exe" | find "AuraiControlCenter.exe"
    echo.
    echo ========================================
    echo   Build Successful!
    echo ========================================
    echo.
    echo You can run the EXE from: dist\AuraiControlCenter.exe
    echo.
) else (
    echo [X] EXE not found!
    echo Build may have failed. Check the output above.
)

pause

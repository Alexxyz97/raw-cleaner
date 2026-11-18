@echo off
chcp 65001 >nul
REM ============================================================
REM  一键重新打包 RAW 废片清理工具 exe
REM  需要本机已安装 Python 与 PyInstaller (pip install pyinstaller)
REM  双击本文件即可，产物在 dist\RAW废片清理工具.exe
REM ============================================================
cd /d "%~dp0"

where py >nul 2>nul && set "PY=py -3" || set "PY=python"

echo [1/2] 正在用 PyInstaller 打包（单文件 / 无黑窗）...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "RAW废片清理工具" raw_cleaner.py
if errorlevel 1 (
    echo 打包失败，请确认已安装 PyInstaller:  pip install pyinstaller
    pause
    exit /b 1
)

echo [2/2] 完成！exe 位于 dist\RAW废片清理工具.exe
pause

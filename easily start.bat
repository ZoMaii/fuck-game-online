@echo off
setlocal

:: 提醒
echo Are you installed Python 3.10+ on this PC ?
echo ===================================
echo 		warning
echo "You should review open-source code(bat,py) !"
echo "press Enter key to countine - UAC..."
echo ===================================
pause

:: 检查是否以管理员身份运行
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Request administrator privileges.....
    powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c \"%~f0\"' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)

:: 切换到当前脚本所在目录（实际上已经通过WorkingDirectory设置了，但为了确保万一，可以保留）
cd /d "%~dp0"


:: 启用单次会话中使用脚本的权限
echo "system > Enable script execution permissions in a single session"
powershell -Command "Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force"

if not exist "venv" (
python -m venv venv
)


call venv\Scripts\activate.bat
echo "system > run python code"

echo.

echo "system > Is venv ?"
python -c "import os; print('Yes' if 'VIRTUAL_ENV' in os.environ else 'No')"

echo.

echo "system > package list"
pip list

echo.

:: 检查pynput是否安装
pip show pynput >nul 2>&1
if %errorlevel% equ 0 (
    echo "system > pynput is installed."
) else (
    echo "system > pynput is not installed."
    pip install pynput
)

echo.

echo "system > OK!"
type many_key.txt
python main.py

:: 暂停以便查看输出
pause
endlocal
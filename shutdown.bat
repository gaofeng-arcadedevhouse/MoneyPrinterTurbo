@echo off
chcp 65001 >nul
echo ========================================
echo   MoneyPrinterTurbo 关闭脚本
echo ========================================
echo.

echo [信息] 正在查找并关闭 Streamlit 进程...

:: 查找并关闭 streamlit 进程
taskkill /F /IM streamlit.exe 2>nul
if %errorlevel%==0 (
    echo [成功] 已关闭 streamlit.exe 进程
) else (
    echo [信息] 未找到 streamlit.exe 进程
)

:: 查找并关闭正在运行 Main.py 的 Python 进程
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%Main.py%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /F /PID %%i 2>nul
    if %errorlevel%==0 echo [成功] 已关闭进程 PID: %%i
)

:: 另一种方式：通过端口查找进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a 2>nul
    if %errorlevel%==0 (
        echo [成功] 已关闭端口 8501 上的进程 PID: %%a
    )
)

echo.
echo [完成] MoneyPrinterTurbo 服务已停止
echo.
pause

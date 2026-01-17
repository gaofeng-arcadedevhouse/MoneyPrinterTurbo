@echo off
chcp 65001 >nul
echo ========================================
echo   MoneyPrinterTurbo 启动脚本
echo ========================================
echo.

set CURRENT_DIR=%~dp0
cd /d %CURRENT_DIR%

echo [信息] 当前目录: %CURRENT_DIR%
echo [信息] 正在启动 WebUI 服务...
echo.

set PYTHONPATH=%CURRENT_DIR%

call .venv\Scripts\activate.bat

echo [信息] 服务启动后，请访问: http://localhost:8501
echo [信息] 按 Ctrl+C 可以停止服务
echo.

streamlit run .\webui\Main.py --browser.gatherUsageStats=False --server.enableCORS=True

pause

@echo off
cd /d D:\11111\english-tutor-app
echo ========================================
echo   Echo 英语大师 - 启动中...
echo ========================================
echo.
echo 启动后请用手机浏览器访问：
echo http://[你的电脑IP]:8000
echo.
echo 本机访问：http://localhost:8000
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.
python server.py
pause

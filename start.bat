chcp 65001

@echo off
echo [1/3] 正在啟動 MediaMTX 串流核心...
REM 請將下面引號內的內容，替換成你實際放 MediaMTX 的資料夾路徑
start "MediaMTX" /d "C:\projects\stream_server\bins\" mediamtx.exe

REM 暫停 2 秒等它啟動
timeout /t 2 /nobreak > nul

echo [2/3] 正在啟動 Ngrok 內網穿透...
REM 開啟新的視窗執行 ngrok，並轉發本機的 5000 port
start "Ngrok Proxy" ngrok http 5000

echo [3/3] 正在啟動 Python 直播網頁伺服器...
REM 在目前的視窗啟動 Flask
C:\projects\stream_server\.venv\Scripts\python.exe main.py
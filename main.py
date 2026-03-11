import os
import subprocess
import requests
from flask import Flask, render_template, jsonify, request, Response

app = Flask(__name__)

# 全域狀態管理
state = {
    "mode": "obs",        # 目前模式：'obs' (等待外部推流) 或 'local' (播放本地影片)
    "is_playing": False,  # 本地影片是否正在播放
    "process": None       # 存放 ffmpeg 的 subprocess 物件
}

# 串流核心的 RTMP 接收網址 (假設本機運行 MediaMTX)
RTMP_URL = "rtmp://localhost:1935/live/stream"
# 要播放的本地影片檔名 (請與此程式放在同一個資料夾)
VIDEO_PATH = "sample.mp4" 
# 新增：MediaMTX 的 HLS 本機位址
MEDIAMTX_HLS_URL = "http://localhost:8888"

@app.route('/')
def viewer():
    """渲染觀看端網頁"""
    return render_template('viewer.html')

@app.route('/admin')
def admin():
    """渲染管理端網頁"""
    return render_template('admin.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """提供前端查詢目前推流狀態"""
    return jsonify({"mode": state["mode"], "is_playing": state["is_playing"]})

def stop_ffmpeg():
    """停止 FFmpeg 推流程序"""
    if state["process"]:
        state["process"].terminate()
        state["process"].wait()
        state["process"] = None
    state["is_playing"] = False

def start_ffmpeg():
    """啟動 FFmpeg 將本地影片推流至伺服器"""
    stop_ffmpeg() # 確保啟動前沒有殘留的程序
    
    if not os.path.exists(VIDEO_PATH):
        print(f"錯誤：找不到影片檔案 {VIDEO_PATH}")
        return False

    # 使用 ffmpeg 將本地影片讀出，並打包成 flv 推送至 RTMP 網址
    command = [
        'ffmpeg',
        '-re',                  # 依照原始幀率讀取 (重要，否則推流會以最高速衝完)
        '-stream_loop', '-1',   # 影片結束後無限循環播放
        '-i', VIDEO_PATH,       # 輸入影片
        '-c:v', 'copy',         # 影像不重新編碼 (節省 CPU 資源)
        '-c:a', 'aac',          # 音訊轉碼為 aac (相容性最佳)
        '-f', 'flv',            # 封裝為 flv 格式
        RTMP_URL                # 推流目的地
    ]
    
    # 在背景啟動程序，不干擾 Web 伺服器運行
    state["process"] = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    state["is_playing"] = True
    return True

@app.route('/api/command', methods=['POST'])
def handle_command():
    """接收管理端傳來的控制指令"""
    data = request.json
    cmd = data.get('command')

    if cmd == 'obs':
        stop_ffmpeg() # 關閉本地影片推流，把通道讓給 OBS
        state["mode"] = "obs"
    elif cmd == 'play_local':
        state["mode"] = "local"
        start_ffmpeg() # 開始推送本地影片
    elif cmd == 'stop_local':
        stop_ffmpeg() # 暫停影片

    return jsonify({"status": "success"})

# --- 新增的轉發 Proxy 路由 ---
@app.route('/live/stream/<path:filename>')
def proxy_hls(filename):
    """
    接收來自前端的 m3u8 或 ts 請求，
    轉向本機的 MediaMTX 取得檔案後，再回傳給前端。
    """
    # 組合出要向 MediaMTX 請求的真實網址
    target_url = f"{MEDIAMTX_HLS_URL}/live/stream/{filename}"
    
    try:
        # 向 MediaMTX 取得資料 (stream=True 適用於影音大檔)
        resp = requests.get(target_url, stream=True)
        
        # 排除 404 等錯誤
        if resp.status_code != 200:
            return Response("Not Found", status=resp.status_code)
            
        # 將取得的資料作為串流回傳給前端瀏覽器
        return Response(
            resp.iter_content(chunk_size=1024 * 1024),
            content_type=resp.headers.get('Content-Type')
        )
    except requests.exceptions.RequestException as e:
        return Response(f"Error connecting to MediaMTX: {e}", status=502)

if __name__ == '__main__':
    print("===================================================")
    print("🌐 網頁伺服器已啟動！")
    print("📺 觀看網址: http://localhost:5000/")
    print("⚙️  管理網址: http://localhost:5000/admin")
    print("⚠️  請確認您已在背景運行了 RTMP 核心伺服器 (如 MediaMTX)")
    print("===================================================")
    app.run(host='0.0.0.0', port=5000)
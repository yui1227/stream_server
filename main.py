from functools import wraps
import glob
import os
import subprocess
import requests
from flask import Flask, render_template, jsonify, request, Response
import logging
from hls_log_filter import NoHLSLogFilter
from werkzeug.utils import secure_filename

app = Flask(__name__)
# 將過濾器套用到 Flask 底層的 werkzeug logger
log = logging.getLogger('werkzeug')
log.addFilter(NoHLSLogFilter())

# 全域狀態管理
state = {
    "mode": "obs",        # 目前模式：'obs' (等待外部推流) 或 'local' (播放本地影片)
    "is_playing": False,  # 本地影片是否正在播放
    "process": None       # 存放 ffmpeg 的 subprocess 物件
}

# 串流核心的 RTMP 接收網址 (假設本機運行 MediaMTX)
RTMP_URL = "rtmp://localhost:1935/live/stream"
# 設定影片資料夾名稱 (請在 app.py 旁邊建立這個資料夾)
VIDEO_DIR = r"videos"
PLAYLIST_FILE = "playlist.txt"
# 新增：MediaMTX 的 HLS 本機位址
MEDIAMTX_HLS_URL = "http://localhost:8888"
chat_messages = []
# --- 🟢 新增：後台帳號密碼設定 ---
ADMIN_USERNAME = "admin"           # 預設帳號，可自行修改
ADMIN_PASSWORD = "password123"     # 預設密碼，可自行修改


def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def authenticate():
    return Response(
        '需要管理員權限\n', 401,
        {'WWW-Authenticate': 'Basic realm="Admin Access Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


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


def generate_playlist():
    if not os.path.exists(VIDEO_DIR):
        os.makedirs(VIDEO_DIR)
        print(f"提示：已建立 '{VIDEO_DIR}' 資料夾，請放入影片。")
        return False

    video_files = glob.glob(os.path.join(VIDEO_DIR, "*.mp4"))

    if not video_files:
        print(f"錯誤：'{VIDEO_DIR}' 資料夾內沒有找到任何 .mp4 影片。")
        return False

    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        for video in video_files:
            abs_path = os.path.abspath(video).replace('\\', '/')
            f.write(f"file '{abs_path}'\n")

    print(f"成功：已產生播放清單，包含 {len(video_files)} 部影片。")
    return True


def start_ffmpeg():
    """啟動 FFmpeg 將本地影片推流至伺服器"""
    stop_ffmpeg()  # 確保啟動前沒有殘留的程序

    if not generate_playlist():
        return False

    # 使用 ffmpeg 將本地影片讀出，並打包成 flv 推送至 RTMP 網址
    command = [
        'ffmpeg',
        '-re',                  
        '-f', 'concat',         
        '-safe', '0',           
        '-stream_loop', '-1',   
        '-i', PLAYLIST_FILE,    
        
        # --- 影像強制轉碼設定 (1080p 升級版) ---
        '-c:v', 'libx264',      
        '-preset', 'veryfast',  
        '-b:v', '4500k',        # 提高為 4.5 Mbps 以支撐 1080p 畫質
        '-maxrate', '4500k',    
        '-bufsize', '9000k',    
        
        # 魔法濾鏡：
        # 1. scale=...decrease: 等比例縮放，確保寬不超過 1920，高不超過 1080
        # 2. pad=...: 建立一個 1920x1080 的黑色畫布，把剛剛縮放完的影片放在正中間
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
        
        '-r', '30',             
        '-g', '60',             
        '-pix_fmt', 'yuv420p',  

        # --- 音訊強制轉碼設定 ---
        '-c:a', 'aac',          
        '-b:a', '128k',         
        '-ar', '44100',         
        '-ac', '2',             
        
        '-f', 'flv',            
        RTMP_URL
    ]

    # 在背景啟動程序，不干擾 Web 伺服器運行
    state["process"] = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    state["is_playing"] = True
    return True


@app.route('/api/command', methods=['POST'])
@requires_auth
def handle_command():
    data = request.json
    cmd = data.get('command')

    if cmd == 'obs':
        stop_ffmpeg()
        state["mode"] = "obs"
        print("切換狀態: 🟢 等待 OBS 推流")
    elif cmd == 'play_local':
        state["mode"] = "local"
        print("切換狀態: 🎬 播放本地影片")
        start_ffmpeg()
    elif cmd == 'stop_local':
        stop_ffmpeg()
        print("切換狀態: ⏸️ 暫停播放")

    return jsonify({"status": "success"})

# --- 🟢 新增：影片管理 API ---


@app.route('/api/videos', methods=['GET'])
@requires_auth
def list_videos():
    """列出所有影片"""
    if not os.path.exists(VIDEO_DIR):
        return jsonify([])
    videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')]
    return jsonify(videos)


@app.route('/api/videos', methods=['POST'])
@requires_auth
def upload_video():
    """上傳新影片"""
    if 'file' not in request.files:
        return jsonify({"error": "沒有檔案"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "沒有選擇檔案"}), 400
    if file and file.filename.endswith('.mp4'):
        filename = secure_filename(file.filename)
        file.save(os.path.join(VIDEO_DIR, filename))
        return jsonify({"status": "success"})
    return jsonify({"error": "只允許上傳 .mp4 檔案"}), 400


@app.route('/api/videos/<filename>', methods=['DELETE'])
@requires_auth
def delete_video(filename):
    """刪除影片"""
    file_path = os.path.join(VIDEO_DIR, secure_filename(filename))
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"status": "success"})
    return jsonify({"error": "找不到檔案"}), 404
# ------------------------------------------------


# --- 🟢 新增：聊天室 API ---
@app.route('/api/chat', methods=['GET'])
def get_chat():
    """取得最新聊天訊息"""
    return jsonify(chat_messages)


@app.route('/api/chat', methods=['POST'])
def post_chat():
    """發送新聊天訊息"""
    import html  # 用於過濾惡意標籤
    data = request.json
    username = data.get('username', '匿名').strip() or '匿名'
    message = data.get('message', '').strip()

    if message:
        # 簡易防護 XSS 攻擊 (把 HTML 標籤轉為純文字顯示)
        safe_user = html.escape(username)
        safe_msg = html.escape(message)
        chat_messages.append({"username": safe_user, "message": safe_msg})

        # 限制只保留最近 50 則訊息，避免伺服器記憶體爆滿
        if len(chat_messages) > 50:
            chat_messages.pop(0)
    return jsonify({"status": "success"})
# ------------------------------------------------
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

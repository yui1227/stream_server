
# stream-server

一個以 Flask 建立的簡易本地串流示範專案，搭配 MediaMTX（或其他 RTMP/HLS 伺服器）使用。主要功能：

- 管理頁面：透過 `templates/admin.html` 控制是否由 OBS 外部推流，或由本地影片透過 ffmpeg 循環推流。
- 觀看頁面：`templates/viewer.html` 使用 HLS (透過 hls.js) 顯示串流。
- HLS Proxy：後端提供 `/live/stream/<filename>` 路由，向本地運行的 MediaMTX 取得 m3u8/ts 並轉發給瀏覽器，避免 CORS/跨來源問題。

## 目標讀者

此專案適合想要快速建立本地直播示範環境的開發者或測試人員。你可以用它來：

- 示範 OBS 推流與伺服器接收流程
- 本地影片循環推送作為測試來源
- 測試 HLS 在瀏覽器的播放（含 hls.js）

## 主要檔案

- `main.py`：Flask 應用，包含前後端路由、啟動/停止 ffmpeg 的邏輯，以及 HLS proxy。
- `pyproject.toml`：宣告 Python 相依套件（Flask、requests）。
- `bins/mediamtx.yml`：提供一個範例 MediaMTX 設定檔（包含 RTMP/HLS/WEbrtc 設定）。
- `templates/admin.html`：管理控制台 UI（切換 OBS / 播放本地影片 / 停止）。
- `templates/viewer.html`：觀看端 UI（使用 hls.js 播放 `/live/stream/index.m3u8`）。

## 需求

- Python 3.12+
- ffmpeg（系統路徑可執行）
- MediaMTX（或其他支援 RTMP 推入與 HLS 輸出的伺服器）

## 安裝與快速開始（Windows PowerShell 範例）

1. 建議使用 `uv` 來還原/管理虛擬環境（你已從官方網站安裝 `uv`）：

```pwsh
# 在專案根目錄執行，`uv` 會根據 `pyproject.toml` 建立或同步虛擬環境與相依套件
uv sync
```

啟用虛擬環境（若 `uv` 建出的環境放在 `.venv`）：

```pwsh
.\\.venv\\Scripts\\Activate.ps1
```

如果 `uv` 將環境放在其他路徑，請參考 `uv` 官方文件取得正確啟動方式。

2. 確認系統已安裝 `ffmpeg`，可在 PowerShell 執行：

```pwsh
ffmpeg -version
```

3. 啟動 MediaMTX（請先自行安裝或使用 Docker，並載入 `bins/mediamtx.yml` 作為設定）。範例（依你的安裝方式調整）：

```pwsh
# 若系統可直接執行 mediamtx，可用下列指令載入 config
mediamtx bins\mediamtx.yml

# 或使用 Docker（示例）：
docker run -it --rm -p 1935:1935 -p 8888:8888 -v ${PWD}/bins:/config blazingly/mediamtx mediamtx /config/mediamtx.yml
```

4. 把想要循環推流的影片放到專案根目錄並命名為 `sample.mp4`（或修改 `main.py` 中的 `VIDEO_PATH`）。

5. 啟動 Flask 應用：

```pwsh
uv run .\main.py
```

6. 開啟瀏覽器：

- 觀看端: http://localhost:5000/
- 管理端: http://localhost:5000/admin

說明：當你在管理端按下「播放本地影片」時，後端會啟動 `ffmpeg` 將 `sample.mp4` 以 flv 封裝推送到 `RTMP_URL`（`rtmp://localhost:1935/live/stream`），而 MediaMTX 會產生對應的 HLS（預設在 8888 port），前端透過 `/live/stream/index.m3u8` 取得並播放。

## 可調整的設定

- `main.py` 中的常數：
	- `RTMP_URL`：RTMP 推流目的地（預設 `rtmp://localhost:1935/live/stream`）。
	- `VIDEO_PATH`：本地測試影片檔案名稱。
	- `MEDIAMTX_HLS_URL`：MediaMTX HLS HTTP 服務位址（預設 `http://localhost:8888`）。

- `bins/mediamtx.yml`：MediaMTX 的完整設定（包含 RTMP/HLS/WebRTC 等），可依需求修改 port、auth、log 等選項。

## API 與路由

- `GET /`：觀看頁面 (templates/viewer.html)
- `GET /admin`：管理頁面 (templates/admin.html)
- `GET /api/status`：查詢目前模式與播放狀態，回傳 JSON
- `POST /api/command`：控制伺服器，body 範例： `{ "command": "play_local" }`, `obs`, `stop_local`
- `GET /live/stream/<filename>`：HLS Proxy，將請求轉發至 `MEDIAMTX_HLS_URL`，避免前端直接跨來源請求

## 偵錯與常見問題

- 若瀏覽器無法播放：確認 MediaMTX 是否已啟動，且 HLS 頁面可從 `http://localhost:8888/live/stream/index.m3u8` 直接取得（或看 MediaMTX log）。
- ffmpeg 找不到或啟動失敗：確認 `ffmpeg` 已安裝且位於 PATH，或在 `main.py` 中改為 ffmpeg 的絕對路徑。
- CORS/網域問題：本專案將 HLS 請求透過 `/live/stream/...` 轉發，應可避免跨域問題；若仍遇到需檢查 MediaMTX 的 CORS 設定。

## 開發與貢獻

歡迎發 PR 與 issues。開發建議：

- 建立獨立分支，撰寫範例測試或擴充播放/推流功能。
- 本專案可延伸：加入使用者認證、更多的推流來源管理、或用 Docker Compose 封裝整個測試環境（包含 MediaMTX、ffmpeg runner 等）。

## 相依套件

專案在 `pyproject.toml` 中列出主要相依：

- Flask >= 3.1.3
- requests >= 2.32.5

可直接安裝上述套件（見上方安裝步驟）。

## 授權

本專案採用 MIT License（詳見 `LICENSE`）。

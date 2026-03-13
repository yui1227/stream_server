import logging

class NoHLSLogFilter(logging.Filter):
    def filter(self, record):
        # 取得 Log 的訊息文字
        msg = record.getMessage()
        # 如果訊息中包含 '/live/stream/' (HLS 相關請求)，就過濾掉不印出來 (回傳 False)
        if '/live/stream/' in msg:
            return False
        return True
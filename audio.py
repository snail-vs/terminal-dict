import os
import subprocess
import requests
import asyncio
from edge_tts import Communicate

class AudioService:
    def __init__(self, cache_dir="audio_cache"):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def play_youdao(self, word, type=1):
        """播放有道网络音频"""
        url = f"https://dict.youdao.com/dictvoice?audio={word}&type={type}"
        file_path = os.path.join(self.cache_dir, f"{word}_{type}.mp3")
        
        if not os.path.exists(file_path):
            response = requests.get(url)
            with open(file_path, "wb") as f:
                f.write(response.content)
        
        self._play_file(file_path)

    async def play_tts(self, text):
        """使用 edge-tts 生成并播放"""
        file_path = os.path.join(self.cache_dir, f"{text}_tts.mp3")
        if not os.path.exists(file_path):
            communicate = Communicate(text, "en-US-JennyNeural")
            await communicate.save(file_path)
        
        self._play_file(file_path)

    def _play_file(self, file_path):
        # 尝试使用 mpv 播放，若无则使用系统默认播放器
        try:
            subprocess.run(["mpv", "--no-video", file_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # 简单回退：调用系统默认播放器 (Linux下的通用处理)
            subprocess.run(["mpg123", "-q", file_path] if os.path.exists("/usr/bin/mpg123") else ["play", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

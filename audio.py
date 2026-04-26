import os
import subprocess
import requests
import asyncio
from edge_tts import Communicate

# 按优先级尝试的播放器命令
_PLAYERS = [
    ["mpv", "--no-video", "--really-quiet"],
    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
    ["mpg123", "-q"],
]


class AudioService:
    def __init__(self, cache_dir="audio_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._player_cmd = self._detect_player()

    @staticmethod
    def _detect_player():
        """找到第一个可用的播放器"""
        import shutil
        for cmd in _PLAYERS:
            if shutil.which(cmd[0]):
                return cmd
        return None

    # ── 有道发音 ──────────────────────────────────────────────

    def _youdao_path(self, word: str, accent: int) -> str:
        return os.path.join(self.cache_dir, f"{word}_{accent}.mp3")

    def _download_youdao(self, word: str, accent: int) -> str:
        """同步下载有道音频，返回本地路径（已缓存则跳过）"""
        path = self._youdao_path(word, accent)
        if not os.path.exists(path):
            url = f"https://dict.youdao.com/dictvoice?audio={word}&type={accent}"
            resp = requests.get(url, timeout=10,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
        return path

    async def play_youdao(self, word: str, accent: int = 1):
        """
        播放有道发音一次。
        accent=1 → 美音 (type=1), accent=2 → 英音 (type=2)
        """
        await self.play_youdao_loop(word, accent, count=1)

    async def play_youdao_loop(self, word: str, accent: int = 1, count: int = 1, delay: float = 1.0):
        """
        循环播放有道发音。
        count=循环次数, delay=每次间隔秒数
        """
        loop = asyncio.get_event_loop()
        try:
            path = await loop.run_in_executor(
                None, lambda: self._download_youdao(word, accent)
            )
            for i in range(count):
                await self._play_file_async(path)
                if i < count - 1 and delay > 0:
                    await asyncio.sleep(delay)
        except Exception:
            pass  # 发音失败不影响主流程

    # ── edge-tts 备用 ─────────────────────────────────────────

    async def play_tts(self, text: str):
        """使用 edge-tts 生成并播放"""
        file_path = os.path.join(self.cache_dir, f"{text}_tts.mp3")
        if not os.path.exists(file_path):
            communicate = Communicate(text, "en-US-JennyNeural")
            await communicate.save(file_path)
        await self._play_file_async(file_path)

    # ── 内部播放 ──────────────────────────────────────────────

    async def _play_file_async(self, file_path: str):
        """异步调用外部播放器，不阻塞事件循环"""
        if not self._player_cmd:
            return
        cmd = self._player_cmd + [file_path]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

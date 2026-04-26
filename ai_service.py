import os
import json
import asyncio
import requests
import toml


class AIService:
    """通用 AI 服务，封装 provider 切换和 API 调用"""

    def __init__(self, config_path="config.toml"):
        self.config = toml.load(config_path)
        self.provider_name = self.config["ai"]["default_provider"]
        self._load_provider()

    def _load_provider(self):
        cfg = self.config["ai"]["providers"][self.provider_name]
        self.api_url = cfg["api_url"].rstrip("/")
        self.model = cfg["models"][0]
        self.api_key = os.getenv(cfg["key_env"])

    def set_provider(self, name):
        if name in self.config["ai"]["providers"]:
            self.provider_name = name
            self._load_provider()

    @property
    def available(self):
        return bool(self.api_key)

    async def chat(self, messages, temperature=0, timeout=15):
        """通用 Chat Completion"""
        if not self.available:
            return None
        if "anthropic.com" in self.api_url:
            return await self._chat_anthropic(messages, temperature, timeout)
        return await self._chat_openai(messages, temperature, timeout)

    async def chat_json(self, messages, temperature=0):
        """Chat Completion，返回解析后的 JSON"""
        content = await self.chat(messages, temperature)
        if not content:
            return None
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    async def chat_openai_json(self, messages, response_schema, temperature=0):
        """请求 JSON 格式的结构化输出（仅限支持 response_format 的 provider）"""
        content = await self.chat(messages, temperature)
        if not content:
            return None
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    # ── OpenAI 兼容 ──────────────────────────────────────────

    async def _chat_openai(self, messages, temperature, timeout):
        url = self.api_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None, lambda: requests.post(url, json=payload, headers=headers, timeout=timeout)
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            print(f"\n[AI Error] {self.provider_name} {resp.status_code}: {resp.text[:200]}", file=__import__("sys").stderr)
        except Exception as e:
            print(f"\n[AI Exception] {e}", file=__import__("sys").stderr)
        return None

    # ── Anthropic 兼容 ───────────────────────────────────────

    async def _chat_anthropic(self, messages, temperature, timeout):
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=self.api_key)
        system = None
        an_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                an_messages.append({"role": m["role"], "content": m["content"]})
        try:
            resp = await client.messages.create(
                model=self.model,
                messages=an_messages,
                system=system,
                temperature=temperature,
                max_tokens=1024,
            )
            return resp.content[0].text
        except Exception as e:
            print(f"\n[AI Exception] {e}", file=__import__("sys").stderr)
        return None

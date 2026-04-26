class EnrichmentService:
    """查词时 AI 补充例句、词根、搭配"""

    def __init__(self, ai, db):
        self.ai = ai
        self.db = db

    def get_cached(self, word):
        """返回已缓存的补充信息，None 表示无缓存"""
        sentences = self.db.get_enrichment(word, "sentence")
        etymology = self.db.get_enrichment(word, "etymology")
        collocations = self.db.get_enrichment(word, "collocation")
        if sentences or etymology or collocations:
            return {
                "sentences": sentences or [],
                "etymology": etymology or "",
                "collocations": collocations or [],
            }
        return None

    async def get_enrichments_async(self, word):
        """异步获取（AI 生成 + 缓存回写）"""
        cached = self.get_cached(word)
        if cached:
            return cached
        return await self._fetch_from_ai(word)

    async def _fetch_from_ai(self, word):
        prompt = (
            f"Analyze the English word '{word}'. "
            "Return ONLY a JSON object with this exact schema, no extra text:\n"
            '{\n'
            '  "sentences": ["sentence 1", "sentence 2", "sentence 3"],\n'
            '  "etymology": "brief root/affix analysis",\n'
            '  "collocations": ["common phrase 1", "common phrase 2"]\n'
            '}\n'
            "- sentences: 3 short example sentences relevant to programming/work\n"
            "- etymology: one-line word root breakdown\n"
            "- collocations: 2-3 common word pairings"
        )
        result = await self.ai.chat_json([{"role": "user", "content": prompt}])
        if result:
            if result.get("sentences"):
                self.db.save_enrichment(word, "sentence", result["sentences"])
            if result.get("etymology"):
                self.db.save_enrichment(word, "etymology", result["etymology"])
            if result.get("collocations"):
                self.db.save_enrichment(word, "collocation", result["collocations"])
        return result

class SyllableService:
    def __init__(self, ai):
        self.ai = ai

    async def get_syllables_async(self, word):
        prompt = (
            f"Break the English word '{word}' into syllables. "
            "Return ONLY a JSON object with this exact schema, no extra text:\n"
            '{"syllables": "syl-la-ble", "stress": 1}\n'
            "Where 'syllables' uses hyphens between syllables, "
            "and 'stress' is the 1-based index of the stressed syllable."
        )
        return await self.ai.chat_json([{"role": "user", "content": prompt}])

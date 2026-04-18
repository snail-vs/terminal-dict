import requests

class DictionaryService:
    def __init__(self):
        self.base_url = "https://dict.youdao.com/jsonapi"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def lookup(self, word):
        try:
            url = f"{self.base_url}?q={word}"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching from Youdao: {e}")
            return None

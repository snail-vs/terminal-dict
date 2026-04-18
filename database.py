import sqlite3
import json
import os

class DatabaseService:
    def __init__(self, db_path="dictionary.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS words (
                    word TEXT PRIMARY KEY,
                    data TEXT,
                    audio_path_us TEXT,
                    audio_path_uk TEXT
                )
            """)
            conn.commit()

    def get_word(self, word):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data, audio_path_us, audio_path_uk FROM words WHERE word = ?", (word,))
            row = cursor.fetchone()
            if row:
                return {
                    "data": json.loads(row[0]),
                    "audio_path_us": row[1],
                    "audio_path_uk": row[2]
                }
            return None

    def save_word(self, word, data, audio_us=None, audio_uk=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO words (word, data, audio_path_us, audio_path_uk)
                VALUES (?, ?, ?, ?)
            """, (word, json.dumps(data), audio_us, audio_uk))
            conn.commit()

import sqlite3
import json

SCHEMA_VERSION = 1

_MIGRATIONS = {
    1: [
        # 用户画像
        """CREATE TABLE IF NOT EXISTS profile (
            key TEXT PRIMARY KEY,
            value TEXT
        )""",
        # AI 补充信息（例句、词根、搭配）
        """CREATE TABLE IF NOT EXISTS word_enrichments (
            word TEXT,
            source TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (word, source)
        )""",
        # 改写/翻译历史
        """CREATE TABLE IF NOT EXISTS writing_assists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            input TEXT,
            output TEXT,
            accepted BOOLEAN,
            context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        # 练习主会话
        """CREATE TABLE IF NOT EXISTS practice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT,
            level TEXT,
            score REAL,
            duration_seconds INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        # 练习明细
        """CREATE TABLE IF NOT EXISTS practice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INT REFERENCES practice_sessions(id),
            prompt TEXT,
            user_answer TEXT,
            correction TEXT,
            feedback TEXT,
            error_tags TEXT,
            correct BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        # 间隔复习队列
        """CREATE TABLE IF NOT EXISTS review_queue (
            word TEXT PRIMARY KEY REFERENCES words(word),
            ease REAL DEFAULT 2.5,
            interval INT DEFAULT 0,
            due_at TIMESTAMP DEFAULT (datetime('now')),
            review_count INT DEFAULT 0,
            last_reviewed_at TIMESTAMP
        )""",
    ]
}

_WORDS_NEW_COLUMNS = [
    "lookup_count INTEGER DEFAULT 1",
    "last_lookup_at TIMESTAMP",
]


class DatabaseService:
    def __init__(self, db_path="dictionary.db"):
        self.db_path = db_path
        self._init_db()
        self._migrate()

    # ── 初始化 & 迁移 ──────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS words (
                    word TEXT PRIMARY KEY,
                    data TEXT,
                    audio_path_us TEXT,
                    audio_path_uk TEXT,
                    syllables TEXT,
                    ai_extended_data TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _migrate(self):
        with sqlite3.connect(self.db_path) as conn:
            current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
            for ver, stmts in sorted(_MIGRATIONS.items()):
                if ver <= current:
                    continue
                for stmt in stmts:
                    conn.execute(stmt)
                for col in _WORDS_NEW_COLUMNS:
                    try:
                        conn.execute(f"ALTER TABLE words ADD COLUMN {col}")
                    except sqlite3.OperationalError:
                        pass
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (ver,))
                conn.commit()

    # ── 单词查词缓存 ───────────────────────────────────────

    def get_word(self, word):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data, audio_path_us, audio_path_uk, syllables FROM words WHERE word = ?",
                (word,),
            ).fetchone()
            if row:
                return {
                    "data": json.loads(row[0]),
                    "audio_path_us": row[1],
                    "audio_path_uk": row[2],
                    "syllables": json.loads(row[3]) if row[3] else None,
                }
            return None

    def save_word(self, word, data, audio_us=None, audio_uk=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO words (word, data, audio_path_us, audio_path_uk)
                   VALUES (?, ?, ?, ?)""",
                (word, json.dumps(data), audio_us, audio_uk),
            )
            conn.commit()

    def update_syllables(self, word, s_data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE words SET syllables = ? WHERE word = ?",
                (json.dumps(s_data), word),
            )
            conn.commit()

    # ── 用户画像 ───────────────────────────────────────────

    def get_profile(self, key):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT value FROM profile WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def set_profile(self, key, value):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO profile (key, value) VALUES (?, ?)", (key, value)
            )
            conn.commit()

    # ── 单词补充信息 ───────────────────────────────────────

    def get_enrichment(self, word, source):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT content FROM word_enrichments WHERE word = ? AND source = ?",
                (word, source),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def save_enrichment(self, word, source, content):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO word_enrichments (word, source, content) VALUES (?, ?, ?)",
                (word, source, json.dumps(content)),
            )
            conn.commit()

    # ── 写作助手历史 ───────────────────────────────────────

    def save_writing_assist(self, type_, input_, output, accepted=None, context=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO writing_assists (type, input, output, accepted, context) VALUES (?, ?, ?, ?, ?)",
                (type_, input_, output, accepted, context),
            )
            conn.commit()

    # ── 练习 ───────────────────────────────────────────────

    def create_practice_session(self, mode, level=None):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO practice_sessions (mode, level) VALUES (?, ?)", (mode, level)
            )
            conn.commit()
            return cur.lastrowid

    def finish_practice_session(self, session_id, score, duration):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE practice_sessions SET score = ?, duration_seconds = ? WHERE id = ?",
                (score, duration, session_id),
            )
            conn.commit()

    def save_practice_item(self, session_id, prompt, user_answer, correction, feedback,
                           error_tags, correct):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO practice_items
                   (session_id, prompt, user_answer, correction, feedback, error_tags, correct)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, prompt, user_answer, correction, feedback,
                 json.dumps(error_tags) if error_tags else None, correct),
            )
            conn.commit()

    # ── 复习队列 ───────────────────────────────────────────

    def get_due_reviews(self, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT word, ease, interval, review_count
                   FROM review_queue
                   WHERE due_at <= datetime('now')
                   ORDER BY due_at ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [{"word": r[0], "ease": r[1], "interval": r[2], "review_count": r[3]} for r in rows]

    def add_to_review_queue(self, word, ease=2.5, interval=0):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO review_queue (word, ease, interval)
                   VALUES (?, ?, ?)""",
                (word, ease, interval),
            )
            conn.commit()

    def update_review(self, word, ease, interval, due_at):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE review_queue SET ease = ?, interval = ?, due_at = ?,
                   review_count = review_count + 1, last_reviewed_at = datetime('now')
                   WHERE word = ?""",
                (ease, interval, due_at, word),
            )
            conn.commit()

    # ── 查词历史 ───────────────────────────────────────────

    def get_lookup_history(self, limit=20, offset=0):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT word, lookup_count, last_lookup_at, data, syllables
                   FROM words
                   WHERE last_lookup_at IS NOT NULL
                   ORDER BY last_lookup_at DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            results = []
            for row in rows:
                word, count, last_time, data_json, syl_json = row
                data = json.loads(data_json) if data_json else {}
                syllables = json.loads(syl_json) if syl_json else None
                results.append({
                    "word": word,
                    "count": count,
                    "last_time": last_time,
                    "data": data,
                    "syllables": syllables,
                })
            return results

    def get_total_lookup_count(self):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM words WHERE last_lookup_at IS NOT NULL"
            ).fetchone()
            return row[0] if row else 0

    def add_words_to_review(self, word_list):
        with sqlite3.connect(self.db_path) as conn:
            for word in word_list:
                conn.execute(
                    "INSERT OR IGNORE INTO review_queue (word) VALUES (?)",
                    (word,),
                )
            conn.commit()

    def is_word_in_review_queue(self, word):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM review_queue WHERE word = ?", (word,)
            ).fetchone()
            return row is not None

    def lookup_count(self, word):
        """每次查词时调用，累计查词次数"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE words SET lookup_count = lookup_count + 1,
                   last_lookup_at = datetime('now')
                   WHERE word = ?""",
                (word,),
            )
            # 如果是新词则初始化
            if conn.total_changes == 0:
                conn.execute(
                    "INSERT INTO words (word, lookup_count, last_lookup_at) VALUES (?, 1, datetime('now'))",
                    (word,),
                )
            conn.commit()

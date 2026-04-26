# 数据库 Schema

所有练习/学习数据都持久化在 `dictionary.db`，SQLite 单文件，零依赖。

---

## 现有表

### words

| 列 | 类型 | 说明 |
|---|---|---|
| word | TEXT PK | 单词 |
| data | TEXT | 有道原始 JSON 响应 |
| audio_path_us | TEXT | 美音本地缓存路径 |
| audio_path_uk | TEXT | 英音本地缓存路径 |
| syllables | TEXT | JSON `{syllables, stress}` |
| ai_extended_data | TEXT | 预留 |

---

## 新增表

### profile — 用户画像

```sql
CREATE TABLE profile (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

Key-Value 方便扩展，不改 schema。

| key | value 示例 | 说明 |
|---|---|---|
| `level` | `"intermediate"` | 英语水平自评 |
| `total_lookups` | `"142"` | 累计查词次数 |
| `total_practice` | `"37"` | 累计练习次数 |
| `practice_streak` | `"5"` | 连续练习天数 |
| `weak_areas` | `["preposition","tense"]` | AI 推断的薄弱点 |
| `preferred_mode` | `"translation"` | 偏好练习模式 |

### word_enrichments — 单词补充信息

```sql
CREATE TABLE word_enrichments (
    word TEXT,
    source TEXT,       -- 'sentence', 'etymology', 'collocation'
    content TEXT,      -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (word, source)
);
```

AI 在查词时异步补充：例句（工作场景）、词根词缀、常见搭配。

### writing_assists — 改写/翻译历史

```sql
CREATE TABLE writing_assists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,                -- 'commit', 'comment', 'translate'
    input TEXT,               -- 原始中文/混合文本
    output TEXT,              -- AI 建议
    accepted BOOLEAN,
    context TEXT,             -- 可选：文件名、git diff 摘要
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

积累越多，越能分析用户常犯的表达错误。

### practice_sessions — 练习会话

```sql
CREATE TABLE practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT,                -- 'translation', 'correction', 'dialogue'
    level TEXT,
    score REAL,               -- 0-100
    duration_seconds INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### practice_items — 练习明细

```sql
CREATE TABLE practice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INT REFERENCES practice_sessions(id),
    prompt TEXT,              -- 题目
    user_answer TEXT,
    correction TEXT,          -- AI 纠正版本
    feedback TEXT,            -- AI 详细解释
    error_tags TEXT,          -- JSON ["preposition","tense"]
    correct BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### review_queue — 间隔复习（SM-2）

```sql
CREATE TABLE review_queue (
    word TEXT PRIMARY KEY REFERENCES words(word),
    ease REAL DEFAULT 2.5,
    interval INT DEFAULT 0,   -- 距离下次复习的天数
    due_at TIMESTAMP DEFAULT (datetime('now')),
    review_count INT DEFAULT 0,
    last_reviewed_at TIMESTAMP
);
```

### word_previews — 复习预展示

```sql
CREATE TABLE word_previews (
    word TEXT PRIMARY KEY REFERENCES words(word),
    preview TEXT              -- 查词时的表格渲染文本，复习时直接展示
);
```

---

## 使用原则

1. **每种数据类型一张表**，字段明确。加新功能 = 加新表，不影响已有逻辑
2. **JSON 存灵活内容**，但需要查询的字段（error_tags, level）独立成列
3. **避免万能表** — 不搞单表 `events` 存所有类型数据，查询和迁移都麻烦
4. **所有表都带 `created_at`**，时间线分析的基础

## 迁移

SQLite schema 变更用版本号迁移：

```
migrations/
  001_initial.sql
  002_profiles.sql
  ...
```

在 `database.py` 中维护一个 `schema_version` 表，启动时自动按顺序执行未应用的迁移。

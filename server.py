"""dict-cli Web 界面 — FastAPI"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3
import json

app = FastAPI(title="dict-cli")

DB_PATH = "dictionary.db"


def db():
    return sqlite3.connect(DB_PATH)


# ── helpers ──

def query(sql, params=()):
    with db() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql, params=()):
    with db() as conn:
        r = conn.execute(sql, params).fetchone()
        return r


# ═══════════════════════════════════════════════════════════
# HTML layout
# ═══════════════════════════════════════════════════════════

_HEAD = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>dict-cli</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f5f5;color:#333;padding:20px;max-width:960px;margin:auto}}
h1{{font-size:1.5rem;margin-bottom:1rem;color:#333;display:flex;align-items:center;gap:8px}}
h2{{font-size:1.2rem;margin:1.5rem 0 .5rem;color:#555}}
nav{{display:flex;gap:12px;margin-bottom:2rem;flex-wrap:wrap}}
nav a{{color:#fff;background:#4a90d9;padding:8px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:.9rem}}
nav a:hover{{background:#357abd}}
.card{{background:#fff;border-radius:8px;padding:16px;margin-bottom:1rem;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-bottom:1.5rem}}
.stat{{background:#fff;border-radius:8px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.stat-num{{font-size:2rem;font-weight:700;color:#4a90d9}}
.stat-label{{font-size:.8rem;color:#888;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
th,td{{text-align:left;padding:8px;border-bottom:1px solid #eee}}
th{{color:#888;font-weight:600;font-size:.8rem;text-transform:uppercase}}
tr:hover{{background:#f0f4ff}}
a{{color:#4a90d9;text-decoration:none}}
a:hover{{text-decoration:underline}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:600}}
.badge-green{{background:#e6f7e6;color:#2d8a2d}}
.badge-red{{background:#ffe6e6;color:#c0392b}}
.badge-yellow{{background:#fff3e0;color:#e67e22}}
.feedback{{font-size:.85rem;color:#666;margin-top:4px}}
.tag{{display:inline-block;padding:1px 6px;border-radius:4px;background:#eee;font-size:.75rem;margin:1px}}
.empty{{color:#999;font-style:italic;padding:2rem;text-align:center}}
</style>
</head><body>
<h1>📖 dict-cli</h1>
<nav>
<a href="/">仪表盘</a>
<a href="/words">单词</a>
<a href="/practice">练习</a>
<a href="/review">复习</a>
</nav>
<main>
"""

_TAIL = "</main></body></html>"


def page(title, content):
    return HTMLResponse(_HEAD.replace("dict-cli", f"dict-cli — {title}") + content + _TAIL)


# ═══════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def dashboard():
    total_words = query_one("SELECT COUNT(*) FROM words")[0]
    total_lookups = query_one("SELECT COALESCE(SUM(lookup_count),0) FROM words")[0]
    total_practice = query_one("SELECT COUNT(*) FROM practice_sessions")[0]
    avg_score = query_one("SELECT COALESCE(ROUND(AVG(score),1),0) FROM practice_sessions")[0]
    due = query_one("SELECT COUNT(*) FROM review_queue WHERE due_at <= datetime('now')")[0]
    recent = query("SELECT word, last_lookup_at FROM words WHERE last_lookup_at IS NOT NULL ORDER BY last_lookup_at DESC LIMIT 10")
    level = query_one("SELECT value FROM profile WHERE key='level'")

    stats = f"""\
<div class="stats">
<div class="stat"><div class="stat-num">{total_words}</div><div class="stat-label">查词</div></div>
<div class="stat"><div class="stat-num">{total_lookups}</div><div class="stat-label">累计查询</div></div>
<div class="stat"><div class="stat-num">{total_practice}</div><div class="stat-label">练习</div></div>
<div class="stat"><div class="stat-num">{avg_score}%</div><div class="stat-label">平均分</div></div>
<div class="stat"><div class="stat-num">{due}</div><div class="stat-label">待复习</div></div>
<div class="stat"><div class="stat-num">{level[0] if level else '—'}</div><div class="stat-label">水平</div></div>
</div>"""

    recent_rows = ""
    for w, t in recent:
        recent_rows += f"<tr><td><a href='/words/{w}'>{w}</a></td><td>{t or ''}</td></tr>"
    recent_html = f"""\
<h2>最近查询</h2>
<div class="card"><table>{"".join(f"<tr><td><a href='/words/{r[0]}'>{r[0]}</a></td><td>{r[1] or ''}</td></tr>" for r in recent)}</table></div>""" if recent else ""

    return page("仪表盘", stats + recent_html)


@app.get("/words", response_class=HTMLResponse)
def word_list(q: str = ""):
    if q:
        rows = query("SELECT word, lookup_count, last_lookup_at FROM words WHERE word LIKE ? ORDER BY last_lookup_at DESC", (f"%{q}%",))
    else:
        rows = query("SELECT word, lookup_count, last_lookup_at FROM words ORDER BY last_lookup_at DESC")

    search = f"""\
<form style="margin-bottom:1rem"><input name="q" placeholder="搜索单词..." value="{q}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:1rem"></form>"""

    rows_html = ""
    for w, cnt, t in rows:
        rows_html += f"<tr><td><a href='/words/{w}'>{w}</a></td><td>{cnt}</td><td>{t or ''}</td></tr>"

    if not rows:
        rows_html = '<tr><td colspan="3" class="empty">暂无数据</td></tr>'

    content = search + """\
<h2>单词列表</h2>
<div class="card"><table>
<tr><th>单词</th><th>查询次数</th><th>最后查询</th></tr>
""" + rows_html + "</table></div>"

    return page("单词", content)


@app.get("/words/{word}", response_class=HTMLResponse)
def word_detail(word: str):
    row = query_one("SELECT data, syllables, lookup_count, last_lookup_at FROM words WHERE word=?", (word,))
    if not row:
        return page("单词", '<div class="empty">未找到</div>')

    data, syllables_json, lookup_count, last_lookup = row
    d = json.loads(data) if isinstance(data, str) else data
    syllables = json.loads(syllables_json) if syllables_json else None

    # Phonetics
    ec = d.get("ec", {}).get("word", [{}])[0] if d.get("ec") else {}
    us_ph = ec.get("usphone", "")
    uk_ph = ec.get("ukphone", "")

    ph_line = f"<p>🔊 美/{us_ph}/" if us_ph else "<p>🔊"
    if uk_ph and uk_ph != us_ph:
        ph_line += f" 英/{uk_ph}/"
    ph_line += "</p>"

    # Syllables
    syl_line = ""
    if syllables:
        syl = syllables.get("syllables", "").replace("-", "·")
        stress = syllables.get("stress", 0)
        syl_line = f"<p>音节: <strong>{syl}</strong> (重音: 第{stress}音节)</p>"

    # Definitions
    defs = ""
    if "individual" in d and "trs" in d["individual"]:
        for tr in d["individual"]["trs"]:
            defs += f"<p><strong>{tr['pos']}</strong> {tr['tran']}</p>"
    elif "ec" in d and d["ec"].get("word"):
        for tr_group in d["ec"]["word"][0].get("trs", []):
            for tr in tr_group.get("tr", []):
                m = "".join(tr.get("l", {}).get("i", []))
                if m and not m.startswith("【"):
                    defs += f"<p>{m[:100]}</p>"

    # Enrichments
    enrich = ""
    for src, label in [("sentence", "📝 例句"), ("etymology", "🌱 词根"), ("collocation", "🔗 搭配")]:
        val = query_one("SELECT content FROM word_enrichments WHERE word=? AND source=?", (word, src))
        if val:
            items = json.loads(val[0]) if isinstance(val[0], str) else val[0]
            if isinstance(items, list):
                for item in items[:3]:
                    enrich += f"<p><strong>{label}</strong> {item}</p>"
            else:
                enrich += f"<p><strong>{label}</strong> {items}</p>"

    # Review status
    rev = query_one("SELECT ease, interval, review_count, due_at FROM review_queue WHERE word=?", (word,))
    review_status = ""
    if rev:
        due_str = f"<span class='badge badge-green'>已复习 {rev[2]} 次</span>" if rev[2] > 0 else "<span class='badge badge-yellow'>未复习</span>"
        review_status = f"<p>复习状态: {due_str} 下次复习: {rev[3]}</p>"

    meta = f"<p style='color:#888;font-size:.85rem'>查询 {lookup_count} 次 · 最后查询 {last_lookup or '—'}</p>"

    content = f"""\
<div class="card">
<h2>{word}</h2>
{meta}
{ph_line}
{syl_line}
{defs}
</div>
<div class="card">
{review_status}
</div>
<div class="card">
{enrich}
</div>"""

    return page(word, content)


@app.get("/practice", response_class=HTMLResponse)
def practice_history():
    sessions = query("""\
SELECT id, mode, level, score, duration_seconds, created_at
FROM practice_sessions ORDER BY created_at DESC LIMIT 50""")

    rows_html = ""
    for sid, mode, level, score, dur, created in sessions:
        badge = "badge-green" if (score or 0) >= 70 else "badge-yellow" if (score or 0) >= 40 else "badge-red"
        label = {"translate": "中译英", "correct": "改错", "dialogue": "对话"}.get(mode, mode)
        rows_html += f"""\
<tr>
<td><a href='/practice/{sid}'>#{sid}</a></td>
<td>{label}</td>
<td>{level or '—'}</td>
<td><span class='badge {badge}'>{score:.0f}%</span></td>
<td>{dur // 60}:{dur % 60:02d}</td>
<td>{created}</td>
</tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="6" class="empty">暂无练习记录</td></tr>'

    content = """\
<h2>练习历史</h2>
<div class="card"><table>
<tr><th>会话</th><th>模式</th><th>水平</th><th>得分</th><th>用时</th><th>时间</th></tr>
""" + rows_html + "</table></div>"

    return page("练习", content)


@app.get("/practice/{session_id}", response_class=HTMLResponse)
def practice_detail(session_id: int):
    sess = query_one("SELECT mode, level, score, duration_seconds, created_at FROM practice_sessions WHERE id=?", (session_id,))
    if not sess:
        return page("练习", '<div class="empty">未找到</div>')

    mode, level, score, dur, created = sess
    label = {"translate": "中译英", "correct": "改错", "dialogue": "对话"}.get(mode, mode)

    items = query("""\
SELECT prompt, user_answer, correction, feedback, error_tags, correct
FROM practice_items WHERE session_id=? ORDER BY id""", (session_id,))

    items_html = ""
    for prompt, answer, correction, feedback, etags, correct in items:
        badge = "badge-green" if correct else "badge-red"
        tags = ""
        if etags:
            for t in json.loads(etags):
                tags += f"<span class='tag'>{t}</span>"
        items_html += f"""\
<div class="card">
<p><strong>📝</strong> {prompt}</p>
<p><strong>你的回答:</strong> {answer} <span class="badge {badge}">{'✓' if correct else '✗'}</span></p>
{f'<p><strong>参考:</strong> {correction}</p>' if correction else ''}
{f'<p class="feedback">{feedback}</p>' if feedback else ''}
<p>{tags}</p>
</div>"""

    if not items_html:
        items_html = '<div class="empty">无题目记录</div>'

    content = f"""\
<div class="card">
<h2>练习 #{session_id}</h2>
<p>模式: {label} · 水平: {level or '—'} · 得分: {score:.0f}% · 用时: {dur // 60}:{dur % 60:02d} · {created}</p>
</div>
{items_html}"""

    return page(f"练习 #{session_id}", content)


@app.get("/review", response_class=HTMLResponse)
def review_queue():
    due = query("""\
SELECT r.word, r.ease, r.interval, r.review_count, r.due_at,
       w.lookup_count
FROM review_queue r
LEFT JOIN words w ON r.word = w.word
WHERE r.due_at <= datetime('now')
ORDER BY r.due_at""")

    upcoming = query("""\
SELECT r.word, r.ease, r.interval, r.review_count, r.due_at
FROM review_queue r
WHERE r.due_at > datetime('now')
ORDER BY r.due_at LIMIT 20""")

    due_html = ""
    for word, ease, interval, rev_cnt, due_at, lookup_cnt in due:
        due_html += f"<tr><td><a href='/words/{word}'>{word}</a></td><td>{ease:.1f}</td><td>{interval}d</td><td>{rev_cnt}</td><td>{due_at}</td><td>{lookup_cnt or 0}</td></tr>"

    if not due_html:
        due_html = '<tr><td colspan="6" class="empty">🎉 没有待复习的单词</td></tr>'

    upcoming_html = ""
    for word, ease, interval, rev_cnt, due_at in upcoming:
        upcoming_html += f"<tr><td><a href='/words/{word}'>{word}</a></td><td>{ease:.1f}</td><td>{interval}d</td><td>{rev_cnt}</td><td>{due_at}</td></tr>"

    if not upcoming_html:
        upcoming_html = '<tr><td colspan="5" class="empty">暂无</td></tr>'

    content = f"""\
<h2>待复习</h2>
<div class="card"><table>
<tr><th>单词</th><th>Ease</th><th>间隔</th><th>复习次数</th><th>到期</th><th>查词</th></tr>
{due_html}
</table></div>

<h2>即将到期</h2>
<div class="card"><table>
<tr><th>单词</th><th>Ease</th><th>间隔</th><th>复习次数</th><th>到期</th></tr>
{upcoming_html}
</table></div>"""

    return page("复习", content)

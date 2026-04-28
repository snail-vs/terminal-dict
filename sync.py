import json
import sqlite3
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()

EXPORT_VERSION = 1


def export_data(db, output_path):
    with sqlite3.connect(db.db_path) as conn:
        words = conn.execute(
            """SELECT word, data, syllables, lookup_count, last_lookup_at
               FROM words"""
        ).fetchall()

        enrichments = conn.execute(
            """SELECT word, source, content, created_at
               FROM word_enrichments"""
        ).fetchall()

        reviews = conn.execute(
            """SELECT word, ease, interval, due_at, review_count, last_reviewed_at
               FROM review_queue"""
        ).fetchall()

    payload = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "words": [],
        "enrichments": [],
        "reviews": [],
    }

    for row in words:
        word, data_json, syl_json, count, last_at = row
        entry = {
            "word": word,
            "data": json.loads(data_json) if data_json else None,
            "syllables": json.loads(syl_json) if syl_json else None,
            "lookup_count": count or 1,
            "last_lookup_at": last_at,
        }
        if entry["data"]:
            payload["words"].append(entry)

    for row in enrichments:
        word, source, content_json, created_at = row
        payload["enrichments"].append({
            "word": word,
            "source": source,
            "content": json.loads(content_json) if content_json else None,
            "created_at": created_at,
        })

    for row in reviews:
        word, ease, interval, due_at, count, last_at = row
        payload["reviews"].append({
            "word": word,
            "ease": ease,
            "interval": interval,
            "due_at": due_at,
            "review_count": count,
            "last_reviewed_at": last_at,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return len(payload["words"]), len(payload["enrichments"]), len(payload["reviews"])


def import_data(db, input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if payload.get("version", 0) > EXPORT_VERSION:
        console.print("[yellow]导出文件版本高于当前版本，部分数据可能无法导入[/yellow]")

    words_added = 0
    words_updated = 0
    enrichments_count = 0
    reviews_count = 0

    with sqlite3.connect(db.db_path) as conn:
        for entry in payload.get("words", []):
            word = entry["word"]
            existing = conn.execute(
                "SELECT lookup_count, last_lookup_at, data, syllables FROM words WHERE word = ?",
                (word,),
            ).fetchone()

            if existing:
                ex_count, ex_last, ex_data, ex_syl = existing
                import_last = entry.get("last_lookup_at")
                import_count = entry.get("lookup_count", 1)
                import_data_json = json.dumps(entry["data"]) if entry.get("data") else ex_data
                import_syl_json = json.dumps(entry["syllables"]) if entry.get("syllables") else ex_syl

                if import_last and (not ex_last or import_last > ex_last):
                    new_count = max(ex_count or 0, import_count or 0)
                    if import_count and ex_count:
                        new_count = ex_count + import_count
                    conn.execute(
                        """UPDATE words SET data = ?, syllables = ?, lookup_count = ?, last_lookup_at = ?
                           WHERE word = ?""",
                        (import_data_json, import_syl_json, new_count, import_last, word),
                    )
                    words_updated += 1
                else:
                    import_data_json = json.dumps(entry["data"]) if entry.get("data") else None
                    import_syl_json = json.dumps(entry["syllables"]) if entry.get("syllables") else None
                    if import_data_json and not ex_data:
                        conn.execute(
                            "UPDATE words SET data = ?, syllables = ? WHERE word = ?",
                            (import_data_json, import_syl_json, word),
                        )
                        words_updated += 1
            else:
                data_json = json.dumps(entry["data"]) if entry.get("data") else None
                syl_json = json.dumps(entry["syllables"]) if entry.get("syllables") else None
                conn.execute(
                    """INSERT OR IGNORE INTO words (word, data, syllables, lookup_count, last_lookup_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (word, data_json, syl_json,
                     entry.get("lookup_count", 1), entry.get("last_lookup_at")),
                )
                words_added += 1

        for entry in payload.get("enrichments", []):
            word = entry["word"]
            source = entry["source"]
            content_json = json.dumps(entry["content"]) if entry.get("content") else None
            conn.execute(
                """INSERT OR REPLACE INTO word_enrichments (word, source, content, created_at)
                   VALUES (?, ?, ?, ?)""",
                (word, source, content_json, entry.get("created_at")),
            )
            enrichments_count += 1

        for entry in payload.get("reviews", []):
            word = entry["word"]
            existing = conn.execute(
                "SELECT ease, interval, review_count, due_at FROM review_queue WHERE word = ?",
                (word,),
            ).fetchone()

            if existing:
                ex_ease, ex_interval, ex_count, ex_due = existing
                im_ease = entry.get("ease", 2.5)
                im_interval = entry.get("interval", 0)
                im_count = entry.get("review_count", 0)
                im_due = entry.get("due_at")

                new_ease = max(ex_ease, im_ease)
                new_count = max(ex_count, im_count)
                if im_due and ex_due:
                    new_due = min(ex_due, im_due)
                elif im_due:
                    new_due = im_due
                else:
                    new_due = ex_due
                new_interval = max(ex_interval, im_interval)

                conn.execute(
                    """UPDATE review_queue SET ease = ?, interval = ?, review_count = ?, due_at = ?,
                       last_reviewed_at = ?
                       WHERE word = ?""",
                    (new_ease, new_interval, new_count, new_due,
                     entry.get("last_reviewed_at"), word),
                )
            else:
                conn.execute(
                    """INSERT OR IGNORE INTO review_queue (word, ease, interval, due_at, review_count, last_reviewed_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (word, entry.get("ease", 2.5), entry.get("interval", 0),
                     entry.get("due_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                     entry.get("review_count", 0), entry.get("last_reviewed_at")),
                )
                reviews_count += 1

        conn.commit()

    return words_added, words_updated, enrichments_count, reviews_count
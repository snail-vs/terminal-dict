import json
import asyncio
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()


def _extract_phonetics(data):
    try:
        word_list = data.get("ec", {}).get("word", []) or \
                    data.get("simple", {}).get("word", [])
        if word_list:
            w = word_list[0]
            return {"us": w.get("usphone", ""), "uk": w.get("ukphone", "")}
    except Exception:
        pass
    return {"us": "", "uk": ""}


def _extract_senses(data):
    try:
        classify = data.get("blng_sents_part", {}).get("trs-classify", [])
        return [item for item in classify
                if not (item["tr"] == "全部" and item["proportion"] == "100%")]
    except Exception:
        return []


def _format_time(timestamp):
    if not timestamp:
        return ""
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return timestamp or ""
    now = datetime.now()
    delta = now - dt
    if delta.days > 30:
        return f"{delta.days // 30}月前"
    if delta.days > 0:
        return f"{delta.days}天前"
    if delta.seconds >= 3600:
        return f"{delta.seconds // 3600}小时前"
    if delta.seconds >= 60:
        return f"{delta.seconds // 60}分钟前"
    return "刚刚"


def _parse_selections(selection_str, max_index):
    if selection_str.strip() == "all":
        return list(range(1, max_index + 1))

    result = set()
    for part in selection_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start, end = map(int, part.split("-", 1))
                result.update(range(start, end + 1))
            except ValueError:
                continue
        else:
            try:
                result.add(int(part))
            except ValueError:
                continue

    return sorted([i for i in result if 1 <= i <= max_index])


class HistoryViewer:
    def __init__(self, db, audio_service, syllable_service, config, page_size=20):
        self.db = db
        self.audio_service = audio_service
        self.syllable_service = syllable_service
        self.config = config
        self.page_size = page_size
        self.page = 1

    def run(self):
        total = self.db.get_total_lookup_count()
        if total == 0:
            console.print("[yellow]暂无查词历史[/yellow]")
            return

        total_pages = (total + self.page_size - 1) // self.page_size
        self.page = 1

        while True:
            offset = (self.page - 1) * self.page_size
            items = self.db.get_lookup_history(self.page_size, offset)

            self._render_table(items, self.page, total_pages)

            cmd = console.input(
                "[dim](n)下一页 (p)上一页 "
                "play 1,3,5 播放 add 1,3,5 加入复习 "
                "review 1,3 复习 (q)退出\n> [/dim]"
            ).strip().lower()

            if cmd in ("q", "quit"):
                break
            elif cmd == "n" and self.page < total_pages:
                self.page += 1
            elif cmd == "p" and self.page > 1:
                self.page -= 1
            elif cmd.startswith("play"):
                self._handle_play(cmd, items)
            elif cmd.startswith("add"):
                self._handle_add(cmd, items)
            elif cmd.startswith("review"):
                self._handle_review(cmd, items)
            else:
                console.print("[yellow]未知命令，请重试[/yellow]")

    def _render_table(self, items, page, total_pages):
        table = Table(
            title=f"查词历史 (第 {page}/{total_pages} 页，共 {self.db.get_total_lookup_count()} 条)",
            show_header=True, header_style="bold", padding=(0, 1),
        )
        table.add_column("#", style="dim", width=4, no_wrap=True)
        table.add_column("单词", style="bold", no_wrap=True)
        table.add_column("音标 / 音节", no_wrap=True)
        table.add_column("核心词义", no_wrap=True)
        table.add_column("次数", justify="right", width=4)
        table.add_column("最后查词", no_wrap=True)

        for i, item in enumerate(items, 1):
            word = item["word"]
            data = item.get("data", {})
            syllables = item.get("syllables")

            ph = _extract_phonetics(data)
            ph_lines = []
            if ph.get("us"):
                ph_lines.append(f"美/{ph['us']}/")
            if ph.get("uk") and ph["uk"] != ph.get("us"):
                ph_lines.append(f"英/{ph['uk']}/")
            if syllables:
                syl_str = syllables.get("syllables", "")
                if syl_str:
                    ph_lines.append(f"[bold]{syl_str.replace('-', '·')}[/bold]")
            ph_text = "\n".join(ph_lines) if ph_lines else ""

            senses = _extract_senses(data)
            sense_lines = []
            for s in senses[:2]:
                sense_lines.append(f"{s['tr']} {s['proportion']}")
            sense_text = "\n".join(sense_lines)

            count = item["count"]
            last_time = _format_time(item["last_time"])

            in_queue = self.db.is_word_in_review_queue(word)
            word_display = f"{word} ✓" if in_queue else word

            table.add_row(
                str(i), word_display, ph_text,
                sense_text, str(count), last_time,
            )

        console.clear()
        console.print(table)

    def _handle_play(self, cmd, items):
        parts = cmd.split()
        if len(parts) < 2:
            console.print("[yellow]用法: play 1,3,5 / play 1-10 / play all [range N] [count N][/yellow]")
            return

        range_count = 1
        count_per_word = 1
        selection_str = parts[1]

        for i, part in enumerate(parts):
            if part == "range" and i + 1 < len(parts):
                try:
                    range_count = max(1, int(parts[i + 1]))
                except ValueError:
                    pass
            elif part == "count" and i + 1 < len(parts):
                try:
                    count_per_word = max(1, int(parts[i + 1]))
                except ValueError:
                    pass

        selected = _parse_selections(selection_str, len(items))
        if not selected:
            console.print("[yellow]未选中有效单词[/yellow]")
            return

        selected_words = [items[i - 1]["word"] for i in selected]
        parts_desc = []
        if range_count > 1:
            parts_desc.append(f"循环 {range_count} 轮")
        if count_per_word > 1:
            parts_desc.append(f"每个 {count_per_word} 遍")
        extra = "，".join(parts_desc)
        console.print(f"[dim]播放 {len(selected_words)} 个单词{f'（{extra}）' if extra else ''}[/dim]")

        asyncio.run(self._play_words_async(selected_words, range_count, count_per_word))

    async def _play_words_async(self, words, range_count, count_per_word):
        loop_delay = self.config.get("pronounce", {}).get("delay", 1.0)
        accent = 1

        for r in range(range_count):
            for word in words:
                console.print(f"[bold]▶ {word}[/bold]")
                await self.audio_service.play_youdao_loop(
                    word, accent, count_per_word, loop_delay,
                )
                if len(words) > 1:
                    await asyncio.sleep(0.3)
            if r < range_count - 1:
                console.print(f"[dim]--- 第 {r + 1} 轮完成 ---[/dim]")

    def _handle_add(self, cmd, items):
        parts = cmd.split()
        if len(parts) < 2:
            console.print("[yellow]用法: add 1,3,5 / add 1-10 / add all[/yellow]")
            return

        selected = _parse_selections(parts[1], len(items))
        if not selected:
            console.print("[yellow]未选中有效单词[/yellow]")
            return

        words = [items[i - 1]["word"] for i in selected]
        self.db.add_words_to_review(words)
        console.print(f"[green]已将 {len(words)} 个单词加入复习队列[/green]")

    def _handle_review(self, cmd, items):
        parts = cmd.split()
        if len(parts) < 2:
            console.print("[yellow]用法: review 1,3,5 / review 1-10 / review all[/yellow]")
            return

        selected = _parse_selections(parts[1], len(items))
        if not selected:
            console.print("[yellow]未选中有效单词[/yellow]")
            return

        words = [items[i - 1]["word"] for i in selected]
        self.db.add_words_to_review(words)
        console.print(f"[green]已将 {len(words)} 个单词加入复习队列[/green]")
        console.print("[dim]请运行 dict-cli review 开始复习[/dim]")

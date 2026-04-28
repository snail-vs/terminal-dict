from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule

console = Console()

QUALITY_LABELS = {
    1: "完全忘了",
    2: "部分记得",
    3: "想了一会儿",
    4: "立刻想起",
}


def sm2_next(quality, ease, interval, review_count):
    """SM-2 算法，quality 1-4"""
    new_ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if new_ease < 1.3:
        new_ease = 1.3

    if quality < 3:
        new_interval = 0
        new_count = 0
    elif review_count == 0:
        new_interval = 1
        new_count = 1
    elif review_count == 1:
        new_interval = 6
        new_count = 2
    else:
        new_interval = round(interval * new_ease)
        new_count = review_count + 1

    due_at = (datetime.now() + timedelta(days=new_interval)).strftime("%Y-%m-%d %H:%M:%S")
    return new_ease, new_interval, due_at


async def run_review(limit, db, audio_service=None, config=None):
    due = db.get_due_reviews(limit)
    if not due:
        console.print("[green]🎉 没有待复习的单词![/green]")
        return

    total = len(due)
    reviewed = 0

    console.print(f"[bold]间隔复习[/bold] 今日待复习: {len(due)} 个\n")

    if audio_service and config:
        pcfg = config.get("pronounce", {})
        audio_enabled = pcfg.get("enabled", True)
        audio_loop = pcfg.get("loop", 1)
        audio_delay = pcfg.get("delay", 1.0)
    else:
        audio_enabled = False
        audio_loop = 1
        audio_delay = 1.0

    for i, item in enumerate(due, 1):
        word = item["word"]
        console.print(f"[bold]{i}/{total}[/bold]  {word}")

        if audio_enabled:
            await audio_service.play_youdao_loop(word, 1, audio_loop, audio_delay)

        # Get word data
        cached = db.get_word(word)
        if not cached:
            continue

        data = cached.get("data", {})
        syllables = cached.get("syllables")
        enrichments = {}

        for src in ("sentence", "etymology", "collocation"):
            val = db.get_enrichment(word, src)
            if val:
                enrichments[src] = val

        console.input("[dim]按回车显示答案...[/dim]")

        # Show phonetics
        ec = data.get("ec", {}).get("word", [{}])[0] if data.get("ec") else {}
        us_ph = ec.get("usphone", "")
        uk_ph = ec.get("ukphone", "")
        ph_line = f" 美/{us_ph}/" if us_ph else ""
        if uk_ph and uk_ph != us_ph:
            ph_line += f"  英/{uk_ph}/"
        if ph_line:
            console.print(ph_line)

        # Show syllables
        if syllables:
            syl = syllables.get("syllables", "").replace("-", "·")
            console.print(f"  音节: [bold]{syl}[/bold]")

        # Show definition
        if "individual" in data and "trs" in data["individual"]:
            for tr in data["individual"]["trs"]:
                console.print(f"  [{tr['pos']}] {tr['tran']}")
        elif "ec" in data and data["ec"].get("word"):
            for tr_group in data["ec"]["word"][0].get("trs", []):
                for tr in tr_group.get("tr", []):
                    meaning = "".join(tr.get("l", {}).get("i", []))
                    if meaning and not meaning.startswith("【"):
                        console.print(f"  {meaning[:80]}")

        # Show enrichments
        if enrichments.get("sentences"):
            console.print(f"  📝 {enrichments['sentences'][0]}")
        if enrichments.get("etymology"):
            console.print(f"  🌱 {enrichments['etymology']}")

        # Quality rating
        while True:
            try:
                q = int(console.input(
                    "\n记得如何? [1]完全忘了 [2]部分记得 [3]想了一会儿 [4]立刻想起\n> "
                ))
                if q in (1, 2, 3, 4):
                    break
            except (ValueError, TypeError):
                pass
            console.print("[yellow]请输入 1-4[/yellow]")

        # Update SM-2
        new_ease, new_interval, due_at = sm2_next(
            q, item["ease"], item["interval"], item["review_count"]
        )
        db.update_review(word, new_ease, new_interval, due_at)
        reviewed += 1

        if new_interval == 0:
            console.print(f"[yellow]明天再复习[/yellow]\n")
        else:
            console.print(f"[green]✓ {new_interval}天后再次复习[/green]\n")

    console.rule("[bold]复习完成[/bold]")
    console.print(f"本次复习: {reviewed}/{total} 个单词")
    remaining = db.get_due_reviews(1)
    if remaining:
        console.print(f"[yellow]还有 {len(remaining)} 个待复习[/yellow]")
    else:
        console.print("[green]🎉 全部完成![/green]")

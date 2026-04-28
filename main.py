import click
import asyncio
import subprocess
import shutil
from dictionary import DictionaryService
from database import DatabaseService
from ai_service import AIService
from syllables import SyllableService
from enrichment import EnrichmentService
from audio import AudioService
from practice import run_practice
from review import run_review
from history import HistoryViewer
from config import load_config
import server
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

console = Console()
db = DatabaseService()
ai = AIService()
dict_service = DictionaryService()
syllable_service = SyllableService(ai)
enrichment_service = EnrichmentService(ai, db)
audio_service = AudioService()
config = load_config()


# ── DefaultGroup：未识别的子命令路由到 lookup ──

class DefaultGroup(click.Group):
    def resolve_command(self, ctx, args):
        if args and args[0] not in self.commands:
            cmd = self.get_command(ctx, "lookup")
            if cmd:
                return "lookup", cmd, list(args)
        return super().resolve_command(ctx, args)


# ═══════════════════════════════════════════════════════════
# 子命令
# ═══════════════════════════════════════════════════════════

@click.group(cls=DefaultGroup, invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """dict-cli - English learning tool in your terminal"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── lookup ──

@cli.command()
@click.argument("word")
@click.option("--uk", is_flag=True, default=False, help="播放英音（默认美音）")
def lookup(word, uk):
    """查英语单词"""
    accent = 2 if uk else 1
    asyncio.run(async_main(word, accent))


# ── fmt ──

@cli.command()
@click.argument("text", nargs=-1, required=True)
@click.option(
    "--type", "-t", "fmt_type", default="auto",
    type=click.Choice(["auto", "commit", "comment", "translate"]),
    help="输出类型（自动、提交信息、代码注释、翻译）",
)
def fmt(text, fmt_type):
    """中译英改写，输出地道英文"""
    full_text = " ".join(text)
    result = asyncio.run(format_text(full_text, fmt_type))
    if result:
        console.print(result)


# ── commit ──

@cli.command()
@click.option("--staged/--all", default=True, help="仅暂存区（默认）或全部变更")
@click.option("--copy", "-c", is_flag=True, default=False, help="复制到剪贴板")
def commit(staged, copy):
    """根据 git diff 生成 commit message"""
    result = asyncio.run(generate_commit(staged))
    if result:
        console.print(result)
        if copy:
            if copy_to_clipboard(result):
                console.print("[dim]✓ 已复制到剪贴板[/dim]")
            else:
                console.print("[yellow]未找到剪贴板工具 (需要 xclip/xsel/pbcopy)[/yellow]")


# ── pronounce / p ──

def _pronounce_cmd(word, uk, loop_count, delay):
    accent = 2 if uk else 1
    asyncio.run(pronounce_async(word, accent, loop_count, delay))

@cli.command()
@click.argument("word")
@click.option("--uk", is_flag=True, default=False, help="英音（默认美音）")
@click.option("--loop", "-l", "loop_count", default=1, type=int, help="循环次数")
@click.option("--delay", "-d", default=1.0, type=float, help="循环间隔（秒）")
def pronounce(word, uk, loop_count, delay):
    """播放单词发音（支持循环）"""
    _pronounce_cmd(word, uk, loop_count, delay)

@cli.command(name="p")
@click.argument("word")
@click.option("--uk", is_flag=True, default=False, help="英音（默认美音）")
@click.option("--loop", "-l", "loop_count", default=1, type=int, help="循环次数")
@click.option("--delay", "-d", default=1.0, type=float, help="循环间隔（秒）")
def p(word, uk, loop_count, delay):
    """播放单词发音（快捷方式）"""
    _pronounce_cmd(word, uk, loop_count, delay)


# ── practice ──

@cli.command()
@click.option(
    "--mode", "-m", default="translate",
    type=click.Choice(["translate", "correct", "dialogue"]),
    help="练习模式",
)
def practice(mode):
    """交互式英语练习（AI 陪练）"""
    asyncio.run(run_practice(mode, ai, db))


# ── review ──

@cli.command()
@click.option("--limit", "-n", default=10, help="本次复习数量")
def review(limit):
    """间隔复习查过的单词（SM-2 算法）"""
    asyncio.run(run_review(limit, db, audio_service, config))


# ── history ──

@cli.command()
@click.option("--page-size", "-n", default=20, help="每页显示条数")
def history(page_size):
    """查看查词历史（交互式）"""
    viewer = HistoryViewer(db, audio_service, syllable_service, config, page_size)
    viewer.run()


# ── serve ──

@cli.command()
@click.option("--host", default="127.0.0.1", help="监听地址")
@click.option("--port", "-p", default=8080, help="端口")
def serve(host, port):
    """启动本地 Web 界面"""
    import uvicorn
    uvicorn.run(server.app, host=host, port=port, log_level="info")


# ═══════════════════════════════════════════════════════════
# 查词核心逻辑
# ═══════════════════════════════════════════════════════════

def extract_phonetics(data):
    """从有道 API 返回的 JSON 中提取音标"""
    try:
        word_list = data.get("ec", {}).get("word", []) or \
                    data.get("simple", {}).get("word", [])
        if word_list:
            w = word_list[0]
            return {"us": w.get("usphone", ""), "uk": w.get("ukphone", "")}
    except Exception:
        pass
    return {"us": "", "uk": ""}


def extract_sense_distribution(data):
    """从有道数据提取词义分布（跳过"全部 100%"汇总）"""
    try:
        classify = data.get("blng_sents_part", {}).get("trs-classify", [])
        return [{"tr": item["tr"], "proportion": item["proportion"]}
                for item in classify
                if not (item["tr"] == "全部" and item["proportion"] == "100%")]
    except Exception:
        return None


def generate_table(word, data, phonetics=None, syllables=None, enrichments=None):
    table = Table(title=f"单词: {word}", show_header=False, padding=(0, 1))
    table.add_column("类型", style="bold", no_wrap=True)
    table.add_column("内容")

    if phonetics:
        ph_parts = []
        if phonetics.get("us"):
            ph_parts.append(f"[bold green]美[/bold green] /{phonetics['us']}/")
        if phonetics.get("uk") and phonetics["uk"] != phonetics.get("us"):
            ph_parts.append(f"[bold blue]英[/bold blue] /{phonetics['uk']}/")
        if ph_parts:
            table.add_row("🔊", "  ".join(ph_parts))

    if syllables:
        syl_str = syllables.get("syllables", "")
        stress = syllables.get("stress", 0)
        if syl_str:
            parts = syl_str.split("-")
            t = Text()
            for i, part in enumerate(parts):
                if i > 0:
                    t.append("·")
                if stress and stress == i + 1:
                    t.append(part, style="bold yellow underline")
                else:
                    t.append(part)
            table.add_row("音节", t)

    if "individual" in data and "trs" in data["individual"]:
        for tr in data["individual"]["trs"]:
            table.add_row(f"[bold cyan]{tr['pos']}[/bold cyan]", tr["tran"])
    elif "ec" in data and data["ec"].get("word"):
        ec_word = data["ec"]["word"][0]
        added = 0
        for tr_group in ec_word.get("trs", []):
            for tr in tr_group.get("tr", []):
                meaning = "".join(tr.get("l", {}).get("i", []))
                if meaning and not meaning.startswith("【"):
                    if ". " in meaning[:10]:
                        pos, text = meaning.split(". ", 1)
                        table.add_row(f"[bold cyan]{pos}.[/bold cyan]", text[:80])
                    else:
                        table.add_row("[bold cyan]释义[/bold cyan]", meaning[:80])
                    added += 1
                    break
            if added >= 5:
                break

    senses = extract_sense_distribution(data)
    if senses:
        parts = [f"[bold]{s['tr']}[/bold] {s['proportion']}" for s in senses]
        table.add_row("📊", " · ".join(parts))

    if enrichments:
        if enrichments.get("sentences"):
            for s in enrichments["sentences"][:2]:
                table.add_row("📝", s)
        if enrichments.get("etymology"):
            table.add_row("🌱", enrichments["etymology"])
        if enrichments.get("collocations"):
            table.add_row("🔗", "  ".join(enrichments["collocations"][:3]))

    return table


async def async_main(word, accent):
    cached = db.get_word(word)
    if cached:
        data = cached["data"]
    else:
        data = dict_service.lookup(word)
        if data:
            db.save_word(word, data)

    if not data:
        console.print("[bold red]未找到单词[/bold red]")
        return

    db.lookup_count(word)

    phonetics = extract_phonetics(data)
    cached_syllables = cached.get("syllables") if cached else None
    cached_enrichments = enrichment_service.get_cached(word) if cached else None

    with Live(
        generate_table(word, data, phonetics, cached_syllables, cached_enrichments),
        refresh_per_second=2, transient=True,
    ) as live:
        tasks = [audio_service.play_youdao(word, accent)]
        if not cached_syllables:
            tasks.append(syllable_service.get_syllables_async(word))
        if not cached_enrichments:
            tasks.append(enrichment_service.get_enrichments_async(word))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        idx = 1
        if not cached_syllables and len(results) > idx:
            syllables = results[idx]
            if isinstance(syllables, dict) and syllables:
                db.update_syllables(word, syllables)
                cached_syllables = syllables
                live.update(generate_table(word, data, phonetics, syllables, cached_enrichments))
            idx += 1

        if not cached_enrichments and len(results) > idx:
            enrichments = results[idx]
            if isinstance(enrichments, dict) and enrichments:
                cached_enrichments = enrichments
                live.update(generate_table(word, data, phonetics, cached_syllables, enrichments))

    console.print(generate_table(word, data, phonetics, cached_syllables, cached_enrichments))
    db.add_to_review_queue(word)


# ── pronounce 异步逻辑 ──

async def pronounce_async(word, accent, loop_count=1, delay=1.0):
    cached = db.get_word(word)
    if cached:
        data = cached["data"]
    else:
        data = dict_service.lookup(word)
        if data:
            db.save_word(word, data)

    if not data:
        console.print("[bold red]未找到单词[/bold red]")
        return

    db.lookup_count(word)

    phonetics = extract_phonetics(data)
    syl_cached = cached.get("syllables") if cached else None

    if not syl_cached:
        syllables = await syllable_service.get_syllables_async(word)
        if isinstance(syllables, dict) and syllables:
            db.update_syllables(word, syllables)
            syl_cached = syllables

    table = Table(title=f"🔊 {word}", show_header=False, padding=(0, 1))
    table.add_column("", style="bold", no_wrap=True)
    table.add_column("内容")

    if syl_cached:
        syl_str = syl_cached.get("syllables", "")
        stress = syl_cached.get("stress", 0)
        if syl_str:
            parts = syl_str.split("-")
            t = Text()
            for i, part in enumerate(parts):
                if i > 0:
                    t.append("·")
                if stress and stress == i + 1:
                    t.append(part, style="bold yellow underline")
                else:
                    t.append(part)
            table.add_row("音节", t)

    if phonetics:
        ph_parts = []
        if phonetics.get("us"):
            ph_parts.append(f"[bold green]美[/bold green] /{phonetics['us']}/")
        if phonetics.get("uk") and phonetics["uk"] != phonetics.get("us"):
            ph_parts.append(f"[bold blue]英[/bold blue] /{phonetics['uk']}/")
        if ph_parts:
            table.add_row("音标", "  ".join(ph_parts))

    senses = extract_sense_distribution(data)
    if senses:
        top = senses[:2]
        parts = [f"[bold]{s['tr']}[/bold] {s['proportion']}" for s in top]
        table.add_row("词义", " · ".join(parts))

    console.print(table)

    await audio_service.play_youdao_loop(word, accent, loop_count, delay)


# ═══════════════════════════════════════════════════════════
# 写作助手核心逻辑
# ═══════════════════════════════════════════════════════════

async def format_text(text, fmt_type="auto"):
    prompts = {
        "commit": "Generate a git commit message in English from the following description. Use conventional commit format (feat:, fix:, chore:, etc). Return ONLY the commit message:\n\n",
        "comment": "Rewrite the following as a clear English code comment. Return ONLY the comment text:\n\n",
        "translate": "Translate the following to natural English. Return ONLY the translation:\n\n",
    }
    instruction = prompts.get(fmt_type, "Rewrite the following as natural English. Return ONLY the result:\n\n")
    result = await ai.chat([{"role": "user", "content": instruction + text}])
    if result:
        db.save_writing_assist(fmt_type, text[:500], result)
    return result


async def generate_commit(staged=True):
    diff = None
    try:
        if staged:
            diff = subprocess.check_output(
                ["git", "diff", "--cached"], text=True, stderr=subprocess.PIPE
            )
        if not diff or not diff.strip():
            diff = subprocess.check_output(
                ["git", "diff"], text=True, stderr=subprocess.PIPE
            )
        if not diff or not diff.strip():
            diff = subprocess.check_output(
                ["git", "diff", "HEAD~1"], text=True, stderr=subprocess.PIPE
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[bold red]error: not a git repository or no changes found[/bold red]")
        return None

    if not diff or not diff.strip():
        console.print("[yellow]no changes to commit[/yellow]")
        return None

    prompt = (
        "Generate a concise git commit message from the following diff. "
        "Use conventional commit format (feat:, fix:, chore:, refactor:, docs:, style:). "
        "Return ONLY the commit message (one-line title + optional body):\n\n"
        f"{diff[:2000]}"
    )
    result = await ai.chat([{"role": "user", "content": prompt}])
    if result:
        db.save_writing_assist("commit", f"git diff ({len(diff)} chars)", result)
    return result


def copy_to_clipboard(text):
    for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "-ib"], ["pbcopy"]]:
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text, text=True, check=False)
            return True
    return False


if __name__ == "__main__":
    cli()

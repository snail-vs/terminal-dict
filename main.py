import click
from .dictionary import DictionaryService
from .database import DatabaseService
from rich.console import Console

console = Console()
db = DatabaseService()
dict_service = DictionaryService()

@click.command()
@click.argument('word')
def main(word):
    """查词工具"""
    # 1. 尝试缓存
    cached = db.get_word(word)
    if cached:
        console.print(f"[bold green]缓存命中[/bold green]: {word}")
        console.print(cached['data'])
        return

    # 2. 网络查询
    console.print(f"[blue]正在查询[/blue]: {word}...")
    data = dict_service.lookup(word)
    
    if data:
        db.save_word(word, data)
        console.print(data)
    else:
        console.print("[bold red]未找到释义[/bold red]")

if __name__ == "__main__":
    main()

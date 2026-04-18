import click
from dictionary import DictionaryService
from database import DatabaseService
from audio import AudioService
from syllables import SyllableService
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
db = DatabaseService()
dict_service = DictionaryService()
audio_service = AudioService()
syllable_service = SyllableService()

@click.command()
@click.argument('word')
@click.option('--play', is_flag=True, help="播放发音")
def main(word, play):
    """查词工具"""
    cached = db.get_word(word)
    
    if cached:
        data = cached['data']
    else:
        data = dict_service.lookup(word)
        if data:
            db.save_word(word, data)
        else:
            console.print(f"[bold red]未找到单词: {word}[/bold red]")
            return

    # 渲染 UI
    # 增加音节显示
    syllables = syllable_service.get_syllables(word)
    
    table = Table(title=f"单词: {word}", show_header=False)
    if syllables:
        table.add_row("[bold yellow]音节[/bold yellow]", "-".join(syllables['s']))

    if 'individual' in data and 'trs' in data['individual']:
        for tr in data['individual']['trs']:
            table.add_row(f"[bold cyan]{tr['pos']}[/bold cyan]", tr['tran'])
            
    console.print(Panel(table, expand=False))
    
    # 音频处理
    if play:
        audio_service.play_youdao(word)

if __name__ == "__main__":
    main()

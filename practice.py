import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

console = Console()

MODE_LABELS = {
    "translate": "中译英",
    "correct": "改错",
    "dialogue": "自由对话",
}


class PracticeService:
    def __init__(self, ai, db):
        self.ai = ai
        self.db = db

    def get_level(self):
        return self.db.get_profile("level") or "intermediate"

    def set_level(self, level):
        if level in ("beginner", "intermediate", "advanced"):
            self.db.set_profile("level", level)
            return True
        return False

    async def generate_prompt(self, mode):
        level = self.get_level()
        if mode == "translate":
            instruction = (
                "Generate a Chinese sentence suitable for a "
                f"{level} English learner in a work/tech context."
            )
        elif mode == "correct":
            instruction = (
                "Write an English sentence with 1-2 deliberate grammar or "
                f"vocabulary errors suitable for a {level} learner. "
                "Errors should be natural mistakes a learner might make."
            )
        else:
            instruction = (
                "Generate a short topic or question for an English conversation "
                f"suitable for a {level} learner in a work context."
            )
        prompt = (
            instruction
            + "\nReturn ONLY a JSON object:\n"
            + '{"prompt": "the text", "hint": "optional brief hint"}'
        )
        return await self.ai.chat_json([{"role": "user", "content": prompt}])

    async def evaluate(self, mode, prompt_text, user_answer):
        if mode == "translate":
            task = f"The student was asked to translate this Chinese to English:\n'{prompt_text}'"
        elif mode == "correct":
            task = f"The student was asked to find and fix errors in:\n'{prompt_text}'"
        else:
            task = f"The student responded to the topic:\n'{prompt_text}'"

        prompt = (
            f"You are an English tutor. {task}\n"
            f"Student's answer: {user_answer}\n\n"
            "Evaluate. Return ONLY JSON:\n"
            '{"correct": true/false, '
            '"correction": "corrected version if wrong", '
            '"feedback": "brief explanation", '
            '"error_tags": ["preposition","tense","article","word_choice","grammar","spelling","punctuation"]}'
        )
        return await self.ai.chat_json([{"role": "user", "content": prompt}])


async def run_practice(mode, ai, db):
    svc = PracticeService(ai, db)
    level = svc.get_level()
    session_id = db.create_practice_session(mode, level)
    start_time = time.time()
    total = 0
    correct = 0

    console.print(f"[bold]开始练习![/bold] 模式: {MODE_LABELS.get(mode, mode)}")
    console.print(
        f"当前水平: [cyan]{level}[/cyan]  "
        f"(输入 [yellow]/level <beginner|intermediate|advanced>[/yellow] 切换)"
    )
    console.print("输入 [red]q[/red] 退出\n")

    try:
        while True:
            prompt_data = await svc.generate_prompt(mode)
            if not prompt_data:
                continue

            console.print(Panel(prompt_data.get("prompt", ""), title="📝 题目"))
            if prompt_data.get("hint"):
                console.print(f"[dim]💡 {prompt_data['hint']}[/dim]")

            answer = console.input("[bold]> [/bold]").strip()

            if answer.lower() in ("q", "quit", "exit"):
                break
            if answer.startswith("/level "):
                lvl = answer.split(" ", 1)[1]
                if svc.set_level(lvl):
                    console.print(f"[green]水平已切换为: {lvl}[/green]")
                    level = lvl
                else:
                    console.print("[yellow]可选: beginner / intermediate / advanced[/yellow]")
                continue
            if not answer:
                continue

            result = await svc.evaluate(mode, prompt_data["prompt"], answer) or {}
            total += 1

            if result.get("correct"):
                correct += 1
                console.print("[bold green]✓ 正确![/bold green]")
            else:
                correction = result.get("correction", "")
                if correction:
                    console.print(f"[bold yellow]参考:[/bold yellow] {correction}")

            feedback = result.get("feedback", "")
            if feedback:
                console.print(f"[dim]{feedback}[/dim]")

            tags = result.get("error_tags", [])
            if tags:
                console.print(f"[red]标记: {', '.join(tags)}[/red]")
            console.print()

            db.save_practice_item(
                session_id, prompt_data["prompt"], answer,
                result.get("correction"), result.get("feedback"),
                tags, result.get("correct"),
            )

    except (KeyboardInterrupt, EOFError):
        pass

    duration = int(time.time() - start_time)
    score = (correct / total * 100) if total > 0 else 0
    db.finish_practice_session(session_id, score, duration)

    console.rule("[bold]练习总结[/bold]")
    score_style = "green" if score >= 70 else "yellow" if score >= 40 else "red"
    console.print(f"得分: [{score_style}]{score:.0f}%[/] ({correct}/{total})")
    console.print(f"用时: {duration // 60}分{duration % 60}秒")

    if total >= 5:
        if score >= 85 and level == "intermediate":
            svc.set_level("advanced")
            console.print("[cyan]→ 建议升级到 advanced![/cyan]")
        elif score >= 80 and level == "beginner":
            svc.set_level("intermediate")
            console.print("[cyan]→ 建议升级到 intermediate![/cyan]")

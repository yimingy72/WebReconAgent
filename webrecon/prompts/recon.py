"""网站信息收集 Agent 系统提示词 — 从 PROMPT.md 加载"""

import sys
from pathlib import Path


def _prompt_dir() -> Path:
    """
    返回 PROMPT.md 所在目录。
    - 正常运行：webrecon/prompts/
    - PyInstaller 打包后：sys._MEIPASS/prompts/
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 运行时，资源文件解压到 sys._MEIPASS
        return Path(sys._MEIPASS) / "prompts"  # type: ignore[attr-defined]
    return Path(__file__).parent


def _load_prompt() -> str:
    """从 PROMPT.md 加载系统提示词"""
    prompt_file = _prompt_dir() / "PROMPT.md"
    return prompt_file.read_text(encoding="utf-8")


def get_recon_prompt(target: str, scope: str | None = None, user_prompt: str | None = None) -> str:
    """
    获取网站信息收集系统提示词。

    Args:
        target:      目标域名或 IP
        scope:       授权范围约束（可选）
        user_prompt: 用户自定义指令，追加到任务末尾（可选）

    Returns:
        完整系统提示词
    """
    prompt = _load_prompt()

    if scope:
        prompt += f"\n\n## 授权范围约束\n{scope}"

    return prompt


def get_task_prompt(target: str, scope: str | None = None, user_prompt: str | None = None) -> str:
    """
    构建发送给 Agent 的任务提示词（用户消息，非系统提示词）。

    Args:
        target:      目标域名或 IP
        scope:       授权范围约束（可选）
        user_prompt: 用户自定义指令（可选）

    Returns:
        任务提示词字符串
    """
    task = f"对目标进行全面的网站信息收集侦察：{target}"

    if scope:
        task += f"\n\n**授权范围**：{scope}"

    task += "\n\n请按照系统提示词中定义的完整侦察流程执行，最终输出结构化情报报告。"

    if user_prompt:
        task += f"\n\n**本次特别要求**：\n{user_prompt}"

    return task

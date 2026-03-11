"""WebReconAgent CLI 入口"""

import argparse
import asyncio
import sys

from rich.console import Console

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="webrecon",
        description="AI-powered 网站信息收集 Agent（基于 Claude Code SDK）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：

  # 基础侦察（使用 Claude Code 已登录的账号）
  webrecon -t example.com

  # 切换模型
  webrecon -t example.com -m claude-sonnet-4-6

  # 侦察完成后交互式选择深入分析
  webrecon -t example.com -i -o report.md

  # 流式输出中实时检测高价值发现
  webrecon -t example.com -r

  # 两种交互模式同时启用
  webrecon -t example.com -r -i -o report.md

  # 自定义本次侦察重点
  webrecon -t example.com -u "重点检测 API 端点，使用 gobuster 进行完整目录爆破"
  webrecon -t example.com -u "只做被动侦察，不要主动扫描"

  # 查看/初始化配置文件
  webrecon --init-config
  webrecon --show-config
        """,
    )

    # 工具管理命令（无需 --target）
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="生成配置文件模板至 ~/.config/webrecon/config.toml",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="显示当前配置",
    )

    # 侦察参数
    parser.add_argument(
        "--target", "-t",
        default=None,
        help="目标域名或 IP，如 example.com 或 192.168.1.1",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="模型名称（覆盖配置文件默认值）。如 claude-opus-4-6 / claude-sonnet-4-6 / claude-haiku-4-5",
    )
    parser.add_argument(
        "--workdir", "-w",
        default=None,
        help="工作目录，侦察结果保存位置（默认：./workspace）",
    )
    parser.add_argument(
        "--scope", "-s",
        default=None,
        help="授权范围约束，如 '仅限 *.example.com，禁止扫描 pay.example.com'",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_false",
        dest="interactive",
        help="禁用交互式跟进分析（默认启用）",
    )
    parser.set_defaults(interactive=True)
    parser.add_argument(
        "--realtime", "-r",
        action="store_true",
        help="启用实时智能检测：流式输出中自动用 LLM 评估发现价值，遇到高价值发现立即暂停询问",
    )
    parser.add_argument(
        "--user-prompt", "-u",
        default=None,
        dest="user_prompt",
        help="自定义本次侦察指令，如 '重点检测 API 端点' 或 '只做被动侦察'。追加到任务末尾，不替换系统提示词",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="将最终报告保存到文件（可选）",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()

    from webrecon.core.config import init_config, load_file_config, show_config

    # 工具管理命令（不需要 --target）
    if args.init_config:
        path = init_config()
        if path.stat().st_size > 0:
            console.print(f"[green]✅ 配置文件已生成：{path}[/green]")
            console.print("[dim]请编辑该文件修改默认模型[/dim]")
        else:
            console.print(f"[yellow]配置文件已存在：{path}[/yellow]")
        return 0

    if args.show_config:
        console.print(show_config())
        return 0

    # 侦察模式需要 --target
    if not args.target:
        console.print("[bold red]错误：请指定目标 --target / -t[/bold red]")
        console.print("运行 webrecon -h 查看帮助")
        return 1

    # 加载配置文件，CLI 参数优先级更高
    file_cfg = load_file_config()
    model = args.model or file_cfg.default_model

    from webrecon.core.agent import run_recon

    result = await run_recon(
        target=args.target,
        working_dir=args.workdir,
        model=model,
        scope=args.scope,
        user_prompt=args.user_prompt,
        interactive=args.interactive,
        realtime=args.realtime,
    )

    if not result.success:
        console.print(f"[bold red]侦察失败：{result.error}[/bold red]")
        return 1

    if args.output:
        from pathlib import Path
        Path(args.output).write_text(result.output, encoding="utf-8")
        console.print(f"[green]报告已保存至：{args.output}[/green]")

    return 0


def main() -> None:
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()

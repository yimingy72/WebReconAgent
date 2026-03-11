"""WebRecon Agent 核心 — 基于 Claude Code SDK"""

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from webrecon.prompts.recon import get_recon_prompt, get_task_prompt

console = Console()


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class ReconFinding:
    """单条侦察发现"""

    category: str        # 类别：subdomain / port / tech / sensitive / info
    content: str         # 发现内容
    detail: str = ""     # 详细说明


@dataclass
class ReconResult:
    """完整侦察结果"""

    success: bool
    target: str
    output: str = ""
    findings: list[ReconFinding] = field(default_factory=list)
    cost_usd: float = 0.0
    error: str | None = None


# ---------------------------------------------------------------------------
# 发现提取：从 Agent 输出中解析关键信息
# ---------------------------------------------------------------------------

# 子域名：形如 sub.example.com 的行
_SUBDOMAIN_RE = re.compile(r"\b([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.){2,}[a-zA-Z]{2,}\b")

# 开放端口：形如 "80/tcp open" 或 "Port 443 open"
_PORT_RE = re.compile(r"(\d{1,5})/(tcp|udp)\s+open|[Pp]ort\s+(\d{1,5})\s+(open|is open)")

# 敏感文件：.git .env .bak 等路径
_SENSITIVE_RE = re.compile(
    r"(https?://[^\s]+(?:\.git|\.env|\.bak|\.old|\.swp|backup|config)[^\s]*"
    r"|/(?:admin|manager|phpmyadmin|wp-admin|swagger|api-docs|actuator|server-status)[^\s]*)",
    re.IGNORECASE,
)


def extract_findings(text: str, target: str) -> list[ReconFinding]:
    """从 Agent 输出文本中提取结构化发现"""
    findings: list[ReconFinding] = []
    seen: set[str] = set()

    # 子域名
    for m in _SUBDOMAIN_RE.finditer(text):
        val = m.group(0).lower().rstrip(".")
        # 只保留与目标相关的子域名
        if target.lower() in val and val not in seen:
            seen.add(val)
            findings.append(ReconFinding(category="subdomain", content=val))

    # 开放端口
    for m in _PORT_RE.finditer(text):
        port = m.group(1) or m.group(3)
        proto = m.group(2) or "tcp"
        key = f"{port}/{proto}"
        if key not in seen:
            seen.add(key)
            findings.append(ReconFinding(category="port", content=key))

    # 敏感路径
    for m in _SENSITIVE_RE.finditer(text):
        val = m.group(0)
        if val not in seen:
            seen.add(val)
            findings.append(ReconFinding(category="sensitive", content=val))

    return findings


# ---------------------------------------------------------------------------
# 核心 Agent
# ---------------------------------------------------------------------------


class WebReconAgent:
    """
    网站信息收集 Agent。

    使用 Claude Code SDK 作为执行引擎：
    - 所有工具调用（nmap/dig/ffuf 等）由 Claude Code CLI 内部执行
    - 本类负责任务下发、消息收集、发现提取、结果汇总

    认证方式（自动判断，优先级：参数 > 环境变量 > OAuth）：
    - 仅传 api_key               → Anthropic 官方 API
    - 同时传 api_key + base_url  → 第三方中转站 / OpenRouter
    - 两者都不传                 → Claude Code CLI 自身的 OAuth 登录

    交互模式：
    - interactive=True  → 侦察全部完成后展示菜单，选择深入分析项（-i）
    - realtime=True     → 流式输出中检测高价值发现，实时暂停询问（-r）
    - 两者同时启用      → 先实时询问，侦察结束后再展示总菜单
    """

    def __init__(
        self,
        target: str,
        working_dir: str | None = None,
        model: str = "claude-opus-4-6",
        scope: str | None = None,
        permission_mode: str = "bypassPermissions",
        user_prompt: str | None = None,
        interactive: bool = True,
        realtime: bool = False,
    ) -> None:
        self.target = target
        self.working_dir = working_dir or str(Path.cwd() / "workspace")
        self.model = model
        self.scope = scope
        self.permission_mode = permission_mode
        self.user_prompt = user_prompt
        self.interactive = interactive
        self.realtime = realtime
        self._client: Any = None
        self._triggered_keys: set[str] = set()
        self._realtime_followups: list[Any] = []

        Path(self.working_dir).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def run(self) -> ReconResult:
        """执行完整侦察流程，返回结构化结果"""
        user_prompt_desc = f"\n[bold cyan]自定义指令：[/bold cyan]{escape(self.user_prompt)}" if self.user_prompt else ""

        modes = []
        if self.realtime:
            modes.append("实时交互 (-r)")
        if self.interactive:
            modes.append("侦察后交互 (-i)")
        mode_desc = f"\n[bold cyan]交互模式：[/bold cyan]{' + '.join(modes)}" if modes else ""

        console.print(Panel(
            f"[bold cyan]目标：[/bold cyan]{escape(self.target)}\n"
            f"[bold cyan]模型：[/bold cyan]{self.model}"
            f"{mode_desc}"
            f"{user_prompt_desc}",
            title="[bold green]WebReconAgent 启动[/bold green]",
            border_style="green",
        ))

        try:
            await self._connect()
            task = self._build_task()
            await self._query(task)
            result = await self._collect_results()
        except Exception as e:
            console.print(f"[bold red]Agent 错误：{escape(str(e))}[/bold red]")
            return ReconResult(success=False, target=self.target, error=str(e))
        finally:
            await self._disconnect()

        # 交互式跟进分析
        if self.interactive and result.success:
            result = await self._run_interactive_followup(result)

        return result

    # ------------------------------------------------------------------
    # 内部方法：SDK 交互
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """连接 Claude Code CLI（使用 Claude Code 自身的认证配置）"""
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

        system_prompt = get_recon_prompt(self.target, self.scope)

        options = ClaudeAgentOptions(
            cwd=self.working_dir,
            permission_mode=self.permission_mode,  # type: ignore[arg-type]
            system_prompt=system_prompt,
            model=self.model,
        )
        self._client = ClaudeSDKClient(options=options)

        result = self._client.connect()
        if result is not None:
            await result

        console.print("[dim]已连接到 Claude Code CLI[/dim]")

    async def _disconnect(self) -> None:
        """断开连接"""
        if self._client:
            result = self._client.disconnect()
            if result is not None:
                await result
            self._client = None

    async def _query(self, prompt: str) -> None:
        """向 Agent 发送任务"""
        if not self._client:
            raise RuntimeError("Agent 未连接")
        result = self._client.query(prompt)
        if result is not None:
            await result

    async def _receive(self) -> AsyncIterator[Any]:
        """接收 Agent 消息流"""
        if not self._client:
            raise RuntimeError("Agent 未连接")
        async for msg in self._client.receive_response():
            yield msg

    # ------------------------------------------------------------------
    # 内部方法：消息处理
    # ------------------------------------------------------------------

    async def _collect_results(self) -> ReconResult:
        """处理消息流，收集输出与发现"""
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

        output_parts: list[str] = []
        all_findings: list[ReconFinding] = []
        cost_usd = 0.0
        self._realtime_followups = []  # 本轮重置

        async for msg in self._receive():

            if isinstance(msg, AssistantMessage):
                for block in msg.content:

                    if isinstance(block, TextBlock):
                        self._print_text(block.text)
                        output_parts.append(block.text)

                        # 结构化发现提取
                        findings = extract_findings(block.text, self.target)
                        all_findings.extend(findings)
                        self._print_findings(findings)

                        # 实时模式：LLM 评估当前输出是否有跟进价值
                        if self.realtime:
                            await self._realtime_check(block.text)

                    elif isinstance(block, ToolUseBlock):
                        self._print_tool(block.name, block.input)

            elif isinstance(msg, ResultMessage):
                cost_usd = getattr(msg, "total_cost_usd", 0.0)

        # 实时模式：主流结束后，统一注入用户已确认的跟进指令
        if self._realtime_followups:
            for i, finding in enumerate(self._realtime_followups, 1):
                console.print(Panel(
                    f"{finding.level}  {finding.description}",
                    title=f"[bold]实时跟进 {i}/{len(self._realtime_followups)}[/bold]",
                    border_style="yellow",
                ))
                await self._query(finding.followup)
                async for msg in self._receive():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                self._print_text(block.text)
                                output_parts.append(block.text)
                                new_findings = extract_findings(block.text, self.target)
                                all_findings.extend(new_findings)
                                self._print_findings(new_findings)
                            elif isinstance(block, ToolUseBlock):
                                self._print_tool(block.name, block.input)
                    elif isinstance(msg, ResultMessage):
                        cost_usd += getattr(msg, "total_cost_usd", 0.0)

        full_output = "\n".join(output_parts)
        self._print_summary(all_findings, cost_usd)

        return ReconResult(
            success=True,
            target=self.target,
            output=full_output,
            findings=all_findings,
            cost_usd=cost_usd,
        )

    # ------------------------------------------------------------------
    # 内部方法：交互式跟进
    # ------------------------------------------------------------------

    async def _run_interactive_followup(self, initial_result: "ReconResult") -> "ReconResult":
        """展示菜单，对用户选择的发现进行深入分析，结果追加到报告"""
        from webrecon.core.followup import (
            extract_followup_items,
            print_followup_header,
            show_followup_menu,
        )

        items = extract_followup_items(initial_result.output)
        if not items:
            console.print("[dim]未提取到可跟进的发现[/dim]")
            return initial_result

        selected = show_followup_menu(items)
        if not selected:
            return initial_result

        # 累积跟进报告
        followup_parts: list[str] = [initial_result.output]
        followup_parts.append("\n\n---\n\n# 深入分析结果\n")
        all_findings = list(initial_result.findings)
        total_cost = initial_result.cost_usd

        for i, item in enumerate(selected, 1):
            print_followup_header(item, i, len(selected))

            try:
                await self._connect()
                # 传入目标 + 跟进指令 + 初始报告摘要作为上下文
                context_prompt = (
                    f"目标：{self.target}\n\n"
                    f"初始侦察已完成，以下是需要你深入分析的具体发现：\n\n"
                    f"{item.prompt}\n\n"
                    f"请直接执行分析，输出精简的漏洞详情格式（证据 + 复现 + 风险）。"
                )
                await self._query(context_prompt)
                sub_result = await self._collect_results()

                followup_parts.append(f"\n## 跟进 {i}：{item.title}\n\n{sub_result.output}")
                all_findings.extend(sub_result.findings)
                total_cost += sub_result.cost_usd

            except Exception as e:
                console.print(f"[bold red]跟进分析失败：{escape(str(e))}[/bold red]")
                followup_parts.append(f"\n## 跟进 {i}：{item.title}\n\n> 分析失败：{e}")
            finally:
                await self._disconnect()

        return ReconResult(
            success=True,
            target=self.target,
            output="\n".join(followup_parts),
            findings=all_findings,
            cost_usd=total_cost,
        )

    # ------------------------------------------------------------------
    # 内部方法：实时检测
    # ------------------------------------------------------------------

    async def _realtime_check(self, text: str) -> None:
        """
        使用 LLM 评估当前文本块是否含有值得立即跟进的安全发现。
        若发现有价值，暂停询问用户；用户确认后将跟进指令加入队列。
        """
        from webrecon.core.followup import RealtimeFinding, assess_finding_potential, ask_realtime_confirm

        finding = await assess_finding_potential(text)
        if not finding:
            return

        # 去重：避免同一发现反复询问
        key = finding.description[:50]
        if key in self._triggered_keys:
            return
        self._triggered_keys.add(key)

        confirmed = await ask_realtime_confirm(finding)
        if confirmed:
            self._realtime_followups.append(finding)

    # ------------------------------------------------------------------
    # 内部方法：任务构建
    # ------------------------------------------------------------------

    def _build_task(self) -> str:
        """构建发送给 Agent 的任务描述"""
        return get_task_prompt(self.target, self.scope, self.user_prompt)

    # ------------------------------------------------------------------
    # 内部方法：Rich 输出
    # ------------------------------------------------------------------

    def _print_text(self, text: str) -> None:
        """打印 Agent 文本输出"""
        console.print(Text(text, style="white"))

    def _print_tool(self, name: str, args: dict[str, Any]) -> None:
        """打印工具调用"""
        cmd = args.get("command", args.get("cmd", str(args)))
        console.print(
            f"[bold yellow]▶ 工具调用[/bold yellow] [cyan]{escape(name)}[/cyan] "
            f"[dim]{escape(str(cmd)[:120])}[/dim]"
        )

    def _print_findings(self, findings: list[ReconFinding]) -> None:
        """打印新发现的条目"""
        icons = {
            "subdomain": "🌐",
            "port": "🔌",
            "tech": "🔧",
            "sensitive": "⚠️ ",
            "info": "ℹ️ ",
        }
        for f in findings:
            icon = icons.get(f.category, "•")
            console.print(
                f"  {icon} [bold]{f.category}[/bold]: [green]{escape(f.content)}[/green]"
            )

    def _print_summary(self, findings: list[ReconFinding], cost: float) -> None:
        """打印最终发现汇总"""
        from collections import Counter
        counts = Counter(f.category for f in findings)

        lines = ["[bold]发现汇总[/bold]"]
        for cat, count in sorted(counts.items()):
            lines.append(f"  • {cat}: {count} 条")
        lines.append(f"\n[dim]总费用：${cost:.4f}[/dim]")

        console.print(Panel("\n".join(lines), title="[bold green]侦察完成[/bold green]", border_style="green"))


# ---------------------------------------------------------------------------
# 便捷入口函数
# ---------------------------------------------------------------------------


async def run_recon(
    target: str,
    working_dir: str | None = None,
    model: str = "claude-opus-4-6",
    scope: str | None = None,
    user_prompt: str | None = None,
    interactive: bool = True,
    realtime: bool = False,
) -> ReconResult:
    """
    执行网站信息收集。

    Args:
        target:      目标域名或 IP
        working_dir: 工作目录
        model:       Claude 模型名称
        scope:       授权范围约束
        user_prompt: 自定义本次侦察指令
        interactive: 是否启用交互式跟进分析（-i）
        realtime:    是否启用实时智能检测模式（-r）

    Returns:
        ReconResult 包含完整输出与结构化发现
    """
    agent = WebReconAgent(
        target=target,
        working_dir=working_dir,
        model=model,
        scope=scope,
        user_prompt=user_prompt,
        interactive=interactive,
        realtime=realtime,
    )
    return await agent.run()

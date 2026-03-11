"""交互式后续分析模块"""

import asyncio
import re
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ---------------------------------------------------------------------------
# 实时发现（-r 模式）
# 使用 LLM 智能判断 Agent 输出是否含有值得立即跟进的安全发现
# 不绑定固定规则，由模型根据语义判断是否有进一步测试的价值
# ---------------------------------------------------------------------------

@dataclass
class RealtimeFinding:
    """LLM 识别的实时高价值发现"""
    description: str        # 发现描述（1-2句）
    followup: str           # 建议的跟进操作
    level: str = "🟠"      # 🔴严重（立即可利用）/ 🟠高风险（需验证）


# LLM 评估提示词
_ASSESS_PROMPT = """\
你是一位经验丰富的渗透测试专家。以下是 AI 侦察 Agent 的一段实时输出。
判断这段文字是否包含「有立即跟进价值的安全发现」，满足以下任一条件即视为有价值：
- 明确发现可访问/可利用的漏洞（源码泄露、配置文件泄露、未授权管理面板等）
- 检测到高风险行为迹象（认证成功、目录遍历启用、敏感接口返回 200 等）
- 发现可被直接利用的服务端点或凭据

不算有价值的情况：
- 纯工具执行过程输出（"正在扫描..."、"已发送请求..."）
- 仅列出扫描结果（端口列表、域名列表）而无明确漏洞结论
- 推测性描述（"可能存在"、"需要进一步确认"）

以 JSON 格式回复（不含其他文字）：
{"has_finding": false}
或
{"has_finding": true, "level": "🔴", "description": "简短描述（1-2句）", "followup": "建议立即执行的具体跟进步骤（200字以内）"}

level 说明：🔴=严重（立即可利用）/ 🟠=高风险（需验证）

Agent 输出片段：
"""


async def assess_finding_potential(text: str) -> RealtimeFinding | None:
    """
    智能评估 Agent 输出片段是否包含值得立即跟进的安全发现。

    优先使用环境变量 ANTHROPIC_API_KEY 调用 LLM 评估（准确）；
    未设置时使用轻量语义启发式（快速）。
    """
    if len(text.strip()) < 150:
        return None

    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if api_key:
        return await _assess_with_llm(text, api_key, os.environ.get("ANTHROPIC_BASE_URL"))
    else:
        return _assess_with_heuristic(text)


async def _assess_with_llm(
    text: str, api_key: str, base_url: str | None
) -> RealtimeFinding | None:
    """调用 LLM 对 Agent 输出进行语义评估"""
    import json

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return _assess_with_heuristic(text)

    client_kwargs: dict = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = AsyncAnthropic(**client_kwargs)
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": _ASSESS_PROMPT + text[:2000],
            }],
        )
        raw = response.content[0].text.strip()
        # 提取 JSON（容错处理）
        if "{" in raw:
            raw = raw[raw.index("{"):raw.rindex("}") + 1]
        data = json.loads(raw)
        if not data.get("has_finding"):
            return None
        return RealtimeFinding(
            description=data.get("description", "检测到高价值安全发现"),
            followup=data.get("followup", "请立即深入分析此发现，验证可利用性并输出漏洞报告。"),
            level=data.get("level", "🟠"),
        )
    except Exception:
        # LLM 调用失败时回退到启发式
        return _assess_with_heuristic(text)


def _assess_with_heuristic(text: str) -> RealtimeFinding | None:
    """
    轻量语义启发式（无 API Key 时的回退方案）。
    检测 Agent 语气中表示"已明确发现某物"的语言模式，而非绑定具体漏洞类型。
    """
    # Agent 表示明确发现/确认某物时使用的语气词
    discovery_signals = [
        "发现了", "检测到", "存在漏洞", "可以访问", "成功访问",
        "泄露", "暴露", "未授权", "弱口令", "成功登录",
        "可下载", "目录列表启用", "directory listing", "200 ok",
        "已确认", "可利用", "存在风险",
    ]
    # 严重等级信号
    critical_signals = ["严重", "高危", "立即", "🔴", "rce", "命令执行", "sql 注入", "sql注入"]

    text_lower = text.lower()
    has_discovery = any(s in text_lower for s in discovery_signals)
    if not has_discovery:
        return None

    level = "🔴" if any(s in text_lower for s in critical_signals) else "🟠"

    # 提取第一个包含发现信号的句子作为描述
    sentences = re.split(r"[。！\n]", text)
    desc = next(
        (s.strip() for s in sentences if any(sig in s.lower() for sig in discovery_signals)),
        "检测到潜在安全发现",
    )[:120]

    return RealtimeFinding(
        description=desc,
        followup="请分析并深入测试上述发现，提供具体的验证步骤和利用路径，输出漏洞报告格式（证据 + 复现 + 风险）。",
        level=level,
    )


async def ask_realtime_confirm(finding: RealtimeFinding) -> bool:
    """
    暂停并询问用户是否立即跟进该发现。
    使用 asyncio executor 非阻塞读取 stdin。
    返回 True 表示确认跟进。
    """
    console.print()
    console.print(Panel(
        f"{finding.level}  {finding.description}\n\n"
        f"[dim]是否立即注入跟进指令，让 Agent 深入分析这个发现？[/dim]",
        title="[bold yellow]实时发现[/bold yellow]",
        border_style="yellow",
    ))
    console.print("[bold]立即跟进？[/bold] [dim](y/N，直接回车=跳过)[/dim] ", end="")

    loop = asyncio.get_event_loop()
    try:
        answer = await loop.run_in_executor(None, input)
        return answer.strip().lower() in ("y", "yes", "是")
    except (EOFError, KeyboardInterrupt):
        return False


# 严重等级对应的颜色
_LEVEL_STYLE = {
    "🔴": "bold red",
    "🟠": "bold yellow",
    "🟡": "yellow",
    "🟢": "green",
}


@dataclass
class FollowUpItem:
    """单条可跟进的发现"""

    index: int
    level: str          # 🔴 / 🟠 / 🟡 / 🟢
    title: str          # 标题
    description: str    # 完整描述（原文）
    prompt: str         # 传给 Agent 的跟进指令


def extract_followup_items(report_text: str) -> list[FollowUpItem]:
    """
    从报告文本中提取"下一步建议"部分的条目。
    同时补充漏洞摘要中的严重/高危项。
    """
    items: list[FollowUpItem] = []

    # 1. 提取"下一步建议"章节
    suggestion_block = _extract_section(report_text, "下一步建议")
    if suggestion_block:
        items.extend(_parse_suggestions(suggestion_block))

    # 2. 如果没有建议章节，回退到漏洞摘要的严重/高危行
    if not items:
        items.extend(_parse_vuln_table(report_text))

    return items


def _extract_section(text: str, heading: str) -> str:
    """提取指定标题的章节内容"""
    pattern = rf"##\s+.*{re.escape(heading)}.*\n([\s\S]*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def _parse_suggestions(block: str) -> list[FollowUpItem]:
    """解析编号列表，如 '1. **xxx** ...'"""
    items: list[FollowUpItem] = []
    # 匹配 "1. **标题**：说明" 或 "1. 🔴 **标题**"
    pattern = re.compile(
        r"^\d+\.\s+(?P<content>.+?)$",
        re.MULTILINE,
    )
    for m in pattern.finditer(block):
        content = m.group("content").strip()
        # 检测严重级别
        level = "🟡"
        for marker in ("🔴", "🟠", "🟡", "🟢"):
            if marker in content:
                level = marker
                break
        # 清理 markdown 加粗
        title = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
        title = re.sub(r"`[^`]+`", "", title).strip()
        # 截取前80字作为标题
        short_title = title[:80] + ("..." if len(title) > 80 else "")

        items.append(FollowUpItem(
            index=len(items) + 1,
            level=level,
            title=short_title,
            description=content,
            prompt=_build_followup_prompt(content),
        ))
    return items


def _parse_vuln_table(text: str) -> list[FollowUpItem]:
    """从漏洞摘要表格中提取严重/高危行"""
    items: list[FollowUpItem] = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        if "🔴" in line or "🟠" in line:
            level = "🔴" if "🔴" in line else "🟠"
            # 提取第二列（漏洞名）
            cols = [c.strip() for c in line.split("|") if c.strip()]
            if len(cols) >= 2:
                title = re.sub(r"\*\*([^*]+)\*\*", r"\1", cols[1])[:80]
                items.append(FollowUpItem(
                    index=len(items) + 1,
                    level=level,
                    title=title,
                    description=line,
                    prompt=_build_followup_prompt(title),
                ))
    return items


def _build_followup_prompt(description: str) -> str:
    """根据发现描述生成跟进指令"""
    desc_lower = description.lower()

    # SourceMap / JS 分析
    if any(k in desc_lower for k in ["sourcemap", "source map", ".map", "源码泄露", "js.map"]):
        return (
            "根据初始侦察发现的 SourceMap 泄露，执行以下深入分析：\n"
            "1. 下载所有 .js.map 文件\n"
            "2. 使用 source-map 工具还原完整源代码结构\n"
            "3. 提取所有 API 路由和端点\n"
            "4. 搜索硬编码的凭据、Token、内部 IP\n"
            "5. 分析认证和鉴权逻辑\n"
            "将分析结果整理为漏洞报告格式，重点突出可利用的发现。\n"
            f"\n原始发现：{description}"
        )

    # 默认凭据
    if any(k in desc_lower for k in ["默认凭据", "弱口令", "admin", "default", "password", "123456"]):
        return (
            "根据初始侦察发现的默认/弱口令，执行以下验证：\n"
            "1. 尝试所有已发现的默认凭据组合\n"
            "2. 成功登录后提取用户信息、权限列表、敏感配置\n"
            "3. 枚举已登录状态可访问的敏感接口\n"
            "4. 检查 Token 机制（有效期、刷新逻辑）\n"
            "结果以漏洞格式输出，包含复现步骤和影响范围。\n"
            f"\n原始发现：{description}"
        )

    # Swagger / API 文档
    if any(k in desc_lower for k in ["swagger", "api-docs", "openapi", "api 文档", "接口文档"]):
        return (
            "根据初始侦察发现的 API 文档暴露，执行以下深入分析：\n"
            "1. 下载完整 Swagger/OpenAPI JSON\n"
            "2. 枚举所有端点（GET/POST/PUT/DELETE）\n"
            "3. 对每个端点测试未授权访问（无 Token / 低权限 Token）\n"
            "4. 重点测试涉及用户、权限、数据管理的敏感端点\n"
            "5. 检查是否存在水平越权或垂直越权\n"
            f"\n原始发现：{description}"
        )

    # CORS
    if any(k in desc_lower for k in ["cors", "跨域", "cross-origin"]):
        return (
            "根据初始侦察发现的 CORS 配置错误，执行以下验证：\n"
            "1. 测试所有敏感 API 端点的 CORS 响应头\n"
            "2. 验证是否接受任意 Origin 且允许携带凭据\n"
            "3. 构造 PoC 演示实际可窃取的信息（Token、用户数据）\n"
            "4. 检查是否影响登录、注销、账户管理等敏感操作\n"
            f"\n原始发现：{description}"
        )

    # Druid / 监控面板
    if any(k in desc_lower for k in ["druid", "actuator", "监控", "控制台", "管理后台"]):
        return (
            "根据初始侦察发现的监控/管理面板暴露，执行以下深入分析：\n"
            "1. 提取所有数据库连接信息（地址、用户名、密码）\n"
            "2. 查看 SQL 历史记录，寻找敏感数据表\n"
            "3. 枚举所有 Actuator 端点（/env, /heapdump, /mappings, /beans）\n"
            "4. 尝试通过 /env 获取敏感环境变量\n"
            "5. 如有 /heapdump，分析内存转储中的凭据\n"
            f"\n原始发现：{description}"
        )

    # 通用跟进
    return (
        f"对以下发现进行深入分析，尝试获取更多信息或验证可利用性：\n\n{description}\n\n"
        "要求：\n"
        "1. 提供具体的验证步骤和命令\n"
        "2. 确认实际影响范围\n"
        "3. 如发现新漏洞，按漏洞格式输出（证据 + 复现 + 风险）"
    )


def show_followup_menu(items: list[FollowUpItem]) -> list[FollowUpItem]:
    """
    展示交互式菜单，返回用户选择的条目。
    输入格式：编号空格分隔（如 "1 3"），all 全选，直接回车跳过。
    """
    if not items:
        return []

    # 展示菜单表格
    table = Table(
        title="发现以下值得深入分析的点",
        show_header=True,
        header_style="bold",
        border_style="dim",
        expand=True,
    )
    table.add_column("#", width=3, justify="right")
    table.add_column("级别", width=4)
    table.add_column("内容", ratio=1)

    for item in items:
        style = _LEVEL_STYLE.get(item.level, "")
        table.add_row(
            str(item.index),
            item.level,
            item.title,
            style=style,
        )

    console.print()
    console.print(table)
    console.print(
        "\n[bold]请选择要深入分析的项目[/bold]"
        "（输入编号，空格分隔，如 [cyan]1 3[/cyan]；[cyan]all[/cyan] 全选；直接回车跳过）：",
        end=" ",
    )

    try:
        raw = input().strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]跳过深入分析[/dim]")
        return []

    if not raw:
        console.print("[dim]跳过深入分析[/dim]")
        return []

    if raw.lower() == "all":
        return items

    selected = []
    for token in raw.split():
        try:
            idx = int(token)
            match = next((i for i in items if i.index == idx), None)
            if match:
                selected.append(match)
        except ValueError:
            pass

    return selected


def print_followup_header(item: FollowUpItem, current: int, total: int) -> None:
    """打印深入分析的章节标题"""
    console.print(Panel(
        f"{item.level}  {item.title}",
        title=f"[bold]深入分析 {current}/{total}[/bold]",
        border_style="yellow",
    ))

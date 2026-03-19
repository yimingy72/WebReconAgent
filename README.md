# WebReconAgent

AI 驱动的网站信息收集 Agent，基于 Claude Code SDK。

通过自然语言系统提示词引导大模型自主执行侦察任务：DNS 枚举、子域名发现、端口扫描、Web 指纹识别、敏感路径探测等，最终输出以漏洞为核心的结构化情报报告。发现高价值漏洞后可通过交互式菜单选择深入分析。

---

## 快速开始

### macOS

**1. 安装 Node.js（用于 Claude Code CLI）**

从 https://nodejs.org 下载安装，或用 Homebrew：

```bash
brew install node
```

**2. 安装 Claude Code CLI**

```bash
npm install -g @anthropic-ai/claude-code
```

**3. 安装 uv**

```bash
# 推荐（国内网络）
pip install uv -i https://mirrors.aliyun.com/pypi/simple/

# 或 Homebrew
brew install uv
```

**4. 安装 WebReconAgent**

```bash
git clone https://github.com/yimingy72/WebReconAgent.git
cd WebReconAgent
uv tool install .
```

**5. 配置 PATH**

`uv tool install` 完成后会提示 `~/.local/bin` 不在 PATH 中，执行：

```bash
echo 'export PATH="/Users/$USER/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**6. 运行**

```bash
webrecon --init-config        # 生成配置文件
webrecon -t example.com       # 开始侦察
```

---

### Windows

**1. 安装 Node.js**

从 https://nodejs.org 下载安装（LTS 版本）。

**2. 安装 Claude Code CLI**

在 PowerShell 中执行：

```powershell
npm install -g @anthropic-ai/claude-code
```

**3. 安装 uv**

```powershell
# 推荐（国内网络，需已有 Python）
pip install uv -i https://mirrors.aliyun.com/pypi/simple/

# 或官方脚本（需能访问 GitHub）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**4. 安装 WebReconAgent**

```powershell
git clone https://github.com/yimingy72/WebReconAgent.git
cd WebReconAgent
uv tool install .
```

**5. 配置 PATH**

`uv tool install` 完成后会提示可执行文件路径（通常为 `%USERPROFILE%\.local\bin`），将其加入系统环境变量：

- 打开「系统属性」→「高级」→「环境变量」
- 在「用户变量」的 `Path` 中添加 `%USERPROFILE%\.local\bin`
- 重新打开 PowerShell 生效

或在当前 PowerShell 会话临时生效：

```powershell
$env:PATH += ";$env:USERPROFILE\.local\bin"
```

**6. 运行**

```powershell
webrecon --init-config        # 生成配置文件
webrecon -t example.com       # 开始侦察
```

---

## 前提条件说明

- **Claude Code CLI**：WebReconAgent 通过 Claude Code SDK 驱动 `claude` 子进程执行所有系统工具（nmap、dig、ffuf 等），`claude` 命令必须在系统 PATH 中可访问。
- **uv**：Python 包管理器，用于安装和运行 WebReconAgent。方式二和方式三均需要。

---

## 其他安装方式

### 方式一：下载预编译可执行文件（无需 Python）

> ⚠️ **当前暂无可用的预编译文件**，Releases 页面尚未发布构建产物。请使用下方方式二或方式三。

预编译文件发布后，可从 [Releases](../../releases) 页面下载对应平台的文件直接运行，无需 Python 环境。

### 方式二：uv tool install（安装为系统命令）

安装后可直接使用 `webrecon`，无需每次写 `uv run`：

```bash
cd WebReconAgent
uv tool install .

# 之后直接使用
webrecon --init-config
webrecon -t example.com -i -o report.md
```

卸载：`uv tool uninstall webrecon`

### 方式三：源码开发模式

```bash
cd WebReconAgent
uv sync
uv run webrecon -t example.com
```

---

## 配置文件

认证由 **Claude Code CLI 自身管理**（OAuth 登录或 CLI 配置），无需在此配置。
配置文件只用于设置默认模型：

```bash
webrecon --init-config    # 生成模板到 ~/.config/webrecon/config.toml
webrecon --show-config    # 查看当前配置
```

配置文件（`~/.config/webrecon/config.toml`）：

```toml
[model]
default = "claude-sonnet-4-6"    # 默认模型
```

---

## 参数说明

| 参数 | 简写 | 说明 |
|------|------|------|
| `--target` | `-t` | 目标域名或 IP（必填） |
| `--no-interactive` | | 禁用交互式跟进分析（默认启用） |
| `--realtime` | `-r` | 实时智能检测：流式输出中自动用 LLM 评估发现价值，遇到高价值发现立即暂停询问 |
| `--model` | `-m` | 模型名称，覆盖配置文件默认值 |
| `--user-prompt` | `-u` | 自定义本次侦察指令，追加到任务末尾（不替换系统提示词） |
| `--scope` | `-s` | 授权范围约束 |
| `--workdir` | `-w` | 工作目录（默认：`./workspace`） |
| `--output` | `-o` | 报告保存路径 |
| `--init-config` | | 生成配置文件模板 |
| `--show-config` | | 查看当前配置 |

---

## 常用命令

```bash
# 基础侦察（默认启用交互式跟进分析）
webrecon -t example.com

# 保存报告
webrecon -t example.com -o report.md

# 禁用交互式跟进（直接结束，不询问）
webrecon -t example.com --no-interactive -o report.md

# 实时智能检测：流式输出中遇到高价值发现立即暂停询问
webrecon -t example.com -r -o report.md

# 两者同时启用：实时询问 + 侦察结束后展示总菜单
webrecon -t example.com -r -o report.md

# 限定授权范围
webrecon -t example.com -s "仅限 *.example.com，禁止测试 pay.example.com"

# 切换模型
webrecon -t example.com -m claude-sonnet-4-6   # 更快更便宜
webrecon -t example.com -m claude-haiku-4-5    # 最快

# 自定义本次侦察重点（不修改系统提示词，仅影响本次运行）
webrecon -t example.com -u "重点检测 API 端点，使用 gobuster 进行完整目录爆破"
webrecon -t example.com -u "只做被动侦察，不执行任何主动扫描"
webrecon -t example.com -u "重点关注 JS 文件分析和参数发现"

# 组合使用
webrecon -t example.com -m claude-sonnet-4-6 -s "仅限主域名" -o report.md
```

---

## 交互式跟进分析（默认启用）

初始侦察完成后，自动从报告"下一步建议"中提取可跟进项，展示菜单供选择：

```
┌───────────────────────────────────────────────────────────┐
│                  发现以下值得深入分析的点                     │
├───┬────┬─────────────────────────────────────────────────┤
│ # │ 级 │ 内容                                            │
├───┼────┼─────────────────────────────────────────────────┤
│ 1 │ 🔴 │ 立即利用 CORS 漏洞，验证是否可窃取用户 Token      │
│ 2 │ 🔴 │ 利用 Druid 弱口令提取数据库连接信息               │
│ 3 │ 🔴 │ 验证 admin:admin123 默认凭据                     │
│ 4 │ 🟠 │ 深入测试 Swagger 暴露的接口权限                  │
│ 5 │ 🟠 │ MinIO 暴力破解默认凭据                           │
└───┴────┴─────────────────────────────────────────────────┘

请选择要深入分析的项目（输入编号，空格分隔；all 全选；回车跳过）：
> 1 3
```

根据发现类型自动生成针对性跟进指令：

| 发现类型 | 自动跟进内容 |
|---------|------------|
| SourceMap 泄露 | 下载 .map 文件 → 还原源码 → 提取 API 路由和硬编码凭据 |
| 默认 / 弱口令 | 尝试凭据登录 → 提取权限和 Token → 枚举敏感接口 |
| Swagger 暴露 | 枚举全部端点 → 测试未授权访问 → 检测越权 |
| CORS 错误配置 | 测试所有敏感端点 → 构造 PoC 验证实际影响 |
| Druid / Actuator | 提取数据库连接 → 读取 /env /heapdump → 内网拓扑 |

跟进分析结果自动追加到 `-o` 指定的报告文件末尾。

---

## 实时智能检测（`-r`）

在 Agent 流式输出中，每收到一段实质性文本，自动调用 LLM（claude-haiku-4-5）评估是否包含值得立即跟进的安全发现。发现高价值内容时立即暂停，询问是否注入跟进指令：

```
╭─────────────────────────────────╮
│          实时发现                │
│                                  │
│  🔴  .env 文件可访问，内容含      │
│       数据库密码和 API Key        │
│                                  │
│  是否立即注入跟进指令？            │
╰─────────────────────────────────╯
立即跟进？ (y/N，直接回车=跳过) y
```

- **有 API Key**：调用 `claude-haiku-4-5` 进行语义判断，不依赖固定规则，能识别任意类型的高价值发现
- **OAuth 模式（无 API Key）**：使用轻量语义启发式，检测 Agent 的"已确认发现"语气
- 用户确认后，跟进指令在**当前侦察流完成后**自动注入，不中断正常侦察节奏
- 可与 `-i` 同时使用：`-r` 处理流式中发现，`-i` 在结束后展示总菜单

---

## 模型参考

| 模型 | 速度 | 能力 | 适用场景 |
|------|------|------|---------|
| `claude-opus-4-6` | 慢 | 最强 | 复杂目标，默认推荐 |
| `claude-sonnet-4-6` | 中 | 强 | 日常使用，性价比高 |
| `claude-haiku-4-5` | 快 | 一般 | 快速预览，简单目标 |

> 切换模型只需在 Claude Code CLI 配置中修改，或使用 `-m` 参数指定。

---

## 自定义系统提示词

系统提示词保存为可直接编辑的 Markdown 文件，无需修改 Python 代码，修改后立即生效：

```
webrecon/prompts/PROMPT.md
```

`-u` 与 `PROMPT.md` 的区别：

| | `PROMPT.md` | `-u` / `--user-prompt` |
|-|-------------|----------------------|
| 作用范围 | 所有运行 | 仅本次运行 |
| 修改方式 | 编辑文件 | 命令行参数 |
| 适合场景 | 修改侦察流程、报告格式 | 临时调整侦察重点 |

---

## 打包为可执行文件

### 本地打包

```bash
uv sync                              # 安装含 PyInstaller 的开发依赖

bash scripts/build.sh                # 当前平台（Linux / macOS）
bash scripts/build.sh --platform mac-universal  # macOS 双架构（需 Apple Silicon）

# 产物：dist/webrecon
```

### GitHub Actions 自动构建

推送 tag 后自动构建四平台可执行文件并发布到 Releases：

```bash
git tag v1.0.0
git push origin v1.0.0
# 自动构建：Linux x86_64 / macOS Intel / macOS ARM / Windows x86_64
```

---

## 项目结构

```
WebReconAgent/
├── webrecon/
│   ├── core/
│   │   ├── agent.py        # Agent 核心（Claude Code SDK 集成）
│   │   ├── config.py       # 配置文件加载
│   │   └── followup.py     # 交互式跟进分析
│   ├── prompts/
│   │   ├── PROMPT.md       # 系统提示词（可直接编辑）
│   │   └── recon.py        # 提示词加载器
│   └── main.py             # CLI 入口
├── .github/
│   └── workflows/
│       └── build.yml       # GitHub Actions 多平台自动构建
├── scripts/
│   └── build.sh            # 本地打包脚本
├── webrecon.spec           # PyInstaller 打包配置
├── workspace/              # 侦察工作目录（运行时自动创建）
├── pyproject.toml
└── .env.example

~/.config/webrecon/config.toml   # 全局配置文件（--init-config 生成）
```

---

## 工作原理

```
webrecon CLI
    ↓ 合并配置（CLI 参数 > 环境变量 > 配置文件）
WebReconAgent
    ↓ 加载 PROMPT.md 作为系统提示词
Claude Code CLI（子进程）
    ↓ 大模型自主决策，调用系统工具
[nmap / dig / ffuf / gobuster / curl ...]
    ↓ 工具执行结果返回给模型，流式输出文本块

    ┌─────────── 启用 -r 时 ────────────────────────────────┐
    │ 每个文本块 → claude-haiku-4-5 语义评估                 │
    │     ├─ 无价值发现 → 继续接收                           │
    │     └─ 检测到高价值发现 → 暂停，询问用户               │
    │             ├─ 跳过 → 继续接收                        │
    │             └─ 确认 → 记录跟进指令，继续接收            │
    └───────────────────────────────────────────────────────┘

WebReconAgent 提取结构化发现，汇总输出报告

    ┌─────────── 启用 -r，且有已确认跟进项时 ───────────────┐
    │ 逐条注入跟进指令 → Claude Code CLI 深入分析            │
    │ 跟进结果追加到报告                                     │
    └───────────────────────────────────────────────────────┘

    ┌─────────── 启用 -i 时 ────────────────────────────────┐
    │ 从报告"下一步建议"提取可跟进项                          │
    │ 展示交互式菜单 → 用户选择                              │
    │ Claude Code CLI 针对选中项再次执行深入分析              │
    │ 跟进结果追加到报告                                     │
    └───────────────────────────────────────────────────────┘
```

**`-r` 与 `-i` 的区别：**

| | `-r` 实时智能检测 | `-i` 侦察后菜单 |
|-|-----------------|----------------|
| 触发时机 | 流式输出中实时触发 | 侦察全部完成后 |
| 判断方式 | LLM 语义评估（不绑定固定规则） | 解析报告"下一步建议"章节 |
| 适合场景 | 希望第一时间跟进高价值发现 | 希望看完全貌再选择性深入 |
| 组合使用 | `-r -i` 两者互补，先实时响应，再系统性跟进 | |

---

## 注意事项

- 请确保仅对**授权目标**使用本工具
- 建议通过 `--scope` 明确限定测试范围
- 在已有 Claude Code 会话内无法嵌套启动，请在**系统终端**直接运行

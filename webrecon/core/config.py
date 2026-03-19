"""配置文件管理 — 读取 ~/.config/webrecon/config.toml"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "webrecon"
CONFIG_FILE = CONFIG_DIR / "config.toml"

CONFIG_TEMPLATE = """\
# WebReconAgent 配置文件
# 路径：~/.config/webrecon/config.toml
#
# 认证由 Claude Code CLI 自身管理（OAuth 登录或 CLI 配置）
# 此文件只需配置模型偏好

[model]
# 默认模型名称
# Anthropic 官方：claude-opus-4-6 / claude-sonnet-4-6 / claude-haiku-4-5
default = "claude-opus-4-6"
"""


@dataclass
class FileConfig:
    """从配置文件读取的配置项"""

    default_model: str = "claude-opus-4-6"


def load_file_config() -> FileConfig:
    """加载配置文件，文件不存在时返回默认值"""
    if not CONFIG_FILE.exists():
        return FileConfig()

    with CONFIG_FILE.open("rb") as f:
        data = tomllib.load(f)

    model = data.get("model", {})
    return FileConfig(
        default_model=model.get("default", "claude-opus-4-6").strip(),
    )


def init_config() -> Path:
    """生成配置文件模板，已存在时不覆盖"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        return CONFIG_FILE

    CONFIG_FILE.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    return CONFIG_FILE


def show_config() -> str:
    """返回当前配置摘要"""
    cfg = load_file_config()

    lines = [
        f"配置文件：{CONFIG_FILE}",
        f"  存在：{'✅' if CONFIG_FILE.exists() else '❌ 未创建，运行 webrecon --init-config 生成'}",
        "",
        "[model]",
        f"  default  = {cfg.default_model}",
    ]
    return "\n".join(lines)

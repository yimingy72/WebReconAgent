# webrecon.spec — PyInstaller 打包配置
# 用法：pyinstaller webrecon.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["webrecon/main.py"],
    pathex=["."],
    binaries=[],
    # 将 PROMPT.md 打包进可执行文件
    datas=[
        ("webrecon/prompts/PROMPT.md", "prompts"),
    ],
    hiddenimports=[
        "webrecon.core.agent",
        "webrecon.core.config",
        "webrecon.core.followup",
        "webrecon.prompts.recon",
        "claude_agent_sdk",
        "rich.console",
        "rich.panel",
        "rich.table",
        "rich.markup",
        "rich.text",
        "pydantic",
        "pydantic_settings",
        "dotenv",
        "tomllib",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="webrecon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # 命令行工具，保留控制台
    disable_windowed_traceback=False,
    target_arch=None,      # None = 当前架构；"universal2" = Mac 双架构
    codesign_identity=None,
    entitlements_file=None,
)

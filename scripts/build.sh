#!/usr/bin/env bash
# scripts/build.sh — 本地打包脚本
# 用法：bash scripts/build.sh [--platform linux|mac|mac-universal]

set -e

PLATFORM=${1:-$(uname -s | tr '[:upper:]' '[:lower:]')}
OUT_DIR="dist"

echo "==> 安装 PyInstaller..."
uv pip install pyinstaller

echo "==> 开始打包 (平台: $PLATFORM)..."

case "$PLATFORM" in
  "--platform linux" | "linux")
    pyinstaller webrecon.spec \
      --distpath "$OUT_DIR" \
      --workpath build/linux \
      --clean
    echo "==> 产物: $OUT_DIR/webrecon  (Linux x86_64)"
    ;;

  "--platform mac" | "darwin")
    pyinstaller webrecon.spec \
      --distpath "$OUT_DIR" \
      --workpath build/mac \
      --clean
    echo "==> 产物: $OUT_DIR/webrecon  (macOS $(uname -m))"
    ;;

  "--platform mac-universal")
    # 需要在 Apple Silicon Mac 上运行，使用 target_arch=universal2
    sed -i '' 's/target_arch=None/target_arch="universal2"/' webrecon.spec
    pyinstaller webrecon.spec \
      --distpath "$OUT_DIR" \
      --workpath build/mac-universal \
      --clean
    # 恢复 spec
    sed -i '' 's/target_arch="universal2"/target_arch=None/' webrecon.spec
    echo "==> 产物: $OUT_DIR/webrecon  (macOS Universal x86_64+arm64)"
    ;;

  *)
    echo "用法: bash scripts/build.sh [--platform linux|mac|mac-universal]"
    exit 1
    ;;
esac

echo ""
echo "打包完成！验证："
"$OUT_DIR/webrecon" --help

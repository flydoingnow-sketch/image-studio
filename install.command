#!/bin/zsh
set -e
cd "${0:A:h}"
if ! command -v python3.12 >/dev/null; then
 echo '请先安装 Python 3.12、Google Chrome，以及 FFmpeg（或构建内置工具）。'
 exit 1
fi
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
echo '依赖安装完成。双击 start.command 启动。'

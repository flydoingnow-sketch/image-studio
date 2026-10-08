#!/bin/zsh
set -e
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ ! -x .venv/bin/python ]]; then
 echo '请先运行 install.command 安装依赖。'
 exit 1
fi
exec .venv/bin/python launcher.py

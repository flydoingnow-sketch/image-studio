#!/bin/zsh
set -e
echo '影像工作台：检查运行环境'
echo '新版安装包已内置 Python、FFmpeg 和 FFprobe，无需安装 Homebrew，无需联网下载视频处理工具。'
echo '工作台页面可以用 Safari 打开；自动登录和发布仍使用 Google Chrome。'
if [[ ! -x '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' && ! -x "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
 echo '请从 Google 官方网站安装 Chrome，完成后重新打开工作台。'
 open 'https://www.google.com/chrome/'
else
 echo 'Google Chrome 已安装。'
fi
read 'reply?按回车键结束。'

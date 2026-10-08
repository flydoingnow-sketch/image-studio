# 构建 Apple Silicon Mac 安装包

目标为 Apple 芯片、macOS 14+。构建过程不读取用户的数据目录，安装版首次打开也没有预置工作区。当前脚本使用临时签名，没有 Apple 开发者签名或公证。

## 1. 安装依赖

按 README 创建 Python 3.12 的 `.venv` 并安装 requirements.txt。打包时从虚拟环境复制 Python 包。

## 2. 构建离线视频工具

```sh
zsh distribution/build_ffmpeg.command
```

需要 Apple Command Line Tools、curl 和编译工具。脚本从 FFmpeg 官方下载固定版本源码，校验 SHA256，然后生成 `media-tools/bin/ffmpeg`、`ffprobe`，同时保存原始完整源码、LGPL 许可及构建命令。首次构建需联网下载源码；打包后使用者不需要联网下载视频工具。源程序禁用网络协议，不链接 Homebrew 的第三方动态库。

## 3. 准备可搬运的 Python 运行时

使用 Python 3.12 的 Apple Silicon 独立运行时（例如 [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 的 install-only 版本），目录中应有 `bin/python3.12`、`lib/python3.12`。不能简单复制依赖原机器外部 Framework 的 Python 安装。

```sh
export IMAGE_STUDIO_PYTHON_RUNTIME="/absolute/path/to/standalone-python"
.venv/bin/python distribution/build_macos.py
```

默认从 `.venv/lib/python3.12/site-packages` 复制包；可用 `IMAGE_STUDIO_SITE_PACKAGES` 覆盖。生成的 `.app` 在 `build/package-build/payload`，安装包和环境检查脚本在 `dist/`。二进制和构建目录已被 .gitignore 排除。

## 4. 验证后再分发

```sh
codesign --verify --deep --strict "build/package-build/payload/影像工作台.app"
IMAGE_STUDIO_NO_BROWSER=1 CAMERA_DATA_DIR="$PWD/build/test-data" CAMERA_PORT=8771   "build/package-build/payload/影像工作台.app/Contents/MacOS/ImageStudio"
```

确认新数据目录没有密钥或登录账号，验证上传与截帧、重新启动和草稿保存；不要在测试中提交真实发布。若需正式发行，应使用自己的 Apple 开发者签名和公证流程。未经公证的版本由使用者按 [Apple 官方说明](https://support.apple.com/zh-cn/102445)自行确认是否允许打开。

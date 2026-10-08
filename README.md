# 影像工作台 · Image Studio

本机运行的多品牌视频发布工作台，支持小红书、视频号、抖音。上传视频和封面，生成或编辑文案，核对后发布；每个工作区分别保存账号、素材、草稿和发布记录，全部工作区共用一个 AI API Key。

![自定义品牌工作区](tutorial/01-workspace.png)

## 功能

- 自定义工作区名称、文字图标、内容方向和文案语气；点击左侧品牌图标切换、随时新增。
- 视频上传、自定义封面拖拽上传、视频截帧封面及可选 AI 封面。
- 最多抽取 12 帧分析，可选结合口播转写，生成三个平台的标题、正文和建议标签。
- 三个平台分别编辑文案，支持一键同步和撤销同步。
- 本机扫码登录、登录状态校验、串行发布、按平台查看结果。
- 立即发布或原生定时发布；当前按中国时间整点设置，限制为未来 2 小时至 7 天。
- 草稿自动保存、恢复，匹配的发布任务全部提交成功后清空草稿；失败或待确认时保留。
- 发布请求去重、重试保护、中断恢复。
- Safari 可打开工作台页面；自动登录和发布通过 Chrome 执行。

## 快速开始（Mac）

源码运行需要 Python **3.12**、Google Chrome、FFmpeg 和 FFprobe。安装 Python 后：

```sh
git clone https://github.com/flydoingnow-sketch/image-studio.git
cd image-studio
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launcher.py
```

也可双击 `install.command` 安装 Python 依赖，然后双击 `start.command`。程序打开 http://127.0.0.1:8769/ ，默认仅监听本机。

已有 Homebrew 时可通过 `brew install ffmpeg` 准备视频工具。也可以按 [构建说明](docs/BUILD.md) 构建内置 FFmpeg；不要把运行数据或个人密钥加入仓库。

**源码仓库不附带 Python/FFmpeg 二进制、Mac 安装包或视频教程。** 打包的 Mac 应用可内置 Python、FFmpeg 和 FFprobe，因此使用者无需另装视频处理工具。

## 第一次使用

1. 创建自己的工作区，填写名称、图标、内容方向和语气。
2. 在「品牌与 AI 设置」填写兼容的 HTTPS 服务地址、自己的 API Key 和支持图片输入的视觉模型 ID。密钥对全部工作区共用；留空保留现有值。
3. 分别连接小红书、视频号、抖音账号，在弹出的 Chrome 窗口自行完成扫码与验证。
4. 上传视频和封面，分析生成文案或手动填写，核对三个平台的标题、正文和标签。
5. 选择立即发布或定时发布，在「发布记录」查看各平台结果。

[图文步骤](docs/USAGE.md) · [图文手册](tutorial/guide.pdf) · [Mac 构建说明](docs/BUILD.md)

## AI 服务接口

使用兼容 OpenAI 格式的服务，按工作区配置服务地址和模型：

| 用途 | 接口 | 要求 |
| --- | --- | --- |
| 抽样画面分析与文案 | `POST /chat/completions` | 支持图片输入 |
| 口播转写（可选） | `POST /audio/transcriptions` | 支持 multipart 上传 M4A/AAC 音轨 |
| 封面生成（可选） | `POST /images/generations` | 支持 1024×1536，返回 `b64_json` |

启用 AI 时会将抽样画面、以及启用的音轨发送至使用者配置的服务。需要自己准备服务密钥与额度；这不是逐帧视频理解，生成结果应自行核对。图像与语音接口不兼容时可先留空。

## 数据和运行方式

- 默认目录：`~/Library/Application Support/ImageStudio`。
- `shared.db` 保存共用密钥和工作区索引，工作区分别保存数据库、素材、日志和登录状态。
- 密钥保存在本机，接口不会回传密钥。数据库不是加密保险箱；不要转发运行数据目录。
- 关闭网页不会停止后台服务；可双击 `distribution/停止工作台.command`。服务会拒绝在发布或其他操作执行中停止。
- 用 `CAMERA_DATA_DIR` 指定隔离数据目录，`CAMERA_PORT` 指定端口（默认 8769）。

```sh
CAMERA_DATA_DIR="$PWD/.local-data" CAMERA_PORT=8770 .venv/bin/python server.py
```

## 开发和验证

前端是原生 HTML/CSS/JavaScript，后端是 Python 标准库 HTTP 服务及 SQLite。

```sh
.venv/bin/python -m unittest discover -s tests -v
```

32 项测试覆盖空白首次启动、工作区与媒体隔离、共用密钥、草稿、发布去重、中断恢复、跨站请求拦截和停止保护。自动测试不调用真实 AI 服务、不登录真实账号、不提交发布。Mac 打包版已在 Apple 芯片本机验证，尚未在另一台实体 Mac 验收。

当前为本地单用户工具，每个工作区每个平台支持一个账号；默认数据目录适合单个服务进程使用。平台网页改版可能需要维护发布适配器。「已提交」不等于平台审核通过；结果不确定时先到平台确认，避免重复发布。请按平台规则填写必要的信息与声明。

## 致谢与许可

工作台采用 [MIT License](LICENSE)。发布适配器来自 [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload)，保留其 MIT 版权及许可，固定基础版本和本地修改见 [THIRD_PARTY.md](THIRD_PARTY.md)。这是独立项目，不隶属于任何相机品牌或发布平台。

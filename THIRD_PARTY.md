# 第三方代码

本项目使用 [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload)，MIT License，Copyright (c) 2023 dreammis。

固定版本：`0012d2c355f88f683cc38dde2a2db209e14091bc`。
完整原始许可证位于 `vendor/social-auto-upload/LICENSE`，保留其版权声明。

本地修改：
- 抖音与小红书 uploader 中指定 Chromium channel 的启动调用改为使用 `LOCAL_CHROME_PATH`。这让登录、校验和上传使用同一已安装的 Chrome，不需要额外下载浏览器。
- 添加本机 `conf.py`（Chrome 路径及运行开关）。
- 通过项目 requirements.txt 补充 Playwright 1.58.0：上游 CLI 导入的其他平台模块依赖它，但主线依赖清单没有列出。

工作台自己的 HTTP 服务、界面、视频分析、状态管理与测试位于 vendor 目录之外。升级上游时需保留这些修改并重新回归验证。

- 移除抖音与视频号 uploader 硬编码的 AI 内容默认声明；仅在调用方明确提供声明时设置，不覆盖平台自己的检测或标识。

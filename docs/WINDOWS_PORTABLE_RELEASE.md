# Windows 免环境发布

`scripts/build-windows-release.ps1` 生成可直接交付给普通 Windows 用户的 TrendScope 文件夹。使用者不需要安装 Python、uv、Node.js、npm 或 Playwright；所需 Chromium 会一起打包。

构建时会把项目的 `data/` 与 `reports/` 复制为首启初始数据。因此平台、采集、排序、Prompt、历史任务、内容、分析结果和报告都会随版本交付。构建脚本仅操作副本：会删除 `ai_provider_configs` 中的全部模型配置，并清空浏览器请求 Header，绝不会修改开发环境的 `data/app.db`。

## 构建者操作

构建机仍需具备 Node.js、npm 和 uv。首次构建需联网下载前端依赖、Python 依赖和 Chromium。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build-windows-release.ps1
```

生成目录为：

```text
release\TrendScope\
  TrendScope.exe
  README.txt
  _internal\
```

不要只复制 `TrendScope.exe`；请将整个 `release\TrendScope` 文件夹压缩后交付，或用 U 盘完整复制。

## 使用者操作

双击 `TrendScope.exe`。程序会在本机 `127.0.0.1` 启动服务并自动打开浏览器；它不会暴露到局域网或互联网。保留的小窗口可用于再次打开页面，关闭窗口会停止服务。

首次启动时，内置的初始数据会复制到用户目录。之后用户的数据、下载的公开媒体和报告保存于：

```text
%LOCALAPPDATA%\TrendScope\
  data\app.db
  data\tasks\
  reports\
```

因此升级程序时，直接以新版本替换 `release\TrendScope` 文件夹不会覆盖已有数据。备份或迁移时复制 `%LOCALAPPDATA%\TrendScope` 即可。首次运行若 Windows Defender SmartScreen 显示未知发布者提示，应由发布者使用代码签名证书签名后再正式分发；不要建议用户关闭系统安全防护。

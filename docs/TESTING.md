# 测试与边界

2026-11-15：v0.2.1 在本机 Windows / Python 3.13 下运行 50 项测试，全部通过，无跳过；Python wheel 构建与独立目录导入检查通过。

在 Windows 安装 Python 3.11+、FFmpeg（包含 ffprobe）和 Deno，再运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
New-Item -ItemType Directory -Force .tmp
.\.venv\Scripts\python -m unittest discover -s tests -v
```

测试使用临时数据库及本地 FFmpeg 生成的媒体。下载接口使用模拟响应，不访问个人账号或下载真实视频。截图中的作者、分组和作品均为模拟数据。

覆盖保存容器、画质上限、真实音视频轨道、内嵌封面字节校验、失败保留源文件、不覆盖交付、旧数据库升级、任务重试选项、三语界面、分组与搜索、大量作者及批量归属。版本更名额外检查旧数据路径沿用和新旧环境变量优先级。

自动测试不能代表 YouTube 当前可用性、长文件断网恢复、持续 24 小时检查或所有播放器的预览表现。封面写入且校验成功，也不保证 Windows 或 PotPlayer 的每种配置都会显示缩略图。

成功后工作文件仍保留；强制终止进程可能遗留不完整交付，需要人工核对。本版本尚无独立 Windows 安装包或自动升级功能。

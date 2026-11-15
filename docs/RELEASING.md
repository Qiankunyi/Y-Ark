# 版本发布

仓库：https://github.com/Qiankunyi/Y-Ark

1. 在 `creatorsave/branding.py`、`pyproject.toml` 和 `creatorsave/i18n.py` 更新同一版本号，补充 `CHANGELOG.md`。
2. 运行完整测试，检查界面与 `git diff`，确认没有个人设置、Cookie、日志、下载文件或真实关注截图。
3. 提交代码并推送 `main`。GitHub Actions 在 Windows 上运行自动测试。
4. 测试通过后为该提交创建 `vX.Y.Z` 标签和 GitHub Release。用 `git archive` 生成源码 ZIP，可用 `pip wheel --no-deps .` 生成 Python wheel；仅上传审查后的构建产物。
5. 发布说明列出变化、兼容方式和未验证的限制；安装包与源码包要明确区分。

本版本是源码发行，需要 Python 和外部媒体工具，并非独立 EXE。不会自动更新运行中的程序。

## 本机更新

关闭 Y-Ark 后拉取新版本，重新运行 `Setup-Y-Ark.cmd`，再打开 `Start-Y-Ark.cmd`。下载 ZIP 的用户应解压到新目录并运行安装入口，不要将 `.venv` 从旧目录复制过来。

设置、历史和分组保存在源码目录之外。存在 `%LOCALAPPDATA%\CreatorSave` 的旧安装会直接继续使用它；新安装使用 `%LOCALAPPDATA%\Y-Ark`。更新前可在程序完全退出后备份这个数据目录。

内部 `creatorsave` 模块、`CREATORSAVE_DATA` 环境变量及 `.creatorsave` 工作目录暂时保留兼容；新环境变量 `Y_ARK_DATA` 优先于旧变量。

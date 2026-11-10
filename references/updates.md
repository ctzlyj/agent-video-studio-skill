# 版本更新：检查、手动更新与一次性自动更新

## 先说结论

O2 当前**没有 per-skill 的原生自动更新开关**。Skill 是安装到 `~/.codex/skills/` 的静态文件；`oxygenskills check/update` 是命令行能力。运行中的 Codex 会话也不会热加载新的 `SKILL.md`。

所以本 skill 提供两层方案：

1. `self_update.py`：检查是否有新版本；可一键更新。
2. `install_auto_update.py`：**一次性安装每日自动更新任务**，之后用户不用每次手动敲更新命令。

自动更新只更新本 Skill 文件，不会安装灵境 CLI；AI 剧仍然要先跑 `ai_drama_preflight.py`。

## 方式一：检查 / 一键更新

```bash
python scripts/self_update.py            # 只检查
python scripts/self_update.py --apply    # 有新版本就更新
python scripts/self_update.py --json     # 给 Agent 解析
```

更新完成后**重启 Codex 或新开一个会话**，当前会话不会热加载新指令。更新会保留最近 2 个 `agent-video-studio.backup.*`，更旧的自动清理。

## 方式二：一次性安装每日自动更新（推荐给同事）

在安装好本 Skill 后，运行一次：

```bash
# 先预览会发生什么（不写计划任务）
python scripts/install_auto_update.py --time 07:30 --dry-run

# 确认后正式安装
python scripts/install_auto_update.py --time 07:30
```

- **Windows**：创建计划任务 `agent-video-studio-auto-update`，每天 07:30 运行；命令文件在 `%LOCALAPPDATA%\agent-video-studio\auto_update.cmd`，日志在 `%LOCALAPPDATA%\agent-video-studio\update.log`。
- **macOS**：创建 `~/Library/LaunchAgents/com.agent-video-studio-auto-update.plist`，用 launchd 每天运行。
- **Linux**：脚本不会自动写 crontab，只打印一行 cron 配置；需要用户自己加到 `crontab -e`。

卸载计划任务：

```bash
python scripts/install_auto_update.py --uninstall
```

## 注意

- 自动更新需要 O2 已登录、网络可用；失败会写日志，下一次任务继续重试。
- 自动更新不会在**当前**会话生效；建议把任务放在早上或下班后，第二天新开会话自然使用新版。
- 自动更新只更新 `agent-video-studio`，不会自动更新灵境 CLI、`lingjing` skill 或 `lingjing-director`；AI 剧前仍要跑 `python scripts/ai_drama_preflight.py`。
- 如果用户不想装计划任务，保留 `self_update.py --apply` 即可；Agent 也可以在每次开始前跑 `--check` 并提示用户。
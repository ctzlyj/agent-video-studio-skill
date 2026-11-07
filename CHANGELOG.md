# 更新记录

## 1.1.0 (2026-11-08)

### 新增
- **内置默认 BGM**《Vibe知识大赏》：代码动画类视频默认使用，按每镜 `mood` 抬压音量、对齐电平、淡入淡出、超长时交叉淡化循环；用户明确要换才降级为自带音乐 / 合成配乐 / 无音乐。
- **按剧情作曲的合成配乐**（`scripts/score.py`）：6 种风格（warm / bright / tech / cinematic / ambient / suspense），每镜 `mood` 或 `energy` 决定和弦换位、分层与鼓点；`score.py --list` 可单独试听。
- **交付终检**（`scripts/finalize.py`）：整片响度校准到目标 LUFS，检查真峰值、全片解码、时长、黑场；输出成片、无 BGM 版、`.srt` 和交付报告，不通过不发布。
- **文章 / 链接 / 口播稿接入指南**（`references/article-intake.md`）：全文抓取、版权提醒、文中指令不执行、事实对照、评论式脚本、竖屏要求。
- 新增音效 `pop` / `click` / `swell`；lint 新增 `mood`、`music`、字幕过长、单镜旁白过长检查；qa 新增配乐检查。
- 分镜表增加"情绪"列；新增 `references/music.md`。

### 变更
- `music` 省略时不再是旧的单调底乐，而是内置 BGM；旧写法 `{"generate": "ambient"|"pulse"|"none"}` 与 `{"file": ...}` 仍然可用。
- `audio.py` 额外输出 `audio/vo_sfx.wav`（无音乐的旁白加音效），`safe_name` 移到公共模块。

### 验证
- 28 项自动测试通过；竖屏 9:16 与横屏临时项目从零 `--preview` / `--final` / `finalize.py` 通过。
- 未验证：macOS 实机、真实网页的文章抓取流程、长于 2 分 40 秒的成片、人耳试听。

## 1.0.0 (2026-11-07)
首个公开版本：代码动画路线与灵境 AI 漫剧 / 真人短剧路线，Windows / macOS。
# 更新记录

## 1.2.0 (2026-11-08)

### 新增
- **能力清单** `references/capabilities.md`：一份开放的清单（不是规则），列出画面（HTML/SVG、Canvas 2D、p5.js、WebGL 着色器、Three.js 3D）、视频框架（HyperFrames、Remotion、Motion Canvas、Manim、Blender）、声音、素材、工具，标明哪些已随包、哪些自取、实测情况；由执行任务的 agent 自行判断用哪些。
- **Three.js 3D 图层**（`assets/fx/three-layer.js` + `vendor/three.module.min.js` r160，MIT）：与 2D 图层、着色器后期共用同一画布；实测 1080p 约 0.14–0.25 秒/帧，同一时间两次渲染像素一致；示例与回归测试。
- **炫技工具集** `assets/fx/`：WebGL 着色器后期（色差、辉光、拖尾、光扫、故障、震动、暗角、颗粒、冷暖调色、冷暖分界线、运动模糊）、画布工具、一镜到底世界与相机（单调三次样条）、粒子池变形、opentype.js 字形工具。
- 做法经验 `references/showcase.md`（画面事件对位旁白词、冷暖双音色、竖屏节奏、避免"带特效的 PPT"、软件渲染性能预算、3D 与 2D 的取舍）。
- 每镜独立音色（`voiceCfg`）；`transcribe.py --words` 词级时间戳；`check_env.py` 增加可选组件提示（node、rembg、librosa，不影响 READY）。

### 修复
- 交付终检：AAC 编码会让真峰值比编码前高约 1 dB，导致成片被误拒。现在编码前压低上限，测量编码后的成品，超限自动逐级重试。
- 渲染用的静态服务器改为多线程并忽略连接重置（原单线程会在浏览器并发请求脚本时卡死，报"找不到镜头"）。
- 竖屏预览不再算出奇数高度（原 960x1707 导致编码失败）。
- 更正一条未经实测的说法：3D 在软件渲染下并不慢。

### 验证
- 34 项自动测试通过（含 Three.js 图层确定性、相机样条不过冲、交付终检真峰值回归）。
- 用本版做出一支 83 秒横屏成片，经 `finalize.py` 校验（响度 -16.4 LUFS，真峰值 -2.3 dBTP，全片解码无错误）。
- 未验证：macOS 实机；HyperFrames / Manim / Blender / Motion Canvas / Revideo 的端到端成片（只确认可安装，Remotion 另出过一张静帧）；人耳试听。

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
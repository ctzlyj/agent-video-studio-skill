---
name: agent-video-studio
description: 用 AI Agent 从一句需求做出成片视频的通用工作室，Windows/macOS 都能用。代码动画路线（汇报片、产品宣传片、知识讲解、口播配画面、MG 动画、纪录片/发展史、从剧本开始）用 HTML 逐帧渲染（可叠 Canvas、WebGL 着色器后期、Three.js 3D）出带旁白、字幕、内置 BGM（按剧情起伏，仅代码动画）的 MP4，并做响度校准与交付终检；AI 漫剧、AI 真人短剧和需要实拍感的镜头，用灵境 CLI + Seedance 2.5 生成后合成，配乐按题材用合成预设（不用内置 BGM）。用户给文章/链接/口播稿要做成视频时也用。用户说"做个视频""做宣传片/汇报视频/发展史/讲解动画""把这段口播做成动画""做 AI 漫剧/短剧""这个视频改快一点/换风格/加署名"时使用。只剪辑现成素材、只生成单张图片时不用。
---

# Agent Video Studio

把"我想要一个视频"变成可交付的 MP4。用户只描述目标；你负责编剧、设计、出样、制作、自检，并在关键节点让用户拍板。

`$SKILL` = 本文件所在目录。项目目录放在用户工作区，**不要放进 `$SKILL`**。

## 硬规则（所有路线）

1. **先方案，后制作。**剧本/分镜和视觉方向各确认一次再大规模制作。用户说"直接做"时可跳过确认，但仍要把方案写进项目。
2. **风格不预设。**每个项目从题材、受众、品牌现场写自己的 `STYLE.md`；出 2–3 个真正不同的方向（不只是换配色）给用户挑。用户点名某个外部风格库时按 `references/external-skills.md` 现取。不要把上一个项目的风格当默认。
3. **生图统一走 `scripts/imagegen.py`**，模型链由配置决定（见 `references/image-providers.md`）。默认链的前两个是主模型；只有主模型都返回额度/限流/鉴权错误才降级到后备，交付说明里写明哪张图降级、用了什么模型。AI 剧路线的角色/场景图同样先用它出图再上传，不用视频平台自带的生图。
4. **所有素材进工程。**任何视频、图片、音乐都放进项目 `assets/` 并写进 `project.json`；禁止在成片上后期叠加（重渲染会丢）。路径一律相对。
5. **改版不覆盖。**改已交付的片子先 `new_project.py <dir> --version` 复制出新版本再改。
6. **花钱前报价。**灵境/Seedance 等付费生成，先报价、得到用户确认再提交；结果不明时先回查任务状态，不重复提交。
7. **说清验到了什么。**交付时给出 QA 结果和联系表；没有完整观看的就直说没看。
8. **AI 剧先定配乐。**AI 漫剧/真人短剧在剧本+分镜确认时同时给配乐方案（题材→预设→20–30 秒试听），用户确认后再批量生成。内置 BGM 只用于代码动画；AI 剧只有用户明确要求时才用 `music.allowBuiltinTrack: true`。

## 第一步：选路线

先问清（能从上下文推断的不问）：给谁看、想让对方得出什么结论、时长、横竖屏、有哪些真实素材（文档、截图、数据、照片、视频、录音）。然后选路线，**只读选中路线的文件**：

| 用户要什么 | 路线 | 读 |
|---|---|---|
| 汇报片、产品介绍、项目宣传、成果展示 | promo | `references/routes/promo.md` |
| 真实软件/网页产品的演示宣传片 | product-demo | `references/routes/product-demo.md` |
| 知识讲解、科普、教程、原理 | explainer | `references/routes/explainer.md` |
| 已有口播/录音，配画面 | voiceover | `references/routes/voiceover.md` |
| 短而精的 MG 动画、片头、品牌演绎、点名某种动效风格（扁平、线条、等轴、手绘沸腾、拼贴、液态、形变、包豪斯、复古、玻璃拟态、花字、像素、HUD 等） | motion-graphics | `references/routes/motion-graphics.md`，风格卡在 `references/mg-styles.md` |
| 发展史、纪录片、历史回顾、大事记 | documentary | `references/routes/documentary.md` |
| 用户只给想法，从剧本开始 | script-first | `references/routes/script-first.md` |
| 用户给的是文章 / 链接 / 报告 / 现成口播稿 | 先 `references/article-intake.md` 提炼脚本，再按内容选路线（常见：explainer / promo / script-first） | `references/article-intake.md` |
| AI 漫剧（动漫角色、连续剧情） | ai-comic-drama | `references/routes/ai-drama.md` + `references/music.md` |
| AI 真人短剧、实拍质感镜头 | ai-live-drama | `references/routes/ai-drama.md` + `references/music.md` |
| 代码动画里插几段 AI 生成镜头 | hybrid | 主路线 + `references/routes/ai-drama.md` 的"单镜生成" |

拿不准就选 promo 或 explainer，并告诉用户你的判断。

## 第二步：代码动画的通用制作流程

适用于除纯 AI 剧以外的所有路线（AI 剧的成片合成也复用第 6–8 步）。

1. **环境**：首次在一台机器上用时跑 `python "$SKILL/scripts/check_env.py" --install`。
2. **建项目**：`python "$SKILL/scripts/new_project.py" <项目目录> --title "片名" --format 16:9 --route <路线>`。
3. **事实与素材**：把用户材料里的事实、数字、名称提炼进 `FACTS.md`（每条注明出处）。旁白和画面里的数字只能来自这里。
4. **剧本 + 分镜**：写进 `project.json` 的 `scenes`（每镜：`id`、`type`、`vo` 旁白、`data` 画面内容、可选 `speed`/`pad`/`sfx`）。同时给用户一份可读的分镜表，等确认。规则见 `references/storytelling.md`。
5. **视觉方向**：按 `references/style-design.md` 写 2–3 个方向，各渲 1–3 张关键帧（`render.py --stills`），用户选定后写成 `STYLE.md`，再按它写 `style.css` 和 `scenes.js`。
6. **小样**：`python "$SKILL/scripts/build.py" <项目> --sheet` 看每镜静帧联系表，再 `--preview` 出低清小样给用户看，按意见改（大白话意见怎么落地见 `references/revisions.md`）。
7. **成片**：`python "$SKILL/scripts/build.py" <项目> --final`，自动跑 lint、配音、时间线、混音、渲染、QA。
8. **交付**：`python "$SKILL/scripts/finalize.py" <项目>` 把响度校准到 -16 LUFS、全片解码检查，输出 `deliver/` 下的成片、无 BGM 版、`.srt` 字幕和交付报告（任一检查不过就不发布）。回复里写：成片路径、时长、QA 与终检结果、联系表 `qa/final_sheet.jpg`、用到的生图模型及是否降级、没验到的点。

配乐：**代码动画**默认用内置 BGM，不用配置；给每镜标 `mood` 让音量跟剧情起伏。**AI 漫剧/真人短剧不用内置 BGM**：新建项目时 `music` 是 `{"style": "auto"}`，按题材走 `workplace` / `healing` / `comedy` / `hotblood` / `suspense` / `cinematic` 等合成预设；剧本确认时先出 20–30 秒试听。**用户明确要换 BGM 才改用 `music.file` / 其他 `music.style`**。规则见 `references/music.md`。

要某种成熟动效风格、纸感/颗粒/胶带质感、运动模糊、独立评审时读 `references/mg-styles.md`。

可用的技术与素材全部列在 `references/capabilities.md`（画面、3D、着色器、框架、声音、素材、工具，标明哪些已随包、哪些自取、实测情况）；做法经验见 `references/showcase.md`。用哪些、怎么组合，由你根据任务自行判断。

读音：中文多音字（还款、长度、重复、银行、重庆等）的实测替换表、`voice.pronounce` 用法和 `voice.py --check [--asr]` 的局限见 `references/voice.md`。

写 `scenes.js` 前读 `references/engine.md`（运行时 API、确定性规则、视频素材、倍速）。踩坑与排查见 `references/pitfalls.md`。

## 脚本速查

| 脚本 | 作用 |
|---|---|
| `check_env.py [--install]` | 检查/安装 Python 依赖、Chromium、ffmpeg，探测网关 key 和灵境 CLI。区分"没装"和"装了但被沙箱拦"，后者不用重装 |
| `new_project.py <dir> [--version] [--textures]` | 新建项目 / 复制出新版本；`--textures` 拷入纸张、颗粒、尘点、和纸胶带纹理包 |
| `imagegen.py "提示词" -o a.png [--size] [--ref]` | 按配置的模型链生图（主模型优先，仅额度类错误降级） |
| `voice.py` | 逐镜配音（edge / say / sapi / 自带录音），文本不变不重配；`--check [--asr]` 做多音字/读音校对 |
| `prep_video.py` | 视频素材拆帧，供画布逐帧确定性播放 |
| `timeline.py` | 按旁白时长和每镜倍速生成时间线与字幕 |
| `audio.py` | 配乐、音效、旁白混音（倍速旁白变速不变调）；代码动画默认内置 BGM，AI 剧默认合成题材配乐；都按每镜 `mood` 起伏 |
| `bgm.py` / `score.py --list / --style X -o a.wav` | 内置 BGM 引擎（仅代码动画）/ 合成配乐引擎（含 AI 剧题材预设） |
| `render.py --stills/--sheet/--preview/--final [--mb N --shutter S --workers N]` | 无头浏览器逐帧渲染；`--mb` 子帧运动模糊，`--workers` 多浏览器并行；输出按 BT.709 编码并打标 |
| `review_pack.py [--moves 3.2,7.5]` | 成片后生成独立评审用的证据包（联系表、快动作条带、全分辨率帧、实测规格）到 `qa/review/` |
| `transcribe.py <音视频>` | 本地语音转写带时间戳（faster-whisper），给生成视频对白配字幕、对齐口播稿 |
| `finalize.py [--lufs -16]` | 交付终检：响度校准到目标、真峰值、全片解码、黑场；输出成片 / 无 BGM 版 / SRT / 报告到 `deliver/`，不通过不发布 |
| `lint.py` / `qa.py` | 出片前检查（品牌用词、禁用词、路径、缺素材、字幕重复）/ 出片后检查（时长、音量、黑帧、冻帧、联系表） |
| `build.py --sheet/--preview/--final` | 一键串起以上步骤 |

# 更新记录

## 1.6.0 (2026-11-10)

增加可选的自动更新能力，解决“每次都要手动更新”的问题。

### 新增
- `scripts/self_update.py`：通过 O2 `oxygenskills check/update` 检查是否有新版；`--apply` 一键更新；更新后提示重启 Codex/新开会话。保留最近 2 个 `agent-video-studio.backup.*`。
- `scripts/install_auto_update.py`：一次性安装每日自动更新任务（Windows 计划任务、macOS launchd；Linux 打印 cron 配置）。`--dry-run` 只预览，`--uninstall` 移除任务；日志写入本机用户目录。
- `references/updates.md`：说明 O2 没有原生 per-skill 自动更新、当前会话不会热加载、自动更新需要 O2 登录/网络，以及自动更新**不会**安装灵境 CLI（AI 剧仍要跑 `ai_drama_preflight.py`）。
- `SKILL.md` 脚本速查加入更新脚本和版本更新说明。

### 验证
- 自动测试 65 项：新增 `self_update` 版本解析、`local_version`、自动更新安装器 `--dry-run`。
- 本机 `python scripts/self_update.py --json` 当前显示已是最新（1.5.2；发布本版后为 1.6.0）。
- 未注册本机计划任务（只做 dry-run）；未提交付费任务。
## 1.5.2 (2026-11-10)

修复“同事机器上 Agent 不调用灵境 CLI、改用浏览器自动化点画布”的问题。

### 根因与修复
- `agent-video-studio` 不随包携带灵境 CLI/`lingjing` skill，旧版 `check_env.py` 又把 CLI 标成 optional；只装 `agent-video-studio` 的机器没有 CLI 契约，Agent 就退回浏览器。
- 新增 `scripts/ai_drama_preflight.py`：AI 剧开始前硬检查 `lingjing` CLI、`lingjing` skill、`lingjing-director` skill 和 `lingjing doctor`；缺任何一项直接非 0 退出，并打印灵境一体包安装入口、`LINGJING_SKILL_DIR` 设置方法和重启/新会话要求。
- `SKILL.md` 新增硬规则 8、`ai-drama.md` 新增“第一次用之前”第 0 步和“为什么不能用浏览器代点灵境画布”：浏览器只用于用户登录/视觉验收，不用于生成、扣费或画布写入。
- `check_env.py` 把 lingjing 行改为“AI drama required”，不再暗示 optional；`pitfalls.md` 增加对应排错行。

### 验证
- 自动测试 62 项（新增：预检发现 CLI/skill、缺依赖时退出码 2 且打印安装说明和禁止浏览器代点）。
- 当前机器运行 `python scripts/ai_drama_preflight.py`：CLI、`lingjing`、`lingjing-director`、`lingjing doctor` 全过（identityVerified=true、bridge=online），READY (AI drama)。
- 未提交付费生成任务；未改内置 BGM 文件和授权。
## 1.5.1 (2026-11-10)

补 1 次真实 MiniMax Music 验证记录（用户授权，仅 1 首）：

- taskId `18789322`，成功提示词原样提交，输出 mp3 25.24 秒、BPM 123、频谱重心 2105 Hz、bright，但调式粗筛为 **B minor**，`music_screen.py --expect-mode major` 未通过；因此未采用，也没有继续提交第二首。
- 结论写进 `references/music.md`：同一提示词不保证调式/时长，必须粗筛 + 用户试听；`music.file` 短于成片时会循环并淡出。
- 系统仍 `quote:null`；完成后约 5 分钟 `lingjing usage show 18789322` 无明细，实际扣费未确认，历史实测约 0.45 元/首，以账单为准。
- 代码无改动；1.5.0 的 60 项测试结果仍然有效。
## 1.5.0 (2026-11-10)

把 AI 剧配乐从“代码合成默认”改成“MiniMax Music 生成 + 客观粗筛 + 用户试听确认”，并补配音、旁白节奏、summary/片尾模板和返工流程。

### 配乐
- **AI 剧新建项目不再写任何默认配乐**：`new_project.py` 对 `ai-comic-drama` / `ai-live-drama` 写 `music: {}`，`audio.py` 在未选定 `music.file` 时直接拒绝出片；`lint.py` 报“AI 剧尚未选定配乐”。
- **内置 BGM 只用于代码动画**：AI 剧写 `track=default` 会被 `bgm.resolve()` 拒绝；只有用户明确要求并写 `music.allowBuiltinTrack=true` 才放行。
- **AI 剧主配乐改走灵境 MiniMax Music 2.6**：`references/music.md` 增加 8 个题材提示词模板（成功案例原样收录）、报价说明（系统 quote:null，实测约 0.45 元/首）、`lingjing model exec` 命令、`scripts/music_screen.py` 客观粗筛（Krumhansl 调式、BPM、频谱重心）和用户试听确认流程。
- **代码合成保留但降级**：`score.py` 的 10 种风格只作氛围衬底，没有真正旋律；AI 剧 `music.style` 会被 lint 提示“不要作为主配乐”。
- **混音默认**：AI 剧 `music.file` 默认 `volume: 0.10`；旁白 + `clipAudio` 一起进闪避侧链，AI 剧闪避 8:1；`audio.py` 写 `mix_report.json` 记录音乐来源/音量/闪避参数。

### 配音与读音
- AI 剧教学/培训默认 `zh-CN-XiaoxiaoNeural` +12%；`XiaoyiNeural` 用于更活泼的场景。edge 合成重试从 3 次增到 5 次（指数退避）。
- `voice.py --check --asr` 先把繁体转简体（如“重復”→“重复”）再做拼音对比；新增“还有”等常见多音字提示；补充 Xiaoxiao/Xiaoyi 声线与语速说明。
- `references/voice.md` 保留实测表：`还款→环款` 三音色稳定；`长度→常度` Yunxi/Yunyang 有效、Xiaoxiao 有歧义；`重复` 本次测试未复现 zhòng。ASR 通过不代表声调/语气正确。

### 旁白、summary 与返工
- `ai-drama.md` 更新女声 +10~12% 的字数表：10 秒 45–52 字、13 秒 60–68 字、15 秒 70–78 字；`timeline.py` 输出每镜 `charsPerSec`，旁白超出 `dur` 时打印 `WARN ... tail will be cut`。
- 模板 `assets/template/scenes.js` 新增 `summary`（渐变呼吸、进度条、要点错峰）、`endcard`（渐变漂移/呼吸光）和 `clip`（正放→倒放 `pingPong` 补画面）；`qa.py` 注明冻结阈值 6 秒。
- `ai-drama.md` 增加参考图 `{{Ref N}}` 顺序、品牌/制服参考图约束、只重做音频不重跑视频素材的标准路径、交付“没验到的点”模板；`finalize.py` 的拒绝覆盖报错补“只改配乐/配音、不需要重新生成 AI 视频”的常见场景。

### 验证
- 自动测试 60 项（新增：AI 剧空/内置曲目拒绝、允许内置、music.file 混音报告、summary 微动效、music_screen 输出、繁简归一/读音）。
- Mock `audio.py`：AI 剧空 music 和 track=default 均非 0 退出；`allowBuiltinTrack=true` 才走 track；`music.file` 生成 `mix_report`（volume 0.10、duck 8）。
- 真实只读验证：`ep1_proj/assets/bgm.mp3` 粗筛为 D major / 123 BPM / 1907 Hz / bright；`ep1_proj` 的 c1 配音 `voice.py --check --asr` 转写与拼音一致。
- 灵境只做了 `model list/show/quote` 只读调用；没有提交付费 Seedance 或 MiniMax 生成任务。未做 Mac 实机和真实人耳试听。
## 1.4.0 (2026-11-10)

修正 AI 漫剧/真人短剧的配乐路线与几个实战问题。代码动画路线的默认行为不变：内置 BGM 仍只服务 promo/explainer 等代码渲染。

### 配乐
- **根因修复**：`new_project.py` 不再把模板里的 `"music": {"track": "default"}` 带进 AI 剧项目。`ai-comic-drama` / `ai-live-drama` 新建时写 `{"style": "auto"}`；promo/explainer/motion-graphics/hybrid 等仍写 `{"track": "default"}`；新增 `--music-style` 可显式指定题材预设。
- **防回归**：`bgm.resolve()` 对 AI 剧的 `track=default` 自动改走合成配乐，并在 `audio.py` 打警告；只有 `music.allowBuiltinTrack: true`（用户明确要求）才保留内置 BGM。`lint.py` 增加 `drama_bgm` 警告。
- **新增 4 个 AI 剧题材预设**：`workplace`（轻松职场/教学，96 bpm C 大调）、`healing`（治愈日常/真人情感，78 bpm F 大调）、`comedy`（搞笑喜剧，112 bpm G 大调）、`hotblood`（热血/成长，124 bpm D 小调）。`ai-comic-drama` 的 auto 默认 `workplace`，`ai-live-drama` 默认 `healing`，不再默认 `cinematic`。
- **混音**：AI 剧音乐床默认压到 0.50、闪避比 8:1（代码动画保持 0.62 / 6:1），旁白和 `clipAudio` 都进闪避侧链；片尾用 `resolve` + 2.5 秒淡出。
- **文档**：`music.md` 重写优先级表和题材选择表，补“剧本/分镜确认时给 20–30 秒试听”的流程、替代方案（授权 `music.file` / 授权 AI 作曲，付费前报价）；`SKILL.md` 和 `ai-drama.md` 同步修正“AI 剧默认内置 BGM / cinematic”的矛盾说法。

### 读音
- `voice.py --check`：扫描 vo 里的常见多音字，给出替换建议；`--asr` 用 faster-whisper 转写已有音频，再用 pypinyin 做拼音级对比；`--strict` 有可疑项时返回非 0。
- 新增 `references/voice.md`：`voice.pronounce` 持久化用法、实测替换表、ASR 方法和局限。2026-11-10 实测：`还款→环款` 在 Yunxi/Yunyang/Xiaoxiao 三个音色都稳定读 huán；`长度→常度` 在 Yunxi/Yunyang 有效，Xiaoxiao 转写有歧义；`重复` 在这几个音色的测试里已读 chóng，未复现 zhòng。字幕继续用原文。

### AI 剧实战文档
- `ai-drama.md` 更新费用口径：**2026-11-10 实测 mode=720p 但成片 1920×1080，13 秒实扣 48.8 元、10 秒 37.6 元，约为报价 3.5 倍；预估 450 元、实际约 856 元。** 报价必须按约 3.5 倍提示，并核对实际输出分辨率。
- 每段 prompt 固定加“本段只出现 A、B，不得出现其他角色”；质检清单增加“多余角色/缺角色”。
- 屏幕、牌子、包装只画图标/色块，不写字；需要文字用 HTML 叠加。
- 补旁白字数表：10 秒 33–38 字、13 秒 45–50 字、15 秒 ≤50 字；先写旁白再定 duration。
- `finalize.py` 拒绝覆盖 `deliver/` 时，报错现在给出三条具体做法（`new_project.py --version`、把旧 deliver 移到 `deliver_<时间戳>/`、只删指定旧文件）。

### 验证
- 自动测试从 50 项增到 57 项，全部通过（新增：新建项目按路线写 music、AI 剧强制走合成配乐、lint 警告、题材预设、读音提示与 `--check` CLI）。
- 本地 mock 项目跑 `audio.py`：AI 剧即使写 `track=default`，也会警告并生成 `workplace` 配乐；代码动画仍走内置 BGM。
- 生成 20 秒试听：`workplace` / `healing` / `comedy` / `hotblood`，并用 `cinematic` 对照（路径见交付说明）。
- 读音：edge-tts + faster-whisper small + pypinyin 实测 3 个音色、原词/替换词对照；结论见 `references/voice.md`。
- 未做：真实付费灵境任务（按要求不跑）；Mac 实机；人耳试听（试听文件已生成，需用户确认）。
## 1.3.0 (2026-11-09)

融合开源仓库 mg-styles-15（Vincentwei1021，MIT）：把它 15 种动效风格里"可复用的做法和素材"并进本 skill，没有并入它的 420 MB 成片、展示站、字体、Blender 片和 mgaudio 配乐库（理由见 `references/mg-styles.md` 第六节）。

### 新增
- **`references/mg-styles.md`**：15 张风格卡（认出它靠什么 / 怎么做 / 在本引擎里怎么落地 / 配乐可选），纹理包用法，运动模糊与"一拍二"，颜色说明，独立评审的做法与可直接使用的评委提示词。
- **质感纹理包** `assets/textures/`（约 5.6 MB）+ `assets/fx/texture.js`：纸张底纹、可无缝平铺的细颗粒/35mm 胶片颗粒、尘点划痕、和纸胶带；颗粒与尘点按拍点换位（"boil" 的底），同一时间逐像素一致。`new_project.py --textures` 拷入项目；来源与授权在 `assets/textures/CREDITS.md`，附来源仓库 MIT 许可全文。
- **运动模糊** `render.py --mb N --shutter S`：每帧渲 N 个子时刻取平均。实测对线性和缓动位移都有拖影，对量化的阶梯运动没有（所以文档写明不同时用）。可写进 `project.json` 的 `render` 块。
- **并行渲染** `render.py --workers N`：N 个浏览器分段并行。实测 1080p、400 个带阴影/模糊元素、180 帧：36 秒 → 26 秒（1.4 倍）；简单画面反而更慢，文档如实写明。
- **`AVS.hold(t, rate)`**：时间量化，做"一拍二"、定格、像素风阶梯。
- **`scripts/review_pack.py`**：成片后生成独立评审证据包（0.5 秒联系表、快动作条带、全分辨率关键帧、实测规格）。
- `lint.py` 检查 `render` 配置的取值范围。

### 修复
- **品牌色在播放器里偏色**：旧版编码没做 BT.709 矩阵转换也没打标，播放器按 601 猜。实测薄荷绿 `#2EE6A8` 偏 23/255、红偏 13/255；现在按 709 转换并打标，按 709 播放器解码后误差 ≤ 6，有回归测试。已交付的旧片需要重渲才会改善。

### 验证
- 自动测试从 37 项增到 50 项，全部通过（新增：采样时间、分段覆盖、帧数精确且无残留临时文件、颜色回归、render 配置 lint、纹理拷贝与授权文件、纹理确定性、评审包）。
- 实测数据：运动模糊灰边像素 0 → 1812（匀速方块）；三个独立浏览器渲同一时刻逐字节一致；单浏览器两次渲染逐字节一致；多浏览器与单浏览器平均像素差 0.1–0.9/255。

### 没验到
- 15 张风格卡没有逐一做成片，只对运动模糊、并行、一拍二、纹理叠加、BT.709 做了实测；其余来自对来源源码的阅读。
- 没有在 Mac 上跑；`--workers` 没在 Mac 上测过。
- 纹理里的"和纸胶带""颗粒""尘点"的授权按来源仓库的声明写入（部分为其自带的 MIT 内容，纸张为 ambientCG CC0），我没有独立核实更上游的出处；对外商用前请自行确认。
## 1.2.1 (2026-11-08)

来自一次真实的 macOS 实测（agent 安装本 skill 后，用代码、AI 漫剧、AI 真人短剧三种模式各做一支教程视频，三支均成片、QA 全过）。实测暴露的问题：

### 修复
- **`check_env.py` 把"装了但被沙箱拦着不让启动"误报成"没装"**：实测里连续 5 次报 `chromium MISSING`，agent 反复重装、排查了 4 轮，而同一段启动代码有时成功、有时失败。现在区分三种情况：能启动 / 装了但被沙箱拦（提示不要重装）/ 没装（才安装）。
- **`render.py` 在不允许绑定本地端口的沙箱里崩溃**（`PermissionError: [Errno 1] Operation not permitted`）：绑定失败时自动改用 `file://` 渲染（素材都是相对路径，结果相同），并打印一行说明；浏览器启动失败时给出可操作的提示，而不是一段栈。

### 文档
- `routes/ai-drama.md` 开头新增「第一次用之前」：灵境登录（无头环境用 `lingjing login --no-open`，把授权链接发给用户）、签《Seedance2.0 模型使用承诺书》（实测第一次付费提交才报 `[539]`）、看余额、自检。
- 新增「旁白字数」：用 edge-tts 实测中文约 3.9 字/秒，15 秒的段旁白 ≤ 50 字（实测一段旁白读出 19.8 秒、视频只有 15.04 秒，改稿重配）。
- `pitfalls.md` 增加：chromium 误报、端口绑定被拒、shell 里直接敲 `ffmpeg` 找不到（用 `imageio_ffmpeg` 或 `lingjing clip which-ffmpeg`）、承诺书、旁白超长。

### 验证
- 37 项自动测试通过（新增沙箱场景回归测试：模拟端口绑定被拒、浏览器被拦、没装）。
- 在"绑定被拒"的模拟环境下端到端渲染出静帧；正常路径出片与 QA 全过。
- 未验证：在真实 macOS 沙箱里重跑（我没有 Mac，只在 Windows 上模拟了同样的异常）；实测里的成片画面质量（记录只有路径与 QA 结果）。

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
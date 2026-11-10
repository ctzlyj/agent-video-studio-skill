# 能力清单：这个 skill 能用的技术与素材

这是一份**能力清单，不是规则**。你（执行任务的 agent）根据用户要的片子、素材和机器环境，自己判断用哪些、不用哪些、怎么组合。想用清单以外的做法也完全可以。下面只说明：每项能做什么、在哪里、是否已随包带好、实测情况。

标记：**随包** = 已放在 skill 里，拷进项目就能用；**自取** = 一条命令装；**重** = 配置多、耗时长，需要时再评估，默认不碰。

## 一、画面：在浏览器里画

| 能力 | 状态 | 能做什么 | 在哪里 / 怎么拿 |
|---|---|---|---|
| ① HTML / CSS / SVG | 随包（引擎默认） | 界面、排版、图章、矢量图形；文字在任何缩放下都清晰 | `assets/template/`、`references/engine.md` |
| ② Canvas 2D | 随包 | 逐帧手绘：线条、粒子、图表、笔触、白板、像素风 | `assets/fx/lib.js`（画布工具：图、辉光、文字、线、粒子） |
| ③ p5.js | 自取 | 生成艺术、噪声、笔刷（p5.brush）；用 `noLoop()` + 固定种子即可确定性输出 | `npm i p5`，取 `lib/p5.min.js` 放进项目；LGPL，**没有随包** |
| ④ WebGL 着色器后期 | 随包 | 色差、辉光、横向光斑、光扫转场、故障切片、屏幕震动、暗角、颗粒、冷暖调色、冷暖分界线、运动模糊 | `assets/fx/fx.js`，参数见文件顶部注释；软件渲染下 1080p 约 0.5 秒/帧 |
| ⑤ Three.js（3D） | 随包 | 写实质感：物理材质、灯光、阴影、雾、景深感、相机穿行 | `assets/fx/three-layer.js` + `vendor/three.module.min.js`（r160，MIT）；与 2D、着色器后期共用同一画布；1080p 约 0.14–0.25 秒/帧，**同一时间两次渲染像素一致（已测）**；示例 `assets/fx/examples/` |
| 一镜到底的相机 | 随包 | 一个世界 + 一条相机路径（单调三次样条，无过冲）、视差分层、天际线、地面、小物件库、粒子池变形 | `assets/fx/world.js`（有回归测试） |
| 字形剪切 / 手剪边缘 | 随包 | 把字形轮廓取出来再加工（剪纸、片头字） | `vendor/opentype.min.js`（MIT） |
| 质感纹理 | 随包 | 纸张底纹、可无缝平铺的细颗粒/胶片颗粒、尘点划痕、和纸胶带；颗粒按拍点换位（"boil"），同一时间逐像素一致 | `assets/textures/` + `assets/fx/texture.js`，`new_project.py --textures`；来源与授权见 `assets/textures/CREDITS.md`，用法见 `references/mg-styles.md` |
| 运动模糊 / 一拍二 | 随包 | `render.py --mb N --shutter S` 子帧平均；`AVS.hold(t, 12)` 时间量化 | `references/mg-styles.md` 第三节 |
| 动画库 GSAP | 自取 | 时间线、缓动、序列；用 `paused` 时间线 + `seek(t)` 即可确定性 | `npm i gsap`；许可为"免费但有条件"，**没有随包** |

## 二、视频框架与引擎

| 能力 | 状态 | 说明 |
|---|---|---|
| 本 skill 自带引擎 | 随包 | 页面是时间的纯函数，逐帧截图，ffmpeg 合成；每镜可调速；旁白对齐字幕。其他框架能做的，用上面的画面技术大多也能做 |
| ⑥ HyperFrames（HeyGen，Apache-2.0） | 自取 / 重 | 用 HTML 写视频、按时间线控制；团队已在用或需要它的组件库时再考虑。`references/external-skills.md` |
| ⑦ Remotion（React） | 自取 / 重 | 视频即 React 组件，按帧控制，适合几分钟长片和系列化。**实测：装好后能在约 45 秒内出静帧，但要装依赖并自行下载浏览器，所以没有随包** |
| Motion Canvas / Revideo | 自取 / 重 | 用 TypeScript 写动画的框架，需 Node 环境 |
| ⑧ Manim | 自取 / 重 | 数理推导动画，公式用 LaTeX 排版；需要 Python + LaTeX |
| ⑩ Blender（可借 blender-mcp） | 自取 / 重 | 真三维动画，门槛和成本最高；需要安装 Blender、通常要独显 |

## 三、声音

| 能力 | 状态 | 说明 |
|---|---|---|
| 中文配音 | 随包（脚本） | edge-tts（联网，免费）；离线兜底 macOS `say` / Windows SAPI；`voice.py`，每镜可单独指定音色、语速、音高 |
| 英文配音 | 自取 | Kokoro（`pip install kokoro`）等 |
| 语音转写与词级时间戳 | 随包（脚本） | `scripts/transcribe.py [--words]`（faster-whisper）：校对旁白、给生成视频的对白配字幕、把画面事件钉在旁白说出关键词的瞬间 |
| 内置 BGM | 随包 | `assets/music/vibe-knowledge.mp3`，按每镜 `mood` 起伏，见 `references/music.md` |
| 代码合成配乐 | 随包 | 10 种风格（含 AI 剧题材预设），按分镜换和弦、加减鼓点，`scripts/score.py` |
| 音效 | 随包 | 代码合成：tick / ok / alert / whoosh / boom / pop / click / swell |
| 音频分析（节拍、响度） | 自取 | `pip install librosa`（实测可装可用）；响度与真峰值检查已在 `scripts/finalize.py` 里 |
| 独立评审证据包 | 随包（脚本） | 联系表、快动作条带、全分辨率帧、实测规格，交给另一个会话评审 | `scripts/review_pack.py`，评审提示词见 `references/mg-styles.md` |
| 混音与终检 | 随包 | 旁白闪避、整片响度校准、真峰值（含 AAC 编码后实测并自动重试）、无 BGM 版、SRT |

## 四、素材：代码画不好的部分

| 能力 | 状态 | 说明 |
|---|---|---|
| ⑱ 生图（公司网关 GPT-Image-2.5） | 随包（脚本） | `scripts/imagegen.py`：主模型 `GPT-Image-2.5-Flare-joybuilder` → `Sunburst`；只有额度/限流/鉴权错误才降级。适合做"证据素材"（实物特写），也可以做任何你认为需要的图 |
| 抠图 | 自取 | `pip install rembg`：把生成的实物抠成透明底，作为实物浮在动画里（实测可用） |
| ⑰ 视频模型（Seedance 等） | 随包（流程） | 灵境 CLI：AI 漫剧、真人短剧、实拍感镜头；**花钱前先报价、用户确认**。`references/routes/ai-drama.md` |
| 外部风格库、示例片 | 自取 | `references/external-skills.md`（lemo-opuscar 51 种风格、anatomy、creator-style-kit 等；注意各自许可） |

## 五、工具

Python、ffmpeg（自动查找，找不到会用 imageio-ffmpeg）、Node.js、Playwright + Chromium、git：`scripts/check_env.py --install` 会检查并尽量装好；缺什么它会告诉你。

## 六、几条经验（供参考，不是约束）

这些来自真实做片时踩过的坑，你可以照做、改做、或不理：
- 每镜只换一张整屏底图再叠字，容易像 PPT；把摄影图抠成实物浮在动画里，或让相机在一个连续的世界里走，会更像视频。
- 画面事件钉在旁白说出关键词的瞬间（词级时间戳），比凭感觉写时间准得多。
- 文字想要锐利，可以画在着色器之后的叠层上；想要和画面融为一体的辉光，就画在着色器之前。
- 着色器的采样数就是渲染时间；运动模糊只对基础颜色做一次。
- AAC 编码会让真峰值比编码前高约 1 dB，交付检查要测编码后的成品。
- 同一项目同一时间只开一个渲染，否则会互相覆盖临时文件。
- 软件渲染下，3D（Three.js）并不慢，别因为印象而放弃它。
- 并行渲染（`--workers`）在简单画面上反而更慢，着色器/3D 这类慢画面才有收益（实测 1.4 倍，见 `mg-styles.md`）。

## 七、没验到的

- ⑥⑦⑧⑩ 和 Motion Canvas / Revideo：没有在本 skill 里端到端跑过成片，只确认了能安装（Remotion 另外出过一张静帧）。
- Mac 实机。
- 人耳试听。
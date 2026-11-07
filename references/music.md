# 配乐：默认用内置 BGM，剧情决定起伏

## 选择顺序（谁优先）

| 优先级 | 用户/工程里写了 | 用什么 |
|---|---|---|
| 1 | `music.file` | 用户自带的音乐（须有授权） |
| 2 | `music.style` | 代码合成的"按剧情作曲"（下文） |
| 3 | `music.generate` (`none`/`ambient`/`pulse`) | 无背景乐 / 旧的单调底乐 |
| 4 | `music.track` 或什么都不写 | **内置 BGM「Vibe知识大赏」**（默认） |

- **代码动画类视频默认就用内置 BGM**，不用问用户、不用配置。纯 AI 漫剧/真人短剧（`ai-comic-drama`、`ai-live-drama`）因为本身是电影感叙事，默认走 `cinematic` 合成配乐；混合路线（`hybrid`）按代码动画处理。
- **用户明确要换 BGM 才降级**：要换成自己的歌 → `music.file`；要别的风格 → `music.style`；不要音乐 → `music.generate: "none"`。不要在用户没提时替他换掉内置 BGM。
- 用户只说"换一首/不喜欢这个音乐"没说要什么：先问"用你自己的歌，还是我用代码合成一首（温暖/明亮/科技/电影感/氛围/悬疑可选）"，听完试听再定。

## 内置 BGM

- 文件 `assets/music/vibe-knowledge.mp3`（《Vibe知识大赏》，约 2 分 40 秒，约 112 拍/分，128 kbps，约 2.5 MB）。适合知识、汇报、产品、回顾等多种风格的衬底。
- 引擎 `scripts/bgm.py` 做的处理（原曲不改）：音量对齐到衬底电平；抹平曲子自身 70% 的忽大忽小；**按每镜 `mood` 抬压音量**（climax 比 calm 响约 5 dB，`silent` 镜头让出）；开头淡入 1.2 秒、结尾淡出 2.5 秒；视频比曲子长时**交叉淡化循环**；旁白出现时自动压低（闪避）。
- 可选：`"music": {"track": "default", "gain": 0.8}`，`gain` 整体增减（0–1.5）。
- 原曲没有"从头起承转合"的结构变化，只靠音量起伏体现剧情；**这是它与下面合成配乐的区别**——合成配乐会换和弦、加减鼓点。
- 局限：太短的视频（<20 秒）只会用到曲子开头；不能随画面事件卡点。要强卡点（MG 片头）用 `music.style: "bright"` 并设 `bpm`。

## 版权与来源

《Vibe知识大赏》（作者署名"霓虹兔"）由团队提供，**已确认可以随本 Skill 一起分发**（GitHub 仓库和 O2 SkillHub）。

这只是"分发"的许可。**用它做出的成片对外公开发布、投放广告或商用，授权范围我们没有逐条核实**：内部汇报、内部分享、工作演示没有问题；对外发布前请先让用户自己确认，不确定就改用 `music.style` 合成配乐或有授权的 `music.file`。交付外部成片时要在回复里提醒一次。

---

# 代码合成配乐：按剧情作曲（`music.style`）

用户要换 BGM 时的第二选择。不是固定底乐，而是**按分镜"作曲"**：你给每镜标情绪，音乐随之起伏。全部用代码合成（numpy），不需要音乐库、不联网、不花钱，同一个 `seed` 每次结果一样。

## 怎么用

`project.json`：

```json
"music": {"style": "auto", "bpm": 90, "key": "D minor", "seed": 7},
"scenes": [
  {"id": "s01", "mood": "calm",   "...": "..."},
  {"id": "s02", "mood": "build",  "...": "..."},
  {"id": "s03", "mood": "climax", "...": "..."},
  {"id": "s04", "mood": "resolve","...": "..."}
]
```

- `style`：`auto`（按 `route` 选）或下表任一风格。`bpm`、`key`（如 `"D minor"`、`"F# major"`）、`seed` 都可省略。
- 每镜 `mood`：`silent`（无音乐）/ `calm` / `build` / `climax` / `resolve`；要更细可写 `energy: 0-1`（优先于 `mood`）。**不标时按"开场轻→推进→高潮→收束"的默认弧线**，lint 会提醒你去标。
- 其他写法不变：`{"file": "assets/x.mp3"}` 用有授权的现成音乐；`{"generate": "none"}` 无背景乐；`{"generate": "ambient"|"pulse"}` 是旧的单调底乐，仍可用。

## 风格

| style | 听感 | 适合 | `route=auto` 时 |
|---|---|---|---|
| `warm` | 温暖钢琴琶音，轻鼓点 | 汇报、品牌、人物、回顾 | promo、voiceover、script-first |
| `bright` | 明亮、四拍鼓点、有活力 | 发布会、促销、MG 片头 | motion-graphics |
| `tech` | 脉冲低音、方波短音 | AI、数据、产品演示 | product-demo |
| `cinematic` | 厚重长音加定音鼓 | 纪录片、发展史、大事记、剧情 | documentary、ai-drama、hybrid |
| `ambient` | 极简、几乎无节奏 | 知识讲解、科普 | explainer |
| `suspense` | 低频心跳、不协和和弦 | 揭秘、问题、危机段 | 手动选 |

先试听再定：`python "$SKILL/scripts/score.py" --list`；`python "$SKILL/scripts/score.py" --style warm --seconds 30 -o warm.wav --mood calm,build,climax,resolve`。

## 它怎么随剧情变化

- **和声**：每种风格一套和弦进行，**换镜时换和弦**，长镜头内每 2–4 小节再换；新和弦的音靠近上一个（只动小步），听起来是同一首曲子在推进，不是换曲。
- **分层**：铺底总在；`energy ≥ 0.2` 加琶音/铃音，`≥ 0.3` 加低音，更高再按风格加底鼓、踩镲、拍手。calm 段稀疏，climax 段丰满。
- **重音**：切入高能量镜头（比前一镜高 0.15 以上、自身 ≥ 0.75）时，在切点放一记低频冲击。
- **收尾**：全曲结尾 2.5 秒淡出；旁白出现时底乐自动压低（`audio.py` 的闪避）。

## 给每镜标情绪的方法

- 想一下观众此刻该有的感觉，不是画面内容：开场引入 `calm`；信息铺陈、数据递进 `build`；全片最想让人记住的一到两镜 `climax`；结论、致谢 `resolve`。
- **`climax` 不要超过全片 1/4**，否则没有对比；连续 3 镜以上同一 mood 会很平，穿插一镜 `calm`。
- 需要停顿让观众看清或思考的镜头标 `silent`，音乐会让出来（混响尾巴会自然衰减）。
- 旁白很密的镜头别标 `climax`，旁白会被盖住；高潮镜头最好是旁白短或无旁白的画面。

## 改音乐的大白话

| 用户说 | 改哪里 |
|---|---|
| 太吵 / 盖住了人声 | 降该镜 `mood`（`climax`→`build`）；整体降 `music.gain`；合成配乐可换 `ambient` |
| 太平 / 没起伏 | 检查各镜 `mood` 是否几乎一样，拉开 calm 与 climax 的差距 |
| 换一首 / 换风格 | 见上面「用户明确要换 BGM」；合成配乐可调 `style`、`bpm`、`key`（如 `"D minor"`）、`seed` |
| 不要音乐 | `"music": {"generate": "none"}` |
| 想用自己的歌 | `"music": {"file": "assets/x.mp3", "volume": 0.5}` |

## 质检

`audio.py` 输出 `audio/score_report.json`（每镜实测响度、峰值）；`qa.py` 检查"不削波、能量弧线可听出"（climax 比 calm 响 1.5 dB 以上）。

## 没验到的

合成器音色不是真乐器，适合做衬底而非主角；"好不好听"没有自动检查，**交付前要请用户听一遍**。要更高质感时，改用外部音乐文件（`music.file`）或授权的 AI 作曲服务，付费前先报价确认。

## 出处

方法借鉴了几个 MIT 许可的开源项目的思路：按场景配和弦并用近距离换和弦（openvids）、按场景能量作曲（motion-graphics-skills）、风格预设与成品自检（procedural-music）。本 skill 的代码为独立实现，未复制其源码。

# 配乐：默认用内置 BGM，剧情决定起伏

## 选择顺序（谁优先）

| 优先级 | 用户/工程里写了 | 用什么 |
|---|---|---|
| 1 | `music.file` | 用户自带的音乐（须有授权） |
| 2 | `music.style` | 代码合成的"按剧情作曲"（下文；AI 剧用题材预设） |
| 3 | `music.generate` (`none`/`ambient`/`pulse`) | 无背景乐 / 旧的单调底乐 |
| 4 | `music.track` 或什么都不写 | **内置 BGM「Vibe知识大赏」**（只用于代码动画） |

- **代码动画类视频**（promo、explainer、motion-graphics、documentary、voiceover、script-first、hybrid）默认就用内置 BGM，不用问用户、不用配置。
- **纯 AI 漫剧 / 真人短剧**（`ai-comic-drama`、`ai-live-drama`）**不默认用内置 BGM**。新建项目时 `music` 写 `{"style": "auto"}`，按题材选合成配乐：漫剧默认 `workplace`（轻松职场/教学），真人短剧默认 `healing`（治愈/情感）；用户可按下面的题材表换。内置 BGM 与 AI 剧的叙事、节奏和对白避让不匹配。
- **只有用户明确说“用内置 BGM”才允许**在 AI 剧里保留 `{"track": "default", "allowBuiltinTrack": true}`；否则 `bgm.resolve()` 会自动改用合成配乐，并在 `lint.py` / `audio.py` 给出警告。
- **用户明确要换 BGM 才降级**：要换成自己的歌 → `music.file`；要别的风格 → `music.style`；不要音乐 → `music.generate: "none"`。
- 用户只说"换一首/不喜欢这个音乐"没说要什么：先问"用你自己的歌，还是我用代码合成一首（轻松职场/治愈/喜剧/热血/悬疑/电影感/科技/氛围可选）"，听完试听再定。

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
| `workplace` | 温暖电钢琴/拨弦琶音，轻打击，96 bpm C 大调 | 轻松职场、教学漫剧、知识型剧情 | **ai-comic-drama 默认** |
| `healing` | 慢速钢琴/铃音，留白多，78 bpm F 大调 | 治愈日常、真人情感短剧 | **ai-live-drama 默认** |
| `comedy` | 跳跃拨弦、轻拍手、俏皮鼓点，112 bpm G 大调 | 搞笑喜剧、段子、轻松二创 | 手动选 |
| `hotblood` | 推进低音、四拍鼓点，124 bpm D 小调 | 热血、成长、逆袭、比赛 | 手动选 |
| `warm` | 温暖钢琴琶音，轻鼓点，84 bpm C 大调 | 汇报、品牌、人物、回顾、真人情感 | promo、voiceover、script-first |
| `bright` | 明亮、四拍鼓点、有活力，118 bpm G 大调 | 发布会、促销、MG 片头 | motion-graphics |
| `tech` | 脉冲低音、方波短音，100 bpm A 小调 | AI、数据、产品演示、科幻 | product-demo |
| `cinematic` | 厚重长音加定音鼓，72 bpm D 小调 | 纪录片、发展史、大事记、史诗剧情 | documentary、hybrid（显式选 style 时） |
| `ambient` | 极简、几乎无节奏，60 bpm C 大调 | 知识讲解、科普、冥想感 | explainer |
| `suspense` | 低频心跳、不协和和弦，90 bpm E phrygian | 悬疑、惊悚、揭秘、危机段 | 手动选 |

## AI 剧的配乐方案（在剧本/分镜确认时一起定）

纯 AI 剧不要等成片才发现音乐不合适。剧本和分镜表给用户确认时，同时给一个配乐方案：**题材 → 预设 → 20–30 秒试听 → 用户确认**。

1. 按题材选 2 个候选（不要只给一个），例如“轻松职场/教学”给 `workplace` 和 `healing` 两版。
2. 用 `score.py` 出试听：
   `python "$SKILL/scripts/score.py" --style workplace --seconds 25 -o audition_workplace.wav --mood calm,build,climax,resolve`
   把文件路径发给用户听；用户确认后才进入批量生成。
3. 把选定的 `style` 写进 `project.json.music`，并按分镜标 `mood`：开场 `calm`、信息推进 `build`、最强一刻 `climax`、片尾 `resolve`。
4. 对白/旁白密集的段落不要同时标 `climax`；让音乐在说话时退到后面（`audio.py` 会自动闪避）。
5. 片尾署名/出品页使用 `resolve`，音乐在最后 2.5 秒自然收束；不要把高潮留到最后一帧。

**混音**：AI 剧的旁白和生成视频自带的对白/环境音（`clipAudio`）都会进入闪避侧链。AI 剧默认把音乐床压到 0.50（代码动画是 0.62），闪避比 8:1（代码动画 6:1）；对白更重要时可再把 `music.gain` 降到 0.8–0.9，或把该镜 `mood` 从 `climax` 降到 `build`。

**题材与预设的对应**（合成器不是万能，见下方“替代方案”）：

| 题材 | 首选 | 备选 | 说明 |
|---|---|---|---|
| 轻松职场 / 教学漫剧 | `workplace` | `healing` / `warm` | 温暖、明快、不抢旁白；本次培训漫剧的默认 |
| 治愈日常 / 真人情感 | `healing` | `warm` | 慢、留白多；对白段自动闪避 |
| 搞笑喜剧 | `comedy` | `bright` | 俏皮拨弦/拍手；笑点处可加 `pop` 音效 |
| 热血 / 成长 / 比赛 | `hotblood` | `cinematic` | 四拍推进；高潮镜头标 `climax` |
| 悬疑 / 惊悚 | `suspense` | `cinematic` | 低频心跳、不协和；少用旋律 |
| 史诗 / 历史 / 纪录片 | `cinematic` | `warm` | 厚重长音+定音鼓；不适合轻松日常 |
| 科幻 / 科技 | `tech` | `ambient` | 脉冲低音、方波短音 |
| 古风 / 国风 | `warm`（近似） | 用户自带或授权 AI 作曲 | 合成器缺少民乐音色，要求高时不要硬撑 |
| 真人情感短剧 | `healing` / `warm` | `cinematic` | 以对白为主，音乐让路 |

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

## 替代方案：合成器不够用时

合成器适合做衬底、节奏和信息型剧情的情绪推进，不适合当“主角音乐”，尤其是古风民乐、复杂管弦、真实乐队质感。需要更高质感时：

1. **用户自带授权音乐**：`"music": {"file": "assets/music.mp3", "volume": 0.5}`；确认授权范围覆盖成片用途，文件放进项目 `assets/`。
2. **授权的 AI 作曲服务**：先说明用途、时长、风格和预算，**付费前报价并得到用户确认**；下载后同样放进 `assets/` 并登记。
3. **不要**用来源不明、无商用授权的音乐；也不要把“合成器试听”说成最终成品，交付时要让用户实际听。

## 没验到的

合成器音色不是真乐器，适合做衬底而非主角；"好不好听"没有自动检查，**交付前要请用户听一遍**。要更高质感时，改用外部音乐文件（`music.file`）或授权的 AI 作曲服务，付费前先报价确认。

## 出处

方法借鉴了几个 MIT 许可的开源项目的思路：按场景配和弦并用近距离换和弦（openvids）、按场景能量作曲（motion-graphics-skills）、风格预设与成品自检（procedural-music）。本 skill 的代码为独立实现，未复制其源码。

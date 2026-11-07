# 配乐：跟着剧情走的背景音乐

默认配乐不再是一条固定的底乐，而是**按分镜"作曲"**：你给每镜标情绪，音乐随之起伏。全部用代码合成（numpy），不需要音乐库、不联网、不花钱，同一个 `seed` 每次结果一样。

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
| 太吵 / 盖住了人声 | 降该镜 `mood`（`climax`→`build`），或换 `ambient` 风格；`music.volume` 只对 `file` 外部音乐生效 |
| 太平 / 没起伏 | 检查各镜 `mood` 是否几乎一样；拉开 calm 与 climax 的差距 |
| 想要更快 / 更慢 | `bpm`（60–130 之间） |
| 想更欢快 / 更沉重 | `key` 改 major / minor；或换风格 |
| 换一个版本 | 改 `seed` |
| 不要音乐 | `"music": {"generate": "none"}` |
| 想用自己的歌 | `"music": {"file": "assets/x.mp3", "volume": 0.5}` |

## 质检

`audio.py` 输出 `audio/score_report.json`（每镜实测响度、峰值）；`qa.py` 检查"不削波、能量弧线可听出"（climax 比 calm 响 1.5 dB 以上）。

## 没验到的

合成器音色不是真乐器，适合做衬底而非主角；"好不好听"没有自动检查，**交付前要请用户听一遍**。要更高质感时，改用外部音乐文件（`music.file`）或授权的 AI 作曲服务，付费前先报价确认。

## 出处

方法借鉴了几个 MIT 许可的开源项目的思路：按场景配和弦并用近距离换和弦（openvids）、按场景能量作曲（motion-graphics-skills）、风格预设与成品自检（procedural-music）。本 skill 的代码为独立实现，未复制其源码。

# 读音校对：多音字、同音替换与交付前检查

中文 TTS 会在多音字上读错（本次实战：`还款` 被读成 hái kuǎn、`长度` 被读成 zhǎng dù）。字幕仍显示原文，只有送进 TTS 的文本做同音替换。

## 1. 项目级 `voice.pronounce`（持久化）

在 `project.json` 里写“原文 → 送 TTS 的写法”：

```json
"voice": {
  "engine": "edge",
  "voice": "zh-CN-YunxiNeural",
  "pronounce": {
    "还款": "环款",
    "长度": "常度"
  }
}
```

- 只替换配音文本；`vo` 原文、时间线和字幕都用原文（`timeline.py` 读 `vo`，`voice.py` 只在合成前替换）。
- 键越长越先替换，避免“重复”和“重”互相覆盖。
- 替换词放进 `pronounce` 后，`voice.py --check` 会显示“已配置”。
- 换音色/改文案后要重跑 `voice.py`（文本不变时才有缓存命中）。

## 2. 实测记录（2026-11-10）

方法：用 edge-tts 生成原词与替换词音频，再用 faster-whisper `small` 转写，最后用 pypinyin（不带声调）比对。测试音色：`zh-CN-YunxiNeural`、`zh-CN-YunyangNeural`、`zh-CN-XiaoxiaoNeural`。这只是 ASR 证据，不是人耳听感；交付前仍要让用户重点听。

| 原词 | 建议替换 | 实测结论 | 建议 |
|---|---|---|---|
| `还款` | `环款` | Yunyang/Xiaoxiao 原词读 hái kuǎn；Yunxi 该短句 ASR 失败，未确认；**三个音色换成“环款”后都读 huán kuǎn** | 建议写进 `pronounce` |
| `长度` | `常度` | Yunxi / Yunyang 原词读 zhǎng dù，换成“常度”后读 cháng dù；Xiaoxiao 的 ASR 仍归为“长度/zhǎng”，**未确认** | Yunxi/Yunyang 可用；Xiaoxiao 要试听确认 |
| `重复` | `虫复` / `崇复` | 本次在“重复三遍”“重复活”里，三个音色都已经读 chóng fù；没有复现 zhòng | 先不替换；如果实际听感是 zhòng，再试“虫复” |
| `银行` | `银杭` | 三个音色都读 yín háng，正确 | 一般不用替换 |
| `行业` | `杭业` | 三个音色都读 háng yè，正确 | 一般不用替换 |
| `重庆` | `虫庆` | 三个音色都读 chóng qìng，正确 | 一般不用替换 |
| `数据` | `数句` | 测试音色读 shù jù，正确 | 一般不用替换 |
| `为了` | `位了` | 测试音色读 wèi le，正确 | 一般不用替换 |
| `得到` | `德到` | 测试音色读 dé dào，正确 | 一般不用替换 |
| `重要` | `众要` | 测试音色读 zhòng yào，正确 | 一般不用替换 |
| `角色` | `决色` | 测试音色读 jué sè，正确 | 一般不用替换 |
| `处理` | `楚理` | 测试音色读 chǔ lǐ，正确 | 一般不用替换 |
| `参与` | `参玉` | 测试音色读 cān yù，正确 | 一般不用替换 |

注意：同一句话在不同音色、语速、上下文里可能读出不同结果；“ASR 识别成同音字”不等于人耳一定听对。上表只记录本次实测，不保证所有音色。

## 3. 交付前检查

```bash
python scripts/voice.py <项目> --check            # 快速：列出 vo 里的常见多音字和已配置替换
python scripts/voice.py <项目> --check --asr      # 慢：转写已有音频，做拼音级对比
python scripts/voice.py <项目> --check --asr --strict   # 有可疑项时返回非 0
```

输出示例：

```text
[s01] 读音提示：
  建议 还款 -> 环款（huán kuǎn；还 here is huán; all three tested voices read the original as hái and 环款 as huán）
  [ASR] s01: 转写「本月环款日期到了。」
  [ASR] 拼音与配音文本一致（不代表声调一定正确）
```

`--asr` 会用 `scripts/transcribe.py` 的 faster-whisper 模型，第一次运行可能下载模型；不上传音频、不调用付费服务。检查完把可疑项列给用户，请用户重点听这些位置。

## 4. 局限（必须如实说明）

- ASR 只能发现“读音被识别成不同拼音”的问题；**读音正确但声调不对、重音不自然、语气不对，ASR 发现不了**。
- ASR 可能把同音字归一成常见词（例如把“常度”转成“长度”），导致拼音比对出现假阴性/假阳性。
- 多音字是否读错强依赖上下文和音色；`--check` 给的是“要重点听”的清单，不是自动验收。
- 最终以人耳试听为准；交付说明里写清哪些词已替换、哪些仍需用户确认。

## 5. 常见处理顺序

1. 先写 `vo` 原文，字幕保持原文。
2. 跑 `voice.py --check` 看提示；把确认有问题的词写进 `voice.pronounce`。
3. 重跑 `voice.py`，再跑 `voice.py --check --asr`。
4. 把 ASR 不一致或你仍不放心的词列给用户，请用户重点听；确认后再 `build.py --final`。
5. 交付报告里写：“已替换：还款→环款；请重点听：长度、重复。”
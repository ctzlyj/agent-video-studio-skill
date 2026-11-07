# 踩坑与排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 重做新版后，之前加的视频素材不见了 | 素材是在成片上后期叠加的，没进工程 | 所有素材写进 `project.json` + 镜头代码；lint 会检查素材是否存在 |
| 改新版本时把旧工程也改了 | 脚本里写死了绝对路径 | 只用相对路径；新版本用 `new_project.py --version`；lint 拦截绝对路径 |
| 旧名字、错误说法残留 | 只改了画面没改旁白（或反之） | `brand.terms` 统一扫描旁白、`data`、`scenes.js` |
| 渲染中途报 `drawImage ... broken state` | 某帧图片偶发加载失败 | 运行时已对视频帧重试 4 次并跳过坏帧；仍出现时检查 `assets/_frames` 是否完整，重跑 `prep_video.py` |
| 成片比时间线短、结尾被截 | 混音时 amix 以最短输入为准 | `audio.py` 已对旁白和底乐 `apad` 到全长；`qa.py` 会核对时长 |
| 静帧正常、成片某段空白 | 图片解码晚于首帧截图 | 运行时在 READY 前等待所有图片 decode；新增动态 `<img>` 时在 build 阶段创建，不要在 render 里创建 |
| 1.3 倍速后文字读不完 | 屏幕文字停留时间不足 | 文字多的镜头 `speed` ≤1.15，或减少屏幕文字 |
| 配音失败（edge-tts 连不上） | 需要外网 | `voice.engine` 改 `say`（macOS）/ `sapi`（Windows），或提供录音 `engine: file` |
| macOS 上字体不对 | 字体栈没命中 | 确认 CSS 用的是通用字体栈；特殊字体放 `assets/` 用 `@font-face` |
| 生图报 400 `模型服务调用失败` | 用 `images/edits` 却没带参考图 | 无参考图走 `images/generations`（`imagegen.py` 自动选择） |
| 生图偶发超时 | 网关拥堵 | `imagegen.py` 同模型重试；只有额度/限流才换模型，网络错误不降级 |
| Seedance 实扣比报价高约 70% | 报价接口按清晰度×时长，实账按 token（含参考图） | 报价时按 1.7 倍告知；交付后 `lingjing usage show` 核对实扣 |
| 生成视频里的对白没有字幕 | Seedance 现场人声不带时间轴 | `transcribe.py` 转写出每句时间，写进该镜 `subs`；该镜 `clipAudio` 保留原声 |
| faster-whisper 报 `metadata_errors` | PyAV 版本不兼容 | `transcribe.py` 先用 ffmpeg 解码成 PCM 再送模型，绕开 PyAV |
| 配乐很平、没起伏 | 各镜 `mood` 没标或都一样 | 拉开 calm/build/climax；lint 会提醒未标；见 `references/music.md` |
| 配乐盖住旁白 | 旁白密集的镜头标了 `climax` | 降为 `build`，高潮放在旁白短或无旁白的镜头 |

# 改版：把大白话意见落到工程

先 `new_project.py <项目> --version` 复制新版本，再改；改完 `build.py --preview` 给用户看，确认后 `--final`。

| 用户说 | 改哪里 |
|---|---|
| 太长了 / 压缩到 X 分钟 | 先算差额；演示类镜头 `speed` 调到 1.2–1.3，结论镜头 ≤1.15，结尾 1.0；仍不够再删镜或删句（改文案前先问） |
| 这段太快 / 太慢 | 该镜 `speed` 或 `pad` |
| 这句话改成…… | 改该镜 `vo`；`voice.py` 只重配改动的镜头 |
| 名字/叫法不对 | `brand.terms` 加旧→新映射，lint 找出所有出现处（旁白、画面、代码）一起改 |
| 颜色/风格不喜欢 | 改 `STYLE.md` 再改 `style.css`；单镜问题只改该镜 |
| 加署名 / Logo / 二维码 | 结尾镜头 `data` 加字段 + `brand.credit`；放在字幕安全区之上（底部 15% 留给字幕） |
| 把这个视频/图片放进去 | 复制进 `assets/`，写进 `project.json`（视频走 `videos` + `prep_video.py`），在对应镜头 `drawVideo`；不要成片后叠加 |
| 字幕挡住了 / 和画面字重复 | 调 `#sub` 位置或删屏幕上的同句文字 |
| 换个声音 / 读错了 | `voice.voice` 换音色；读错的词加进 `voice.pronounce` |
| 不要背景音乐 / 换音乐 | `music.generate: "none"` 或 `music.file` 指向有授权的音乐 |

每次改完在回复里列：改了哪些镜头、新时长、QA 结果。

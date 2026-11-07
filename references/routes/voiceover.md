# voiceover：已有口播配画面

方法参考 dashi-animationstyle（关键词绑定动作、字级时间、先出静帧）与 jc-remotion-skills。

1. 用户的录音放 `assets/`，按段切成每镜一个 wav（ffmpeg `-ss/-to`，切点选在停顿处），放进 `audio/vo/<id>.wav`，`voice.engine: "file"`。
2. 有文字稿就逐句对齐写进各镜 `vo`；没有稿时先转写（有 whisper 用 whisper，否则请用户提供稿子）。
3. 每句口播挑 1 个关键词，画面动作在关键词出现时落下（在 `scenes.js` 里按该镜时间写入场点）。
4. 先出 3 张不同镜头的静帧确认风格，再做整段。
5. 交付带字幕版和无字幕版（`subtitles.enabled: false` 再渲一次），方便用户在剪映里统一加字幕。

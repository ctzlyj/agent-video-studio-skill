# 引擎：运行时 API 与确定性规则

项目页面 = `index.html`（模板，不改）+ `style.css`（本项目风格）+ `scenes.js`（本项目镜头）。
渲染器逐帧调用 `window.render(t)`，`t` 是成片秒数；运行时把它换算成每镜的局部时间 `lt`。

## 写镜头

```js
const { scene, el, add, set, enter, seg, lerp, E, count, typeText, rand, video, drawVideo, FMT, P } = AVS;
scene('s03', (o, data) => {           // 第一个参数 = 镜头 id，或 project.json 里的 type（多镜复用）
  o.title = add(o.root, el('div', 'abs', data.title, 'left:120px;top:200px;font-size:96px'));
}, (o, lt, dur, t) => {               // 每帧调用：只根据 lt / t 设置状态
  enter(o.title, lt, 0.2, 0.9, { dy: 40, ease: 'back' });
});
```

- `lt` 是**原速秒**：镜头动画按 1 倍速写，`speed` 由运行时统一压缩画面、旁白、字幕和音效。
- `dur` 是该镜原速时长；淡入淡出由运行时处理（`transition: "cut"` 关掉）。
- 尺寸用 `FMT.w / FMT.h` 换算，横竖屏才能共用。
- 工具：`seg(lt,a,b)` 0→1 进度；`E.out/inOut/back/spring` 缓动；`enter()` 入场；`count(0,1200,k)` 数字滚动；`typeText(s,k)` 打字；`rand(seed)` 固定种子随机数。

## 确定性（违反会被 lint 拦下）

- 画面只由 `lt`/`t` 决定。禁止 `requestAnimationFrame`、`setInterval/setTimeout` 驱动动画、CSS `transition/animation`、`Math.random()`、`<video>` 标签。
- 随机效果用 `rand(seed)` 在 build 阶段生成一次，render 里只读。
- 字体用 CSS 字体栈，Windows（微软雅黑）、macOS（苹方）各自命中：`"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif`。需要特殊字体时把 OFL 字体文件放进 `assets/` 用 `@font-face` 加载。

## 视频素材

`project.json`：`"videos": {"demo": {"src": "assets/demo.mp4", "fps": 25, "width": 540}}`，`prep_video.py` 会拆帧并生成 `videos.js`。

```js
o.v = video(o.root, 'demo', x, y, w, h, 'border-radius:16px');   // build
drawVideo(o.v, lt - 2.0);                                        // render：从本镜 2.0s 开始播
```

素材时长要覆盖它在镜头里的展示时长；不够就加大该镜 `pad` 或降低 `speed`，不要让画面停在最后一帧太久。

## 倍速与时长

- 每镜 `speed`（默认 1.0）：演示过程 1.2–1.3，关键结论 1.0–1.15，结尾 1.0。>1.35 时 lint 会警告文字可能读不完。
- 镜长 = `lead`（旁白前空白，默认 0.45s）+ 旁白时长 + `pad`（默认 1.2s），也可用 `dur` 固定、`minDur` 兜底。
- 旁白在 `audio.py` 用 `atempo` 变速不变调。

## 字幕

默认按标点切成横屏 ≤22 字、竖屏 ≤14 字一条，烧进画面（`#sub` 的样式在 `style.css` 里改）。
`subtitles.replace` 可把读音写法换成显示写法（例如旁白写"一百四十三项"，字幕显示"143 项"）；`voice.pronounce` 反过来把显示写法换成读法。
不要烧字幕时设 `"subtitles": {"enabled": false}`；某一镜的画面大字就是旁白原句（开场提问、结尾口号）时，在该镜设 `"subtitle": false`，只保留画面字。

## AI 生成片段（带现场人声）

```json
{"id": "c1", "type": "clip", "dur": 15, "transition": "cut", "clipAudio": "seg1",
 "subs": [[1.44, 4.10, "这么好的杯子，怎么就没人买呢……"]], "data": {"video": "seg1"}}
```
- `clipAudio`：把该视频素材自带的声音（对白、环境音）混进成片；`clipGain` 调音量。
- `subs`：按镜头内时间直接给字幕，时间用 `scripts/transcribe.py` 转写得到，文字用剧本原句。

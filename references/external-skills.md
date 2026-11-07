# 外部 Skill 与风格库

本 skill 吸收了下列项目的方法。需要它们的**风格卡、示例源码或特定能力**时按需拉取，不要整库复制进本 skill。
拉取：`git clone --depth 1 --filter=blob:none --sparse <url>`，再 `git sparse-checkout set <需要的目录>`，放到用户项目的 `refs/` 下。
**许可**：MIT / Apache-2.0 / CC0 可以改编并注明出处；无许可（NONE）只看方法、不复制文本和代码；AGPL 只参考架构，不复制代码。

| 需求 | 项目 | 许可 | 取什么 |
|---|---|---|---|
| 不知道用哪个（通用总控） | Kianzzz/xilo-opus-video | MIT | 3 方案出样 → brief.md 锁定 |
| 特定风格（66 种） | lemomo-ai/lemo-opuscar | MIT | `styles/<风格>/STYLE.md`：archive-lighttable、newsreel、visual-investigation、cel-anime-80s、ukiyoe、ink-wash、swiss-motion、dark-keynote、dataviz、paper-popup、pixel-rpg、watercolor、blueprint、hologram-hud…；先写自己的方案再看 demo |
| MG 动画 | Vincentwei1021/mg-styles-15 | MIT | `prompts/<风格>.md` 的 Signature features 段、`rubric.md` 评审表 |
| 口播配画面 | chuspeeism/dashi-animationstyle | MIT | 关键词绑定、7 套画风的风格词典 |
| 知识/艺术解说 | alchaincyf/huashu-art-motion | MIT | `references/` 的镜头表、正面经验、36 种艺术风格 |
| 从剧本开始 | WaterDJiang/Wattter_openSkills（wtt-code-animation-studio） | 无 | 只看流程 |
| 产品宣传片 | Vincentwei1021/video-shotcraft、H0nGzA1/product-ui-promo | 无 / 未标 | 只看流程：功能→镜头、真实页面采集 |
| 历史纪录片 | （archival-doc 不存在）lemo 档案类风格、Ebaoj/harness-documentario | MIT / — | 档案风格卡、长片剪辑流程 |
| HTML 渲染框架 | heygen-com/hyperframes | Apache-2.0 | 需要其组件库或团队已在用时作为替代引擎 |
| React 渲染框架 | remotion-dev/skills | — | 团队已有 Remotion 工程时用 |
| 全流程生产系统 | calesthio/OpenMontage | AGPL-3.0 | 只参考管线设计 |
| 短剧/漫剧 | UnderleveledBuilder/awesome-short-drama-skills（CC0）、suihe1/short-drama-production（Apache-2.0）、xixihhhh/ai-short-drama-skill（MIT）、djyy1031/ai-comic-drama-director-skills（MIT） | 见左 | 剧本改编、分镜、Seedance 提示词写法、连续性审核 |
| 选型清单（427 个仓库） | zhuyansen/awesome-claude-video-skills | — | 找新类型的参考 |

列表会过时：用户要的类型不在表里时，先在上面的选型清单或 GitHub 搜索，挑星标高、近期更新、许可清楚的项目。

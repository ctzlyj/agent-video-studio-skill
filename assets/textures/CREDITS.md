# 纹理包：来源与授权

纹理来自开源仓库 mg-styles-15（Vincentwei1021/mg-styles-15，MIT 许可，许可全文见 `LICENSE-mg-styles-15.txt`）。随包时只做了缩放/格式转换，没有改内容。

| 文件 | 用途 | 来源与授权（按来源仓库的说明） |
|---|---|---|
| `paper_2048.jpg` | 纸张底纹（暖白纸、纤维） | ambientCG Paper001，CC0；原图 4096 宽，这里缩到 2048 宽 |
| `grain_fine_2048.jpg` | 细颗粒（灰度，可无缝平铺，接缝比约 1.0） | 来源仓库自带，随该仓库 MIT；PNG 转 JPEG q92（灰度，统计特征不变） |
| `grain_film35_2048.jpg` | 35mm 胶片颗粒（灰度，可无缝平铺） | 同上 |
| `dust_01..04_1920.png` | 尘点、划痕、纤维（透明底） | 来源仓库称为共享的程序生成 CC0 素材；原图 3840×2160，这里缩到 1920×1080 |
| `washi_solid_12.png` / `washi_solid_14.png` | 和纸胶带（撕边，透明底，1600×300） | 来源仓库自带，随该仓库 MIT |

用法：`python scripts/new_project.py <项目> --textures` 把整个目录拷进项目的 `assets/textures/`；画法见 `assets/fx/texture.js` 和 `references/mg-styles.md`。
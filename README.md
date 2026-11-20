# ZZZ_Toon

面向 Goo Engine 4.4 的卡通着色器，目标是接近《绝区零》的角色渲染。它是一组节点组，可以单独 Append 到任何材质里使用；[仿ZZZ渲染 · MMD 插件](https://github.com/Teyvat0/zzz-toon-plugin) 用它给 MMD 模型批量配置材质。

> 同人性质的非官方项目，与米哈游无关。仓库不含游戏贴图或游戏数据。

## 内容

`ZZZ_Toon_Core.blend` 里有三个节点组（Append 即可用，已设 Fake User）：

| 节点组 | 作用 |
|---|---|
| `ZZZ_Toon_Core` | 主着色器。59 个输入，分 Surface / Shade / Specular / Rim / Face / MatCap / Grade 七组；输出 `Shader`、`Color`、`Avatar`、`AOV Normal`、`AOV Rim` |
| `ZZZ_Toon_Maps` | 把游戏的 `_N` / `_M` / `_A` 三类贴图拆成通用通道：`Normal`、`Shade Bias`、`AO`、`Metal`、`Spec Mask`、`Smooth`、`ID`、`MatCap Mask`、`MatCap UV` |
| `ZZZ_Toon_Outline` | 描边壳使用的着色器。按材质 ID 从 5 个调色板颜色里取色，深色衣料上自动压暗 |

## 在 Blender 里使用

1. 在 Goo Engine 4.4 里用 文件 → 链接 / 追加，从 `ZZZ_Toon_Core.blend` 追加节点组。
2. 在材质里加一个 `ZZZ_Toon_Core` 组节点，接到 Material Output。
3. 至少设置这些输入：
   - `Base Color`：底色或贴图。
   - `Domain`：1 脸、2 眼睛、3 身体。
   - `Light Dir`：指向光源的世界方向。
   - `Head Forward` / `Head Right` / `Head Center`：脸的朝向、角色右侧、头部中心，只有脸部的 SDF 阴影用到。
4. 材质混合模式用 OPAQUE、HASHED 或 CLIP。BLEND 模式下 `ScreenspaceInfo` 返回的是背景深度，接触阴影和边缘光会失效。

## 光照与材质

- **明暗**：用半兰伯特（与光强无关）乘接收阴影，再加光照贴图 B 通道给出的 `Shade Bias`（范围 ±2）。
- **三段色**：亮部、浅影、深影。阴影色在近处只保留色相，远处保留全色，明暗交界处有暖色的 `Terminator Glow`。
- **接触阴影**：沿光线在视空间偏移约 1 cm（乘 `Model Scale`），前方遮挡超过约 1.5 cm 才变暗。
- **脸**：用 `Light Dir` 和 `Head Forward` / `Head Right` 求水平夹角，以 SDF 的 R 通道做阈值，左右镜像按光源所在一侧切换。SDF 的 A 通道是 `Face Mask`，颈部和下颌回到身体光照。鼻尖线读脸贴图的 Alpha，只在平视时显示。
- **头发高光**：`Hair Spec` 大于 0 时使用发丝模型，手绘的 `Spec Mask` 与半角项先相加再取阈值；头部球面法线只在 `Head Sphere` 半径内生效。
- **金属**：`Chrome` 让金属像素显示 MatCap 反光，`Chrome Tint` 按底色色相染色。
- **MatCap**：`MatCap`、`MatCap Alpha`、`MatCap Mode`（0 插值、1 相加、2 叠加）。需要按材质 ID 自行接线。
- **边缘光**：沿法线的屏幕方向偏移取深度，深度差达到 12 到 30 cm 才亮，用 screen 混合，不会过曝。`AOV Rim` 把受光一侧的边缘光颜色交给合成器。
- **输出前**：曝光、ACES 混合（`Tone Curve`）、饱和度。眼睛不走这一步，只受 `Eye Saturation` 影响。
- 只有眼睛（`Domain` = 2）把贴图 Alpha 接进 `Alpha`；头发和身体保持不透明，穿透效果交给合成器的 Hair / Eye AOV。
- `Multiply Mode` = 1 时用透明 BSDF 乘背景，适合眼影这类暗色叠层。

## 重新生成

节点组全部由 `zzz_toon/` 里的 Python 代码构建，`.blend` 是导出的结果：

```bash
blender --factory-startup -b --python export.py
```

| 文件 | 内容 |
|---|---|
| `zzz_toon/toon_core.py` | `ZZZ_Toon_Core` 的输入表与接口 |
| `zzz_toon/toon_build.py` | `ZZZ_Toon_Core` 的节点构建 |
| `zzz_toon/toon_maps.py` | `ZZZ_Toon_Maps` |
| `zzz_toon/toon_outline.py` | `ZZZ_Toon_Outline` 与描边几何节点的常量 |
| `zzz_toon/toon_surface.py` | 把 Core / Maps 接进材质的辅助函数 |
| `zzz_toon/toon_lib.py` | 搭节点用的小工具 |

这些文件与插件仓库里的 `toon_*.py` 是同一份代码。

## 许可

本着色器以 **CC BY 4.0** 发布，全文见 [LICENSE.txt](LICENSE.txt)：可以自由使用、修改和商用，需要署名并说明是否做了修改。

署名示例：ZZZ_Toon 着色器 by Teyvat0，CC BY 4.0。

## 开发方式

本着色器的设计、代码与文档由 [dsh（DeepSeek Harness）](https://github.com/deepseek-ai/deepseek-harness) 驱动的 AI 编程代理完成，使用的模型有 Opus 5.5、Sonnet 5.5、GPT 6.1 Sol 和 DeepSeek V4.1 Flash。作者负责需求、方向与验收。

[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)

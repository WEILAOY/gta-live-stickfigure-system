# 实时极简火柴人画面系统——可用于GTA直播
# Minimalist Stick-Figure Visual System for GTA Streaming

**中文简介：** V0.32 是一款面向 Windows 的本地桌面工具，可读取本地视频或 OBS 虚拟摄像机画面，分析人物、动物、车辆与环境，并用项目自带的预设素材生成独立动画窗口，供 OBS 或直播软件捕获。推理在本机运行，不需要云端模型 API。输出画布为 1280×720，视频预览静音。本项目为独立工具，与 GTA 或其发行商无官方关联。

**English:** Version 0.32 is a local Windows desktop application for GTA livestream scenes. It reads a local video or OBS Virtual Camera feed, analyzes people, animals, vehicles, and scenery, then renders preset stick-figure and vehicle assets in a separate window for OBS or streaming software to capture. Inference runs locally with no cloud model API. Output is 1280×720 and video preview is silent. This is an independent fan tool and is not affiliated with GTA or its publisher.

## 功能 / Features

- 检测人物、狗和多种载具并跟踪位置。 / Detects people, dogs, and several vehicle classes and tracks their positions.
- 使用预设素材绘制人物动作和车辆视角，支持二维骨骼驱动、手动动作与主角绑定。 / Renders preset character actions and vehicle views, with 2D pose-driven animation, manual actions, and a primary-subject binding.
- 可选显示地平线、道路边缘、建筑外轮廓、漫画阴影或背景色块。 / Optional horizon, road edges, building outlines, comic shading, and flat-color backgrounds.
- 可选识别画面文字并以系统字体排版；部分战斗提示仅为实验性检测。 / Optional on-screen text recognition with system-font rendering; some combat cues are experimental.
- 支持本地视频或 OBS Virtual Camera；输出显示在独立的“火柴人动画输出”窗口。 / Accepts local video or OBS Virtual Camera input and renders to a separate “Stick-Figure Animation Output” window.

姿态、朝向、动作、道路和建筑分析可能误检或漏检，效果会受画质、遮挡、视角和硬件影响，不构成准确率或帧率保证。项目不会将原视频中的人物或车辆像素描摹为输出素材。枪械、火光和 OCR 等实验功能的限制见应用内说明及模型文档。

Pose, direction, action, road, and building analysis may produce false positives or misses. Results vary with video quality, occlusion, camera angle, and hardware; no accuracy or frame-rate guarantee is made. The project does not trace people or vehicles from source pixels into output assets. See the in-app notes and model documentation for experimental weapon, muzzle-flash, and OCR features.

## 安装与启动 / Installation

建议使用 Windows 10/11、64 位 Python 3.13（安装时包含 Tkinter）和 FFmpeg/ffprobe，并确保命令行可找到 `ffmpeg` 与 `ffprobe`。仓库不包含 Python、FFmpeg、OBS 或测试视频。

Recommended: Windows 10/11, 64-bit Python 3.13 with Tkinter, and FFmpeg/ffprobe available on `PATH`. Python, FFmpeg, OBS, and sample videos are not included.

1. 克隆仓库，或下载并解压 GitHub ZIP。 / Clone the repository or download and extract its GitHub ZIP.
2. 双击 `安装检测依赖.cmd`。脚本会创建本地 `.venv` 并安装 `requirements.txt`；它会移除该环境中的冲突 ONNX Runtime CPU/DirectML 包，建议使用新建的 `.venv`。 / Run `安装检测依赖.cmd`. It creates `.venv` and installs `requirements.txt`; it removes conflicting ONNX Runtime CPU/DirectML packages from that environment, so use a fresh project environment.
3. 双击 `启动软件.cmd`。 / Run `启动软件.cmd`.
4. 选择本地视频；使用实时输入时，先在 OBS 启动 Virtual Camera，再在应用中连接。 / Select a local video, or start OBS Virtual Camera and connect to it for live input.

首次安装需要联网下载 Python 依赖。模型权重随仓库提供。Windows 下优先使用 DirectML，不可用时回退 CPU；姿态分析使用 CPU。实际帧率取决于输入视频和硬件。

An internet connection is needed to install Python dependencies. Model weights are included. Windows prefers DirectML and falls back to CPU; pose analysis uses CPU. Actual frame rate depends on the source video and hardware.

```powershell
.\.venv\Scripts\python.exe main.py --smoke-test
```

## 开发与测试 / Development and Tests

核心界面位于 `stickfigure/app.py`；识别和跟踪由 `detection.py`、`vision.py`、`tracking.py` 提供；`assets.py` 定义预设素材，`rendering.py` 负责绘制。`road.py`、`buildings.py`、`ocr.py` 与 `context.py` 处理环境、文字和辅助识别。

The main UI is in `stickfigure/app.py`. Detection and tracking are in `detection.py`, `vision.py`, and `tracking.py`; `assets.py` defines preset assets and `rendering.py` draws them. `road.py`, `buildings.py`, `ocr.py`, and `context.py` handle scenery, text, and auxiliary recognition.

安装依赖后可运行以下测试： / Run these tests after installing dependencies:

```powershell
.\.venv\Scripts\python.exe tools\test_frame_clipping.py
.\.venv\Scripts\python.exe tools\test_tracking.py
.\.venv\Scripts\python.exe tools\test_skeleton_mode.py
.\.venv\Scripts\python.exe tools\test_curbs_and_cadence.py
.\.venv\Scripts\python.exe tools\test_visuals.py
```

`--video-smoke-test`、`--detect-smoke-test`、`--workflow-smoke-test` 与 `--performance-smoke-test` 需要额外的本地视频。短时性能测量只代表对应视频、设置和硬件，不代表持续性能或 OBS 全链路速度。

The `--video-smoke-test`, `--detect-smoke-test`, `--workflow-smoke-test`, and `--performance-smoke-test` options require a local video. Short performance measurements apply only to the tested video, settings, and hardware; they do not represent sustained performance or end-to-end OBS throughput.

## 模型与使用范围 / Models and Scope

模型来源、版本、SHA-256、预处理和许可材料见 [`models/README.md`](models/README.md) 及各模型目录。模型提供分析参数，画面素材仍由项目预设提供。

Model sources, revisions, SHA-256 hashes, preprocessing, and license notices are documented in [`models/README.md`](models/README.md) and the individual model folders. Models provide analysis parameters; rendered visuals come from project presets.

- YOLOX、MediaPipe Pose 和随附 OCR 模型按各自的 Apache-2.0 材料发布。 / YOLOX, MediaPipe Pose, and bundled OCR models carry their respective Apache-2.0 notices.
- SegFormer 道路模型限研究或评估用途，见 [`models/ROAD_MODEL_LICENSE.txt`](models/ROAD_MODEL_LICENSE.txt)。 / The SegFormer road model is limited to research or evaluation; see [`models/ROAD_MODEL_LICENSE.txt`](models/ROAD_MODEL_LICENSE.txt).
- `models/context/` 中扩展模型的权重元数据标注 AGPL-3.0；直升机模型卡另写 MIT。仓库保留此差异，不宣称可按 MIT 重新授权；详情见 [`models/context/README.md`](models/context/README.md)。 / Extension-model metadata in `models/context/` identifies AGPL-3.0, while the helicopter model card also states MIT. This discrepancy is documented without claiming MIT relicensing; see [`models/context/README.md`](models/context/README.md).
- RapidOCR 许可与归属见 [`models/ocr/MODEL_LICENSES.md`](models/ocr/MODEL_LICENSES.md)。未采用的 `models/context/research_not_shipped/` 不属于运行依赖，也不会随仓库发布。 / RapidOCR attribution and licensing are in [`models/ocr/MODEL_LICENSES.md`](models/ocr/MODEL_LICENSES.md). The unused `models/context/research_not_shipped/` models are not runtime dependencies and are excluded from publication.

项目不包含游戏视频。使用者应遵守各第三方许可，并自行确保输入视频、素材和直播内容的使用权。

Game videos are not included. Users are responsible for following third-party licenses and ensuring they have rights to use their input videos, assets, and livestream content.

## 项目性质与代码许可 / Project Status and Code License

作者以非盈利性质分享本项目，用于交流、学习与研究。项目自有代码目前未附开放源代码许可证；公开可见不等于获得修改、再发布或商业使用授权。第三方模型、依赖和素材仍适用各自许可。

The author shares this project for non-profit discussion, learning, and research. The project’s own code currently has no open-source license; public visibility does not grant permission to modify, redistribute, or use it commercially. Third-party models, dependencies, and assets remain under their respective licenses.

## 目录 / Repository Layout

- `stickfigure/`：应用、检测、素材、追踪、渲染和界面代码。 / Application, detection, assets, tracking, rendering, and UI code.
- `models/`：模型、来源信息、哈希和许可文件。 / Models, provenance, hashes, and license notices.
- `tools/`：测试、诊断、基准测试和导出脚本。 / Tests, diagnostics, benchmarks, and export scripts.
- `V0.*_*.md`：版本功能验证记录。 / Feature validation notes by version.
- `AGENTS.md`：项目素材边界和实现约束。 / Asset boundaries and project implementation constraints.

---

<details>
<summary>历史开发与验证记录（V0.31 及更早版本）</summary>

# 历史开发记录

# V0.31 背景颜色开关

“视频预览”页新增“颜色代替阴影”。开启后，背景使用随场景变化的柔和色块，替代排线与脚下网点；人物、车辆和狗继续使用原预设形象。关闭后恢复原来的漫画阴影和天空配置。开关即时应用并自动保存，“背景设置…”里也能切换。

颜色只在现有低分辨率环境分析中量化，不增加模型或推理频率。颜色模式下阴影层次、纹理密度、淡蓝天空暂不可调；“分区精度”对两种背景均有效。说明见 `V0.31_背景颜色开关与验证.md`。

# V0.30 轻量画质优化

人物、车辆和狗根据显示大小切换细节，小目标使用细线并省略装饰；近处整理车窗、车身和关节线条。切换有尺寸缓冲，不随临界大小反复闪变。素材绘制保留小数位置，改善缓慢移动时的线条跳动。

新增与屏幕位置分离的有界素材缓存，主角、动作角标、枪械火光与四侧裁剪继续正常更新。车辆弱方向证据不触发小幅歪动；可靠证据按真实时间纠正。完整人物的小幅尺寸波动受到抑制，坐姿、躺卧、出画和明显缩放及时响应。

没有新增模型或提高推理频率，输出仍为1280×720。固定驾驶片段的20秒同配置短测，画布约25.3→25.0FPS；不代表OBS整链路或长时间性能。详细变化和测量边界见 `V0.30_轻量画质优化与验证.md`。

# V0.29 狗素材

启用画面检测后，现有 YOLOX 模型识别到狗时会调用独立的侧身简笔狗素材。可在“形象与视角”选择“动物·狗”预览两个方向。移动方向用于估计左右，使用固定站姿。

# V0.28 OBS 实时输入

在 OBS 启动虚拟摄像机，双击项目根目录“打开OBS实时测试.cmd”。也可在控制台选择“OBS 虚拟摄像机”，点击“连接 OBS”。程序通过 FFmpeg 读取 OBS Virtual Camera 的视频，分析画面为 960×540，输入上限为 30 FPS。点击“停止”释放连接，之后可以重新连接。

本机 GTA5 实时试跑使用现有精细档、躺卧补检与局部 OCR 配置。12 秒内收到 30.0 FPS，画布约 13.7 FPS，人车识别约 3.5 Hz。测量记录和输出对照保存在 runtime/obs-live-test.json 与 runtime/obs-gta5-output.png。

# V0.27 坐姿检测与素材

增强坐姿/下蹲/站立区分，更新左右坐姿及坐姿手势、手机上身组合。原有三个姿态分析名额中给较矮宽的人物保留一个名额，避免坐姿人物被高个站立人物挤掉。双击“打开坐姿测试.cmd”定位测试短片40秒餐桌镜头。说明见 V0.27_坐姿检测与素材验证.md。

# V0.26 OCR 自定范围

视频预览页点击“识别范围…”：拖拽矩形、底部字幕区、全画面切换，原尺寸/1.5倍精度可选。范围以原画面比例保存，字幕输出仍用原生字体和原位置；新增0.5/0.25Hz频率及区域像素完全一致时复用。打开OCR范围测试.cmd 提供底部字幕、原尺寸、0.5Hz的临时试用。详细说明见 V0.26_OCR范围与性能验证.md。

# V0.25 左右朝向与播放优化

补充右侧前景人物向左持枪/射击；火光分析移出视频解码线程，采用最新帧单槽队列；人物更新不等待火光模型锁，限制 OpenCV 线程竞争。全功能短测预览仍未达到稳定 30FPS，OBS 实时采集入口尚未接入。详细说明见 V0.25_方向与性能验证.md。

# 实时火柴人画面系统 · V0.24 研究评估版

V0.24 修复枪械、持枪动作和火光被过度过滤的问题。持枪显示与开火分开；当前样片可用“形象与视角 → 游戏HUD辅助 / 自动枪型”识别前景长枪、手枪及弹药变化；已确认火光增加首帧显示保护，避免界面忙时整次跳过。两个恢复测试入口及使用范围见 `V0.24_持枪与开火恢复验证.md`。

V0.23 增加本地枪械框核验，删除只有亮点/上半身范围就触发的兜底规则，已用 16 分钟烧车片段验证；新增明确直升机类别检测，自动映射原有预设模型。“形象与视角 → 动作变化角标（2秒）”默认开启，显示玩手机、开枪、倒地等识别动作的变化提示。核验模型主要覆盖手枪，长枪/小枪仍可能漏触发；额外本地模型增加推理耗时。详见 `V0.23_动作角标与识别修正验证.md`。

V0.22 完成六档漫画阴影：留白、疏点、网点、疏排线、密排线、交叉排线。背景默认 120×68 分区，加入有限时间平滑和阈值回差，脚下投影改为两层网点。视频预览右上角“阴影设置…”可调 3/4/6 档、密度及分区精度；默认 6 档 / 中等 / 标准。双击 `打开六档阴影测试.cmd` 可打开 23:20 参考片段。详见 `V0.22_六档漫画阴影验证.md`。

V0.21 将战斗人物改回细线火柴人，手枪用 3 组、长枪用 6 组预设线条。视频预览新增默认开启的“自动火光”，按可见枪口亮点定位并触发 120ms 预设火光；人物动作保持“自动姿态”。双击 `打开23分20秒开火测试.cmd` 可打开本次参考片段，点击播放。枪型使用所选素材，不自动辨认枪型；未见闪光、人物漏检时仍可能漏触发，强反光也可能误触发。它不识别中弹、死亡。详见 `V0.21_极简战斗与自动火光验证.md`。

V0.20 完成手枪、长枪两套三态枪口火光，连接三维枪口并跟随后坐。双击项目根目录 `打开枪口火光素材.cmd` 可查看静态三态、四视角与 15/30 FPS 动画；“只开火”重播一次。该版本为手动素材演示；自动可见闪光分析从 V0.21 起接入。说明见 `V0.20_枪口火光素材验证.md`。

V0.19 针对整幅闪白，改成完整新帧生成后再替换旧帧，并按实际分析耗时调整有限等待。暂停/继续重新分析时短暂保留同时间点画面；新批次漏检仍立即隐藏目标。说明与验证见 `V0.19_闪白修复验证.md`。

V0.18 新增货车和船的预设模型与九视图，接入现有检测类别；车辆匹配请选择“自动估计”。控制台绑定载具后，可单独转 90°/180° 修正方向。朝向分析保持本地运行，未调用 Harness 模型；使用和局限见 `V0.18_货车船与方向验证.md`。

V0.17 新增自动躺卧补检，解决一部分横向人物漏检和倒地素材比例错误。视频预览勾选“躺卧补检”，人物动作保持“自动姿态”；已用第 9:30 秒片段验证固定 DOWN 素材输出。补检增加推理耗时，严重遮挡仍可能漏检。识别到躺卧姿态不代表识别中弹或死亡；使用、证据与限制见 `V0.17_倒地人物补检验证.md`。

V0.16 新增摩托车、直升机多视角预设模型，入口为“形象与视角 → 载具素材”和新增两组九视图。摩托车已接入自动检测；直升机暂为手动素材，未自动识别。视频预览的“漫画阴影”将实体黑灰块换成斜排线与网点，“淡蓝天空”独立控制语义天空区域。详细使用与限制见 `V0.16_载具与漫画阴影验证.md`。

下面 V0.15 及更早段落为历史功能记录；当前阴影显示以 V0.16 的排线、网点为准。

V0.15 将持枪/射击改为简化立体预设，支持斜后方、正后方、侧面、正面；枪械增加枪托、弹匣、握把和黑灰白体块。视频预览新增“黑灰白明暗”，默认“分区+投影”，可选“明暗分区”或“仅脚下投影”。环境 Hz 同时控制路缘、楼群和明暗采样。人车仍用预设素材，战斗事件与视角仍为手动选择。说明见 `V0.15_第三人称与黑灰白验证.md`。

V0.14 加入极简战斗预设：手枪、长枪，以及持枪、射击、中弹、侧倒、倒地五个动作。入口为“形象与视角 → 极简战斗素材演示”，或双击 `打开极简战斗素材演示.cmd`。当前是素材与手动演示，尚未自动识别视频战斗事件；详细说明见 `V0.14_极简战斗素材验证.md`。

V0.13 新增本地 OCR。视频预览勾选“文字识别”后，识别到的中英文会以系统字体显示在画布对应位置，不使用源文字贴图或轮廓。默认 1Hz，可选 1/2/3/5Hz，实际速度见状态行；存在识别延迟及错漏字。详细验证见 `V0.13_OCR文字验证.md`。

当前测试入口为 `打开GTA6完整视频.cmd` 和 `打开GTA6动作片段.cmd`。前者读取用户下载的完整视频，后者使用随包 132 秒短片。人物动作由 6 种扩充到 26 种，按“人物·基础 / 交流 / 生活 / 运动 / 战斗”分组预览。

自动分析可选择基础姿态和部分上肢动作；举重、划桨、搂抱、舞动、攀爬、挥拳目前需要手动选择。手机、杯子等也是预设素材，语义动作需要物品与手部证据。完整说明、自动样片对照及限制见 `V0.12_GTA6动作验证.md` 和 `13_GTA6动作验证`。动作素材库演示不能当作自动识别结果。

V0.11 新增“快速 / 均衡 / 精细”识别档位，默认精细；Windows 自动优先使用 NVIDIA 显卡的 DirectML，初始化失败回退 CPU。人车、路缘和楼群模型的显卡调用串行执行，避免本机驱动在并发调用时发生崩溃。人物车辆的预设素材规则不变。

核心规则：人物和车辆只使用 `stickfigure/assets.py` 定义的预设素材。视频分析提供类别、位置、尺寸、朝向和动作参数；不会把实时轮廓、像素边缘或素描当成人车素材。该规则已记录在 `AGENTS.md`。

## 裁剪与遮挡

仅在视频画面的四条边缘裁剪。保留预设素材的完整尺度和出画位置，不把完整模型缩进残缺检测框。画面内被建筑、车辆等遮住的部分继续使用完整预设素材，不使用遮挡掩膜挖洞。普通线条素材内部留白透明；当前持枪预设使用细线枪身和白色圆头，明暗背景上加细白描边辅助阅读。

车辆使用固定车身网格和预设多视角；人物使用固定关节形象和 26 种预设动作。人体关键点只参与动作识别，不直接生成素材外形。手动视角和动作覆盖继续生效。

跟踪保留已知完整尺寸，应对部分遮挡引起的检测框收缩。当前仍检出的部分遮挡目标继续使用完整预设素材；完全漏检时仅在内部保留身份约 1 秒，不再将预测目标画成浅灰残影。低于 60% 检测评分的新目标需连续关联后才显示；评分不是校准后的准确率。car/bus/truck 共用车辆轨迹，防止同一辆车因类别变化留下重叠身份。未曾完整出现的目标，其完整尺寸只能估计，位置和比例不保证精确。长时间遮挡后仍可能丢失身份。

## 启动与操作

GTA6 使用上方新入口；保留的 `打开GTA5测试片段.cmd` 用于旧版回归，打开第 90 秒驾驶画面；`打开可见区域示例.cmd` 打开第 35 秒近处车辆出画示例。点击“播放/继续”开始；普通入口为 `启动火柴人框架.cmd`。

当前电脑优先使用本地 `.venv`。新电脑需准备 Python 3.13（含 Tkinter）、FFmpeg/ffprobe，并运行 `安装检测依赖.cmd`。人车和环境推理优先使用 DirectML；人体动作分析仍使用 CPU。视频为静音预览。本版不占用采集卡，也不修改 OBS 场景。独立窗口名称为“火柴人动画输出”，逻辑画布 1280×720。

- “视频预览”：播放、暂停、跳转、重放，人车检测与左右路缘开关。
- “形象与视角”：车辆九视图、连续角度、人物 26 种动作和自动/手动覆盖。
- “控制台”：识别档位、人车和环境频率、路缘显示模式、主角绑定、保存配置、重开输出窗口。档位切换立即生效；要重启保留请保存配置。
- “日志与说明”：运行日志。

点击输出人物或车辆可绑定主角，也可在控制台列表中绑定。暂停/继续保留绑定；跳转、停止、换源、切镜头清理旧状态；丢失时不自动换绑。

## 地平线、道路与频率

画布保留人物、车辆、动态地平线、驾驶左右路缘及建筑最外侧轮廓，没有原视频背景或建筑纹理。路缘是两条开放曲线，不填充或封闭。地平线由消失点/弱天空边界证据估计，证据不足时保持或显示虚线参考；不是游戏真实相机参数。

“视频预览”中的“建筑轮廓”控制原视频的紫色外轮廓标注和动画中的建筑边界。只显示建筑区域最外侧的简化轮廓，不提取窗框、立柱或内部竖线。V0.11 环境输入为 512×288，建筑几何使用 384×216 语义图，保留最多 12 个区域和每区域最多 28 个拐点，保留更多远处楼体和屋顶高低变化。建筑贴边时不沿视频边框封口。默认开启，不受“驾驶自动”模式限制；关闭“驾驶路缘”仍可独立显示建筑。建筑与道路共用一次 SegFormer 推理，频率在控制台“环境 Hz”调整。跳转、切镜头、停止及结果过期会清理旧轮廓。

路缘使用 SegFormer 的 road 语义、局部边界与拟合；建筑仅提取 building 主要区域的最外侧轮廓。道路、建筑和地平线不参与人物或车辆素材生成。路缘默认“驾驶自动”，也可“始终检测”；关闭环境分析或模型失败不阻止预设人车输出。语义误判、细小或远处建筑仍可能漏线或误线，当前没有逐建筑实例或精度真值。

默认人车 10Hz（100ms），路缘 5Hz（200ms）。控制台可选择人车 5/8/10/12/15/30Hz、路缘 2/3/5/8/30Hz；这是调度目标，实际频率随场景、源视频帧率和硬件变化。工作队列只保留最新帧，不为凑频率重复分析同一视频帧。实际短测见 `09_预设素材与画面裁剪验证/performance-result.json`，不代表端到端延迟或持续性能保证。启动参数 `--detect-hz 30 --road-hz 30 --output-fps 30` 可选择 30Hz 检测目标和 30FPS 输出刷新目标；重启保留需保存配置。

最新样片、人工核对的人车对照和并行测速在 `12_城市群与识别对照`，其结果优先于旧版速度记录。源视频仅 24FPS，30Hz 目标不能产生每秒 30 张不同源画面。识别档位由 YOLOX Nano/Tiny/S 分别提供；档位大小不保证每个场景都更准。8 张人工核对帧中精细档仍漏掉 3 个标注目标，远处小人和小车仍是难点。楼群仍是语义区域外形，相连楼房可能合并，不能据此宣称逐栋检测或精确三维城市。

## 模型许可

YOLOX-Nano 与 OpenCV Zoo MediaPipe Pose 的 Apache-2.0 许可随附。道路 SegFormer 模型限非商业研究/评估，见 `models/ROAD_MODEL_LICENSE.txt`；商业使用需替换或确认授权。所有权重未修改，来源、SHA-256 和预处理见 `models/README.md` 及 metadata JSON。

## 代码与验证

`assets.py` 定义唯一的人车形象与动作来源；`rendering.py` 绘制这些素材；`frame_clipping.py` 只将素材按视频矩形视口裁剪，不接收视频像素或语义图。`detection.py`、`vision.py`、`tracking.py` 提供分析参数与轨迹；`road.py`、`curbs.py` 独立提供路缘。

`buildings.py` 提供建筑外轮廓；`tools/test_buildings.py` 验证内部孔洞不产生线条、外边界保留、无证据不画线、忽略细小碎片、不画视频边框和绘制清理。`tools/benchmark_buildings.py` 导出实际样片对照，最新报告与图在 `11_建筑外轮廓验证`。原有预设素材与重影修复继续保留。

使用 `.venv/Scripts/python.exe` 执行：

- `tools/test_frame_clipping.py`：四边裁剪、完整预设、短时遮挡、缺失关节不删素材、透明留白。
- `tools/test_curbs_and_cadence.py`、`tools/test_visuals.py`、`tools/test_tracking.py`、`tools/test_detection.py`、`tools/test_road_worker.py`：路缘、调度、素材视角、追踪与后台任务。
- `main.py --smoke-test`、`--video-smoke-test 视频路径`、`--detect-smoke-test 视频路径 --start-at 15`、`--workflow-smoke-test 视频路径 --start-at 90`：界面集成。
- `main.py --performance-smoke-test 视频路径 --start-at 90`：并行频率短测。
- `tools/benchmark_presets.py`：实际样片及人工裁切/遮挡的预设素材对照图。

最新报告与样图在 `09_预设素材与画面裁剪验证`。其中 edge_crop 为人工裁切，occluder_test 为人工加入遮挡块，不冒充原片自然遮挡。旧 V0.7 的素描和语义遮挡裁剪方案已撤回，旧报告仅作为历史记录。尚未做全场景精度评估和长时间压力测试。

</details>

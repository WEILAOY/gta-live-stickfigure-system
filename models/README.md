# YOLOX 人车检测模型

V0.11 同时随附官方 YOLOX-Nano（快速）、YOLOX-Tiny（均衡）、YOLOX-S（精细）。Tiny 为 416×416，S 为 640×640；其余预处理与下述 Nano 相同。权重未修改，均按上游 Apache-2.0 许可随附；各自来源与 SHA-256 见 `model-info.json`、`yolox-tiny-model-info.json`、`yolox-s-model-info.json`。模型档位不是准确率保证。

Windows 使用 ONNX Runtime DirectML 1.24.4，自动选择 DXGI 枚举中的 NVIDIA 显卡，初始化失败回退 CPU。人车与环境显卡会话共用调用锁；这是本机并发崩溃后的兼容处理。输入视频保留至 960 像素宽，目标检测/人体 ROI 使用原画素；相机运动仅用 480 像素工作图以控制开销。设置环境变量 `STICKFIGURE_CPU=1` 可执行 CPU 对照。

环境分割执行输入现为 512×288，路缘几何仍使用 160×90，建筑外轮廓使用 384×216。SegFormer 权重和研究评估许可不变。OBS Detect 附带模型仅在 runtime 目录作对照，不作为正式素材或模型随包分发，也没有安装 OBS 插件。

本项目使用 Megvii-BaseDetection/YOLOX 官方发布的 YOLOX-Nano ONNX 模型，未修改模型权重。

- [官方 ONNX 模型说明](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/demo/ONNXRuntime/README.md)
- [模型下载来源](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx)
- 上游作者：Megvii, Inc. and its affiliates。
- 上游仓库许可：Apache-2.0，随附 `YOLOX_LICENSE.txt`。
- 本地文件来源、大小和 SHA-256 记录在 `model-info.json`。

输入使用 BGR、左上角对齐的 114 填充、416×416、float32、0–255 数值，不进行 0–1 归一化。输出采用 YOLOX 网格与步长解码，并进行按类别的 NMS。该处理遵循官方模型接口；本项目没有导入或修改上游 Python 程序文件。

YOLOX 优先使用 ONNX Runtime DirectML、失败回退 CPU，限制最多 4 名人物及 4 辆车辆。类别包括 person、car、bus、truck。该检测模型只提供类别与框；人体姿态由下述模型补充，车辆多视角由预设网格绘制。

## V0.4 人体关键点模型

增加 OpenCV Zoo 发布的 MediaPipe Pose ONNX 转换模型，未修改权重：

- [官方说明与接口](https://github.com/opencv/opencv_zoo/tree/main/models/pose_estimation_mediapipe)
- [模型来源](https://huggingface.co/opencv/pose_estimation_mediapipe/resolve/main/pose_estimation_mediapipe_2023mar.onnx)
- 许可：Apache-2.0，随附 `POSE_LICENSE.txt`。
- 模型大小约 5.56MB，校验值见 `pose-model-info.json`。

模型以 256×256、RGB、0–1 浮点输入预测人体关键点。项目使用人框周围的正方形区域作为 ROI，再将关键点映射回视频坐标；和上游完整人体检测/旋转校正链路不同，因此在遮挡、非直立姿态和游戏人物上不保证所有点准确。本项目仅使用姿态输出，不绘制原始像素或分割纹理。

## V0.5 道路语义分割（研究评估）

- [ONNX 转换发布者 Xenova](https://huggingface.co/Xenova/segformer-b0-finetuned-cityscapes-1024-1024)
- [上游 NVIDIA 模型](https://huggingface.co/nvidia/segformer-b0-finetuned-cityscapes-1024-1024)
- [上游许可](https://github.com/NVlabs/SegFormer/blob/master/LICENSE)，随附 `ROAD_MODEL_LICENSE.txt`。该模型限研究或评估用途；不适用于未经授权的商业用途。
- 模型文件约 15.2MB。V0.6 为降低 CPU 开销，执行输入改为 384×256；权重未修改。仍使用 RGB、ImageNet 均值/标准差。发布者原始配置保存在 `road-preprocessor.json`，其中的 512×512 是上游配置，不是本版执行尺寸。
- 使用 Cityscapes 的类别 0（road）及周边语义，提取左右开放路缘，进行图像梯度修正、曲线拟合与平滑。车辆语义用于连接被遮挡道路，但不将车身边界当作路缘。没有合成背景纹理。
- 来源与 SHA-256：`road-model-info.json`；处理配置：`road-preprocessor.json`。

V0.10 环境模型同时提供路缘及建筑最外侧轮廓，不向人物或车辆提供语义掩膜或像素边缘。人物、车辆一律使用预设素材。模型权重和许可不变。

## V0.13 文字识别

`ocr/` 保存 RapidOCR 3.10.0 随包 PP-OCRv6 检测、识别及备用方向模型。权重未修改，哈希、来源、代码许可和模型许可通知随附。使用本地 CPU，不与已有 DirectML 会话并发执行 OCR GPU 推理；只向画布提供字符串、位置和评分。

"""Write a report from recorded measurements, with their scope and limits."""
from pathlib import Path
import json

base=Path(__file__).resolve().parents[1]
out=base.parent/'12_城市群与识别对照'
cpu=json.loads((out/'model-audit.json').read_text(encoding='utf-8'))
gpu=json.loads((out/'model-audit-gpu.json').read_text(encoding='utf-8'))
perf=json.loads((out/'performance-gpu-30hz.json').read_text(encoding='utf-8'))
stress=json.loads((out/'gpu-switch-stress.json').read_text(encoding='utf-8'))
by_name={r['model']:r for r in gpu['summary']}
table=['| 模型 | 检中 | 误检 | 漏检 | CPU 单次中位数 | GPU 单次中位数 |',
       '|---|---:|---:|---:|---:|---:|']
for row in cpu['summary']:
    other=by_name[row['model']]
    assert [row[k] for k in ('tp','fp','fn')]==[other[k] for k in ('tp','fp','fn')]
    table.append(f"| {row['model']} | {row['tp']} | {row['fp']} | {row['fn']} | {row['median_ms']:.1f}ms | {other['median_ms']:.1f}ms |")
text=f'''# V0.11 精细识别、GPU 加速与楼群外轮廓验证

## 已实现

- 控制台新增快速 / 均衡 / 精细档位，对应原版 YOLOX Nano / Tiny / S；默认精细，切换时清理旧推理结果及追踪状态。三份权重来源、SHA-256、Apache-2.0 许可随附。
- Windows 自动选择 DXGI 枚举中 RTX 2050 的 DirectML。初始化失败可回退 CPU；已实际验证强制 CPU 模式。独立的人车和环境工作队列仍只保留最新画面。
- 原先解码宽度 560 改为上限 960，本样片保留 852×480；人体 ROI 使用保留后的画素。相机运动用 480 像素工作图，避免让背景计算抵消目标检测提速。
- 修复低评分、被高评分完整人框包含且顶部对齐的人体碎片重复框；相邻两人不按此规则合并。继续隐藏无当前检测证据的预测残影。
- 环境输入从 384×256 提到 512×288，建筑语义几何从 160×90 提到 384×216。最多保留 12 处建筑区域，最多 28 个外边界拐点，保留更多远处建筑和屋顶高低变化；不画窗框、立柱或内部竖线。
- 人物和车辆仍只用预设素材，被场景遮住时保留完整素材，只在画面四边裁剪。无需 OBS 边缘滤镜参与人车素材生成。

## 人工核对与速度

人工核对 8 张原生 852×480 的 GTA 视频帧，共 17 个明确标注目标；较模糊/约 20 像素以下目标放入忽略区。IoU≥0.5 才记检中，car/bus/truck 统一按车辆评估。蓝框为人工标注、绿框为检中、红框为误检、灰框为忽略区。标注框和预测坐标完整保存在 `model-audit.json`。这是小样本原始检测对照，不是整体准确率，也不是追踪后画面效果评分。

{chr(10).join(table)}

CPU/GPU 均使用 ONNX Runtime {cpu['runtime_version']}；单次中位数包含预处理、模型与框后处理，不包括追踪、动作、楼群分析或界面。每张图预热后取 3 次，表中再取 8 张图的中位数。两个后端的检中/误检/漏检计数在这些帧上相同，不能据此保证所有画面完全一致。

精细档在第 90 秒检出原 Nano 漏掉的右侧人物；第 55.6 秒 Nano 把桥附近画面误认作大车。精细档仍漏掉远处小车、小人。均衡档在第 35 秒把门口误认作巴士，说明大模型档位不保证每帧更准。

30Hz 人车目标、5Hz 环境目标、30FPS 输出刷新目标的并行短测：实际人车 **{perf['human_measured_hz']:.2f}Hz**，环境 **{perf['road_measured_hz']:.2f}Hz**，预览/绘制 **{perf['preview_fps']}FPS**。人车最近一次完整分析 {perf['latest_human_ms']:.1f}ms，环境 {perf['latest_road_ms']:.1f}ms。源视频只有 24FPS，未达到 30 次/秒人车检测；不能把目标值当实测值。原有用户配置的 15FPS 输出、10Hz 人车、5Hz 环境保留，未自动改成 30。

## OBS 结论

已把 OBS Detect 0.0.3 附带的 EdgeYOLO 小模型数据抽出，在同一套 CPU/GPU 框架、相同标注帧上比较；没有运行插件 DLL，也没有安装插件或修改 OBS。其已解码的输出按实际接口适配，避免重复解码。它能额外检出某些远处车辆，但漏掉第 90 秒人物，并在第 55.6 秒把地面杂物认成车。当前没有依据认为改到 OBS 就比本软件精细档更准。这不是 OBS 插件端到端测速，参考模型不随正式包分发。

[OBS Detect 上游仓库](https://github.com/royshil/obs-detect)已归档。普通 [obs-shaderfilter](https://github.com/exeldro/obs-shaderfilter) 的 [edge_detection.shader](https://github.com/exeldro/obs-shaderfilter/blob/master/data/examples/edge_detection.shader) 提取亮度边缘，不能直接解决人物/车辆类别误检。显卡加速按照 [ONNX Runtime DirectML 官方配置](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html) 使用顺序执行和关闭内存模式优化。

## 楼群效果与限制

`street_*.png` 从左到右是原画面、V0.10、V0.11；原图与输出使用相同时间点，当前弱评分目标用真实的前一帧作追踪确认，未复制单帧伪造连续证据。只输出检测到的建筑区域外边界，不凭空添加楼房。测试片段主要是街道近景，并非密集城市全景。

新轮廓保留更多连续屋顶变化；它仍来自 Cityscapes 语义区域，相连楼体可能合并，树木遮挡也会造成缺口或错线。尚未达到逐栋城市实例识别或准确三维重建，不能把增加拐点数量等同于城市精度提升。

## 稳定性与回归

39 项单元检查通过，包括三档切换竞态、GPU 初始化失败回退、显卡调用互斥、内部孔洞不画线、远处建筑和屋顶阶梯、人物碎片去重、相邻人物保留、预设素材/画面裁剪、路缘与追踪。

模拟、真实视频、精细模型人车、道路/楼群工作流集成通过。另有实际 CPU 回退检测与 {stress['duration_seconds']:.1f} 秒显卡连续切档/跳转检查通过。详细记录在相邻 JSON 中。

双模型直接并发调用 DirectML 时曾出现驱动访问冲突；现共用调用锁串行执行，退出时等待后台线程结束，修复后上述短测通过。短测不代表长时间运行保证；没有实测 30FPS 持续精确识别。
'''
(out/'V0.11_对照与验证报告.md').write_text(text,encoding='utf-8')
(base/'V0.11_GPU识别与楼群验证.md').write_text(text,encoding='utf-8')
print('report written')

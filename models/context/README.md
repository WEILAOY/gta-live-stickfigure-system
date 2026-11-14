# 本地扩展识别模型

仅输出类别、框和持枪证据，不输出素材。CPU ONNX Runtime 执行；人物和载具仍由 assets.py 预设绘制。

| 文件 | 来源与固定版本 | 实际用途 |
|---|---|---|
| helicopter.onnx | [Hunjun/yolo-tank-detection](https://huggingface.co/Hunjun/yolo-tank-detection/tree/2b0f956ad5363d19477ac00585679654e4c04c00)，optimized/student_quantized.onnx | 使用明确 Helicopter 类，不将 Airplane/Vehicle 重命名为直升机 |
| pistol.onnx | [Hadi959/weapon-detection-yolov8](https://huggingface.co/Hadi959/weapon-detection-yolov8/tree/1c7397a7f9268ed60611650cdad936e306a3dc04)，best.onnx | 只用 pistol 类核验紧凑枪械框；knife 不作为开枪证据 |

这是研究评估接入。持枪模型的显式类别只有 pistol，不能据此声称支持所有长枪；小枪、遮挡、角度变化会漏检。输出分数不是校准后的正确率。剔除整幅画面大小的异常枪框，并在触发端要求手腕、枪框、亮点相互匹配；枪械证据缺失时不触发。

两份 ONNX 内嵌元数据都写明 AGPL-3.0，随附上游 AGPL 文本。直升机仓库模型卡另写 MIT，保留此差异，不宣称已解决许可冲突或可按 MIT 重新授权。权重来源、SHA-256 和元数据记录在 model-info.json；上游 [Ultralytics](https://github.com/ultralytics/ultralytics) 的许可说明也应保留。

research_not_shipped 是开发中未采用的分类模型试验，不属于运行依赖，也不进入发布包。

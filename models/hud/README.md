# 样片 HUD 分析参考

`gta5_hud_features.npz` 保存当前测试素材中武器图标的稳定梯度特征及数字字形特征，用于局部匹配和弹匣计数。仅供分析，不是可绘制人物/枪械素材，也不传入画布渲染器。

`reference-info.json` 保存归一化参考布局、构建样本标注和特征文件 SHA-256。构建脚本是 `tools/build_hud_reference.py`。运行模块 `stickfigure/hud.py` 只使用布局和特征，不使用参考样本时间来安排动作或射击。

目前支持这组 GTA5 HUD 中的长枪、手枪及燃烧瓶排除；不宣称适配全部游戏布局或全部武器。

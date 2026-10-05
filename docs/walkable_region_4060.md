# 4060 可行走区域验证

桌面端可用 `nvidia/segformer-b0-finetuned-ade-512-512` 的 ADE20K 分割结果估计道路/人行道的连续区域。模型权重由 Transformers 缓存，不放入仓库。

```powershell
python -m pip install -r requirements-4060.txt
python scripts/detect_video.py <video> <report.json> `
  --model android/app/src/main/assets/two_wheeler_candidate_320.onnx `
  --walkable-model nvidia/segformer-b0-finetuned-ade-512-512 `
  --walkable-interval 4
```

`walkable_interval=4` 表示每 4 帧更新一次分割，中间帧复用上一结果；这只影响 4060 回放验证。模型加载失败、掩码无法从画面底部连通到中央区域或置信度不足时，输出 `geometry_fallback`，不会把未知区域当成安全。

手机端首版仍使用轻量几何回退，直到真机性能和可行走区域模型分别通过验证。

## 2026-10-05 关键帧视觉复核

在 4060 上用同一适配器复核了一个严格冲突帧（`VID_20260922_170525`，帧 56）
和一个安全场景帧（`VID_20260922_170259`，帧 108）。两帧都成功输出
`segformer_ade20k` 区域，未使用几何回退；冲突帧的中央目标接地点落在路线走廊内，
右侧停放车辆落在走廊外。可视化结果保存在外部复核目录
`C:/Users/19770/Documents/Codex/blindnav_external/walkable_inspect_20261005/`。

这一步证明了 4060 回放可以提供道路/人行区域边界和目标接地点关系，但单帧推理约为
数秒级，不能把它当作实时手机分割方案。手机继续使用几何回退；后续只有在真机测得
延迟后，才决定是否移植更小的自由空间模型。

## 2026-10-05 路线方向证据门槛

分割结果现在额外计算中央、左侧和右侧候选走廊的连续表面支持率，并保留遮挡和未知像素。
只有表面类别明确、区域置信度达到门槛且支持率连续满足要求时，才会给出直行或绕行方向。
几何回退不再根据检测框之间的空隙猜测方向；它仅用于中央路线内目标的风险判断，方向不明确时返回减速状态。

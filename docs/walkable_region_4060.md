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

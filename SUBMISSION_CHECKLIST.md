# 比赛提交前清单

目标不是把未验证的内容包装成完成，而是让评审能清楚区分：当前仓库能复现什么、现场需要补跑什么、下一阶段还缺什么。

## A. 提交前在当前电脑完成

- [x] 已初始化 Git 并建立可复现基线提交；后续实验按功能或验证批次提交。
- [ ] 安装 `requirements.txt` 中的依赖，并确认 Python、PyTorch、Ultralytics 版本。
- [ ] 运行 `python scripts/check_environment.py`，确认依赖没有缺失或版本不兼容。
- [ ] 运行 `python -m unittest discover -s tests`，记录测试数量和结果。
- [ ] 运行 `python scripts/acceptance_check.py -o acceptance.json`，确认 `passed: true`。
- [ ] 运行 `python scripts/submission_audit.py`，确认 `passed: true`；若失败，处理 `blocking_items`，不要只看单元测试绿灯。
- [ ] 运行 `python scripts/evaluate_risk_engine.py`，保留阈值扫描输出。
- [ ] 用一份可公开使用的视频或检测框 JSON 跑 `detect_video.py` / `replay_detections.py`，保存原始 JSON 报告。
- [ ] 若展示性能，使用 `benchmark_pipeline.py`，同时记录设备、模型、分辨率、输入 FPS、预热帧数。
- [ ] 检查所有对外材料没有把合成数据写成真实道路准确率。

## B. 答辩现场演示顺序

1. 先运行 `acceptance_check.py`，证明核心逻辑和反馈协议可复现。
2. 打开一条接近场景的回放 JSON，展示 `looming`、风险等级、方向和 `feedback`。
3. 如果机器和视频准备好，再展示 YOLO + ByteTrack 的实时或离线运行。
4. 展示安卓接入协议，说明手机端只消费 `feedback`，不自行猜测距离。
5. 主动说明真实胸挂视角数据、安卓真机和视障用户验证的状态。

## C. 可以宣称的内容

- 已完成从检测/追踪结果到风险特征、分级告警和平台无关反馈 JSON 的软件闭环。
- 已有连续窗口平滑、真实帧间隔归一化、FPS 参考归一化和 ByteTrack 接入。
- 已有参数化场景、阈值扫描、回放和一键验收测试。
- 已定义安卓震动、提示音、语音的跨模块协议。

## D. 当前不能宣称的内容

- 真实道路准确率、召回率、误报率、漏报率或预警提前秒数。
- 安卓骁龙 7/8 系列上的实时 FPS、功耗、发热和端到端延迟。
- 视障用户实际使用效果或 O&M 专业人员认可。
- 精确距离、精确碰撞时间、100% 避障或替代导盲杖/导盲犬。

## E. 最短补强路径

如果只能再投入半天，优先级为：

1. 按 [DATA_COLLECTION.md](DATA_COLLECTION.md) 完成最低 12 段采集，并填写 `data/collection_manifest.csv`；
2. 在一台安卓真机上把 `feedback` 映射到振动器、音效和 TTS；
3. 记录端到端延迟和三种告警动作的现场视频；
4. 把结果填回 `PROJECT_STATUS.md`，并注明采集条件和局限。

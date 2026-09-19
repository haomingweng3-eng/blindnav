# 视觉、导航与助盲项目横向对比

**检索日期**：2026-09-19  
**目的**：寻找可学习的工程结构、算法模块和验证方法，不把宣传页中的“支持功能”直接当作安全能力证据。

## 结论先行

真正和本项目形成互补的不是某一个“AI 导盲眼镜完整方案”，而是四类技术：

1. **动态目标筛选与反馈节流**：SightWalk、Lyne ADAS 和 BlindNav-Aid 都把“只播报可能影响用户的目标”作为核心工程问题。
2. **自运动补偿**：BlindNav-Aid 使用背景深度和 ego-motion compensation；Motor Focus 研究用光流估计人体/相机运动。它们直接对应本项目当前停车场视频中的误报问题。
3. **可行走区域/自由空间**：SightWalk 和 Blind Guidance System 不只检测物体，还判断用户能走的区域，这比单纯扩大目标类别更能约束风险判断。
4. **感知设备与计算设备解耦**：OpenGlass、AI-FanGe 项目都把摄像头/麦克风/IMU和后端推理分开，适合作为我们 Android + 可选胸挂设备的系统架构参考。

## 项目矩阵

| 项目 | 输入与部署 | 核心能力 | 反馈/验证 | 对本项目的价值 |
|---|---|---|---|---|
| **BlindNav（本项目）** | 手机 RGB 视频；Android 目标形态，当前桌面端 | YOLOv8n + ByteTrack + looming/横向风险 + 告警仲裁 | 13 段安全距离视频；当前无危险事件召回证据 | 重点补自运动补偿、正向事件和 Android 闭环 |
| **SightWalk** | button camera + Jetson Xavier | 物体检测、目标时序跟踪、运动方向向量、盲道偏移和转弯分类 | 音频 + 腰部震动；公开自定义数据和演示 | 学“碰撞相关目标筛选”和“盲道状态约束”，不直接抄旧 YOLOv4 管线 |
| **BlindNav-Aid** | Raspberry Pi 4 + RealSense D435 | 深度距离、YOLO ONNX、ego-motion compensation、TTC、静态目标抑制 | 本地音频/TTS、冷却桶、事件日志；仓库自报有回归套件 | 当前最值得复现的工程参考：自运动、冷却、延迟日志、回放测试 |
| **Blind Guidance System** | iPhone + ARKit/LiDAR；Python WebSocket 服务 | SegFormer 地面分割、YOLO11-seg、深度估计、自由空间、路径中心 | ILD/ITD 空间提示音；分帧调度和 EMA 稳定 | 学自由空间、空间音频和“不同模型不同频率”，不采用其服务端依赖作为主方案 |
| **Lyne ADAS** | Android CameraX，端侧推理 | YOLOv8n、可行驶区域分割、IoU 追踪、单目 TTC、自适应阈值 | 音频/视觉/触觉；事件时间线、设备自适应 | 最适合参考 Android 工程：推理调度、设备自测、低置信度不升级硬告警 |
| **AI-FanGe OpenAIglasses** | ESP32-CAM + Python/CUDA 后端 + WebSocket | 盲道、过街、红绿灯、物品查找、ASR/多模态对话 | 语音、Web 监控、IMU 可视化；作者明确称仅供学习 | 学导航总控和模块拆分；不照搬云端功能堆叠，也不把功能列表当安全验证 |
| **MIT ALVU / Wearable Blind Navigation** | ToF 传感器腰带 + 腹部振动带；另有相机/嵌入式版本 | 自由空间、障碍和楼梯感知；低/高悬障碍 | 12 名盲用户、162 次试验 | 作为用户验证和触觉编码的高质量基准，不是代码依赖 |
| **Motor Focus** | 单目视频 + 光流 | 无需相机标定的自运动/运动意图估计 | 50 个行人场景片段，报告 >40 FPS 等实验结果 | 优先研究其自运动抑制思想，可能直接降低本项目 looming 误报 |
| **OpenGlass** | ESP32-S3 摄像头/麦克风 + 附近主机 | 感知—计算分离、本地多模态、会话回放和评测工具 | 记录、重放、延迟与硬件文档 | 学设备桥接、session replay 和隐私边界；不把 MLLM 对话加入当前 MVP |

## 三个最值得实际拉代码学习的项目

### 1. BlindNav-Aid：优先级最高

它与我们的目标最接近，且已经把几个容易被忽略的工程问题显式化：背景深度自运动补偿、静态目标抑制、按距离分桶冷却、事件日志和离线回放。其 README 还明确把音频播放不强制打断、队列、冷却、措辞和延迟作为可测试对象。先学习它的测试和日志设计，再决定哪些算法适合我们的单目 RGB 条件。

### 2. Lyne ADAS：Android 落地参考

它不是助盲项目，但 Android 端的结构高度相关：CameraX、端侧 YOLO、推理调度、追踪、TTC、事件记录和设备自适应。特别值得借鉴“低置信度估计只记录、不升级成硬告警”的边界，这可以成为我们的 Android 风险入口规则。

### 3. SightWalk：场景与反馈参考

它的价值不在模型新旧，而在于明确只把“可能与用户碰撞的对象”交给反馈层，并同时判断盲道偏移和转弯。它还使用音频和腰部震动的双通道，这与本项目的分级反馈方向一致。

## 现在应该做什么

### P0：直接进入本项目

- 加入摄像头整体运动估计：先用稀疏光流/背景特征做轻量版本，不立即引入深度模型。
- 在报告中区分 `raw_alert_count` 和 `operational_alert_count`，继续保留原始告警供审计。
- 把低置信度、走廊外、单帧抖动和无稳定轨迹的目标禁止升级成硬告警。
- 学习 Lyne ADAS 的 Android 推理调度和设备自测结构。
- 学习 BlindNav-Aid 的事件日志、延迟字段和离线回放方式。

### P1：有视频和 Android 后再做

- 轻量可行走区域/道路边界分割，只用于风险约束，不做完整路径规划。
- 空间提示音的左右声道编码，与现有震动/短音组合。
- 手机与胸挂摄像头的传感器桥接层，记录源帧号、时间戳和丢帧情况。

### 暂不做

- 云端多模态对话、物品购物、完整红绿灯过街决策。
- ESP32 上直接跑主模型。
- 为了“功能看起来更多”而加入盲道、地图、红绿灯等未经验证的模式。

## 重要的证据边界

- SightWalk、AI-FanGe 和多数 GitHub 项目证明的是“系统原型存在”，不能直接证明真实安全性。
- MIT 的 ALVU 页面提供了更强的用户研究证据：12 名盲用户完成 162 次试验，但其传感器和触觉系统与本项目不同，不能直接移植指标。
- BlindNav-Aid、Lyne ADAS 的性能和测试数字主要是各自仓库的自报结果，复现前不写入本项目 PPT 的硬指标。
- 本项目目前只有安全距离视频基线；任何“真实召回率、漏报率、预警提前量”仍必须等受控危险事件标注后再报告。

## 参考链接

- [SightWalk / outdoor-blind-navigation](https://github.com/team8/outdoor-blind-navigation)
- [BlindNav-Aid](https://github.com/Anthonyiswhy/blind_navigation_aid)
- [Blind Guidance System](https://github.com/Southik/Blind-Guidence-System)
- [Lyne ADAS](https://github.com/Sherin-SEF-AI/Lyne-ADAS)
- [AI-FanGe OpenAIglasses for Navigation](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation)
- [MIT Wearable Blind Navigation](https://www.csail.mit.edu/research/wearable-blind-navigation)
- [Motor Focus](https://arxiv.org/abs/2404.17031)
- [OpenGlass](https://github.com/OpenSQZ/OpenGlass)

## 对 AI-FanGe Issues 的二次审查

Issue #17 的五点建议很有价值，但优先级不能照单全收。它们来自使用者和复现者的真实反馈，尤其能暴露“演示能跑”和“长期可用”之间的差距；例如该仓库还有声音卡顿、重复初始化、交通灯误检/漏检和分割性能等公开问题。

| 建议 | 判断 | 本项目决策 |
|---|---|---|
| 摄像头放脖子/胸口下方 | 值得做形态实验；胸口更稳定、可容纳更大电池和手机支架，但会改变视野、俯角和隐私边界 | **P0 形态对比**：手持、胸挂、颈下三种只比较稳定性/视野/遮挡，不立即冻结外壳 |
| 手机本地模型、避免云端 | 方向正确；安全告警不能依赖网络。Issue #14 也出现了地区 API 不可用的问题 | **P0**：安全检测、追踪和风险在手机本地；云端只允许作为非关键的场景描述 |
| 双摄、深度或 SLAM | 技术上有帮助，但会引入标定、同步、功耗和端侧算力成本；SLAM 也不等于碰撞预测 | **P2**：先用单摄 + 光流/IMU 自运动补偿；若误报仍受限，再评估双目/ToF |
| 地图导航或常走路线模型 | 高层路线导航有价值，但“给盲人常走的路预训练”涉及数据隐私、泛化和样本量，不能作为短期技术壁垒 | **P1**：接入成熟地图 SDK 做路线；不训练个人路线模型 |
| 与红绿灯等 IoT 互联 | 长期可扩展，但依赖道路基础设施和标准；不能在基础设施缺失时影响安全判断 | **P3**：只做未来扩展接口，不放入当前 MVP，也不输出“可以安全过街”的自动决策 |

### Issue 中最值得吸收的工程教训

- **声音卡顿不是小问题**：反馈必须有队列、短提示音优先、TTS 非关键路径和可测的播放延迟；不要在危险链路里等待云端语音。
- **交通灯不能只靠单帧 YOLO**：必须结合信号灯类别、时间稳定性、视角和行人/车辆信号关系；当前项目暂不承担过街安全决策。
- **模型效果取决于领域数据**：Issue #23 对斑马线分割效果的质疑说明，公开数据集验证不能替代目标视角测试。
- **生命周期必须幂等**：Issue #16 的重复初始化问题对应我们未来 Android 的相机、推理线程、音频播放器和导航状态机；启动、暂停、恢复、销毁都要可重复执行。
- **空间音频可以作为低成本加分项**：Issue #12 的“用立体声描绘画面”适合先做左右方向短音，不必一开始引入完整 3D 音频引擎。

Issue 来源：[#17](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation/issues/17)、[#20](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation/issues/20)、[#23](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation/issues/23)、[#24](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation/issues/24)、[#14](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation/issues/14)、[#16](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation/issues/16)、[#12](https://github.com/AI-FanGe/OpenAIglasses_for_Navigation/issues/12)。

# Android 构建证据

最后验证日期：2026-09-21

## 本机结果

在 macOS Apple Silicon 上使用 Homebrew OpenJDK 17 执行：

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
cd android
./gradlew clean test assembleDebug
```

结果：`BUILD SUCCESSFUL`。

- Android JVM 单元测试：Debug/Release 均通过
- Debug APK：`android/app/build/outputs/apk/debug/app-debug.apk`
- APK 大小：89,533,925 bytes
- APK SHA-256：`7096412a2266c0cee533548b66f4494663a9a5a2cf373c0ef8d0397967aac20a`
- Android 静态契约检查：通过

构建时有两类非阻断提示：Android SDK XML 版本提示，以及 ONNX Runtime/CameraX 原生库无法 strip、因此按原样打包。这两项没有导致构建失败，也不等于真机性能已验证。

## 尚未完成的验证

当前机器没有连接到可用 Android 真机，因此没有声称 APK 已安装、摄像头权限已授予、CameraX 预览已显示、反馈自检已实际发声/振动、端侧 FPS/延迟已测量或长时间运行稳定。

## 2026-10-03 当前候选构建

在本机准备的 Microsoft OpenJDK 17 和 Android SDK 35 环境中重新执行：

```text
gradlew.bat clean test assembleDebug
```

结果：`BUILD SUCCESSFUL`；Debug/Release JVM 单元测试均通过（Debug 30
tests，0 failures）；当前 Debug APK：
`android/app/build/outputs/apk/debug/app-debug.apk`

- APK 大小：98,099,099 bytes
- APK SHA-256：`9e5cd5005c1eeab86ac55161ef1bb3933eaf7fc36621acf930e4dba90aa2ea68`
- 包含当前两轮车 ONNX、骑行者过滤和路线预测代码
- 仍未连接真机，因此安装、摄像头、端侧 FPS、反馈硬件和长时间运行未验证
- `android_smoke_test.py` 当前结果：`no_device`（ADB 设备列表为空）

## 2026-10-03 构建状态修正

上面的历史 APK 条目不包含当前改动；本节之后的“当前候选构建”条目已经
覆盖该限制，包含 `two_wheeler_candidate.onnx`、`RiderGateDetector` 和路线
预测代码，并已通过本机 Gradle 构建。真机安装和摄像头运行仍未验证。

拿到测试机后，队友应先安装该 APK，再按 [android/README.md](README.md) 的顺序记录：权限、预览、帧回调、ONNX 检测、反馈执行和连续运行温度。

## 2026-10-04 实时轨迹线候选构建

在 Android 预览层加入了两轮车框、历史接地点轨迹和路面预测线：

- 青色：连续接地点轨迹；
- 紫色：从检测框底部中心外推的短时路面线路；
- 绿/黄/红框：跟踪、预警、明显接近状态。

本机重新执行 `clean test assembleDebug`，结果为 `BUILD SUCCESSFUL`；静态契约检查通过。

- APK：`C:/Users/19770/Documents/Codex/blindnav_external/android_candidate_20261004/blindnav-two-wheeler-overlay-debug.apk`
- APK 大小：98,099,239 bytes
- APK SHA-256：`6174e48dc7ff30ea7f45df880faba75a7326279fd0d97e7093021213c2e426d1`
- 真机安装、相机预览映射、端侧 FPS 和长时间运行仍未验证

## 2026-10-04 路线占用提前提醒构建

按关键帧复核结果，风险引擎和 Android 端均加入“连续占据路线后先提示”的规则：
有骑行者过滤、连续轨迹、路线走廊确认和最小可见面积后，即可先发“可能影响路线”；
之后再根据接近速度升级为“明显接近”。本机重新执行 `clean test assembleDebug`，结果为
`BUILD SUCCESSFUL`，静态契约检查通过。

- APK：`C:/Users/19770/Documents/Codex/blindnav_external/android_candidate_20261004/blindnav-two-wheeler-overlay-route-blocked-debug.apk`
- APK 大小：98,099,239 bytes
- APK SHA-256：`6f93c75ae7f955a96fb62e2f46ec5dd02c49dad7c81dfe778c7528f5934cc84f`
- 真机安装、端侧 FPS 和长时间运行仍未验证

## 2026-10-04 预测性危险提前提醒构建

当前风险规则在“路线已确认被占用”后，继续根据面积增长趋势预测即将进入近距离，
提前升级为危险；本机 `clean test assembleDebug` 和静态契约检查均通过。

- APK：`C:/Users/19770/Documents/Codex/blindnav_external/android_candidate_20261004/blindnav-two-wheeler-overlay-predictive-urgent-debug.apk`
- APK 大小：98,099,239 bytes
- APK SHA-256：`b23e8c5fc83c30bb709306eb12eaebb4e2245e7b2d34b180e029f2532094c3a0`
- 真机安装和端侧实时性能仍未验证

## 2026-10-04 单模型实时路径与端侧后端回退

按手机端初级目标，将实时路径改为单套 `two_wheeler_candidate_320.onnx`：不再在
每帧运行人员模型，停放目标由连续两帧确认、中央路线走廊、接近趋势和两级
风险规则过滤。目标关联增加框重叠优先的轻量匹配，减少同类目标切换 ID。

该模型由原两轮车候选权重导出为 320x320 固定输入，原 640 输入资产保留作
对照；输出仍为未经过 NMS 的 `[1, 8, 2100]` 张量，端侧解码器按动态候选数处理。

ONNX Runtime 现在优先尝试 XNNPACK，再回退到 NNAPI 和 CPU；任一端侧后端不可用时
自动回退，不改变模型候选或正式训练数据。状态栏显示实际选择的后端。这样避免
部分设备接受 NNAPI 图后又静默回退，导致实时速度异常偏慢。

本机重新执行 `gradlew.bat test assembleDebug`，结果：`BUILD SUCCESSFUL`。
当前只完成代码构建和 JVM 测试，未安装新 APK、未重新训练、未启用安全预警。
手机此前实测的旧双模型候选约为 2.6 FPS，新单模型版本需在确认后另行安装测量。

- APK：`android/app/build/outputs/apk/debug/app-debug.apk`
- APK 大小：106,686,175 bytes
- APK SHA-256：`19267EFB1B92F2F7C8D8783AE962294345BB449265654D52DE7AF77BCD6188A8`
- 320 输入模型 SHA-256：`5C65FEE96035E014AAF48E202B2057FD7D365A396ED2875CD10184E9BD168403`
- 当前新构建未安装到手机，需负责人确认后再测试。

## 2026-10-04 实时链路第二轮代码验证

本轮保持单模型和 320 输入不变，补充了：

- CameraX 分析分辨率约束为 480x270，减少手机端 YUV、旋转和缩放开销；
- 预测路线按目标框与中央走廊的相交判断，横向穿入时不只看框中心；
- 跟踪关联加入速度外推、面积突变保护和连续帧校验；
- 同一目标的“注意”重复播报抑制，以及“注意”升级“危险”时立即放行；
- 画面覆盖层直接使用风险引擎的 track id、风险级别和轨迹，避免覆盖层重新分配 ID。

本机重新执行 `gradlew.bat test assembleDebug`，结果：`BUILD SUCCESSFUL`；静态契约检查通过。
新构建仍未安装到手机，未重新训练，也未启用安全预警。

- APK：`android/app/build/outputs/apk/debug/app-debug.apk`
- APK 大小：`106686175` bytes
- APK SHA-256：`FCA3EE4CB20DE154BCC6BC8FFB4C64D0A6847A4C97ECFEB2252E397047602A23`

模型资产离线冒烟检查：ONNX Runtime CPU 成功加载 `[1,3,320,320]` 输入和
`[1,8,2100]` 输出；已知两轮车画面产生 class 1 最高置信度约 `0.668`，
手机当前空场景截图的 class 1 最高约 `0.0034`。这只证明资产和解码链路可运行，
不替代手机端 FPS、温度和道路误报验收。

## 2026-10-05 手机同款模型离线重放

上一段演示误用了桌面 `.pt` 推理和旧 Python 风险规则，提醒帧不能代表手机端。
本轮使用 `two_wheeler_candidate_320.onnx` 的真实逐帧输出，并通过 Android
`RecordedModelReplayTest` 送入与手机相同的 `TemporalRiskEngine`，再渲染演示视频。

- 回放视频：`C:/Users/19770/Documents/Codex/blindnav_external/android320_verified_20261005/android320_route_prediction.mp4`
- 249 帧全部完成模型解码；主接近目标约第 112 帧进入“注意”、第 157 帧进入“危险”；
- 发现并修正了静止目标因框抖动提前触发的问题：接近必须同时满足车框底部向下运动和面积未明显缩小；横向切入增加额外连续观测；
- Android 单元测试、真实 ONNX 输出重放、静态契约检查和 APK 构建均通过。

该视频仍是离线逻辑验证，不是手机 FPS 或道路安全证明；新 APK 仍未安装手机。

## 2026-10-05 相机运动补偿与可信方向

为减少手持手机平移造成的假接近，实时链路加入 96px 灰度背景块的稀疏
前后向匹配。只有纹理、前后向一致性和空间分布同时满足时才采纳背景平移；
否则标记补偿不可用，不凭空外推未来方向。风险引擎用可信补偿修正关联和接地点
历史，语音左右方向仍按目标当前画面方位播报，避免把运动方向当成目标方位。

离线回放使用同一 `two_wheeler_candidate_320.onnx`、Android 解码器和风险引擎，
四段视频均完成逐帧重放；背景补偿可靠帧数分别为 394、171、138、51。
回放视频位于 `C:/Users/19770/Documents/Codex/blindnav_external/android320_motion_20261005/`。

本机 `gradlew.bat test assembleDebug`、相机补偿单元测试和静态契约检查通过；
仍未安装手机，端侧 FPS、温度和真实道路效果仍待负责人确认后验收。

## 2026-10-05 端侧预处理优化构建

本轮只调整端侧执行路径：优先尝试 XNNPACK，摄像头分析目标分辨率改为
`480x270`，保持 `two_wheeler_candidate_320.onnx`、风险阈值和反馈语义不变。
单元测试、Debug 构建和静态契约检查均通过。

- APK：`android/app/build/outputs/apk/debug/app-debug.apk`
- APK 大小：`106726705` bytes
- APK SHA-256：`C128B2ED8FE7BFAF3C485572C25754123449626EFD0E7FE5748EF3C48530E881`
- 尚未安装手机，实际 FPS、端到端延迟和温度仍未验证；安全预警保持关闭。

## 2026-10-05 路线绕行反馈

当中央路线连续两帧被占用、但风险引擎没有判定为迎面接近时，手机和桌面参考状态机
现在会根据左右空间代价给出“注意，向左绕行”或“注意，向右绕行”；两侧都不明确时
仍保持“注意”而不猜方向。迎面接近、相机补偿不可用和路线不确定分支不变。

本轮 Android 单元测试 48 项通过，静态契约检查通过；重新构建后的 APK SHA-256：
`4049C8CE7D70DCC90C2D62F253E2A21670CFEC58E0250B07540BAB010A119EF3`。
真机方向正确性和性能仍待实机验证。

随后对手机同款回放的第 246 帧做了视觉复核：目标虽尚未被风险引擎升级为危险，
但已被路线引路判定为向右绕行，覆盖层现在显示橙色路线提示，不再错误显示绿色普通跟踪。
演示渲染脚本与 Android 覆盖层已同步这一规则。

同一回放的第 112 帧又发现全局“注意”会把路线边缘的停放目标一起染成橙色，
现已改为只给实际风险轨迹、近中央目标或明确绕行目标着色；中央来车保持橙色，
右侧停放目标恢复普通跟踪颜色。最新 APK SHA-256：
`41B414719805E91CEEDAC571DF990144501CBB2354AD63545029181691ACA1B5`。

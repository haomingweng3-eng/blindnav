# 高德步行导航独立验收

入口：首页点“高德步行导航”。此路径不会启动 CameraX 或 ONNX 模型。

## 准备

1. 在高德开放平台申请 **Android** Key，包名填 `com.blindnav.mobile`；将测试用 APK 的 debug 签名 SHA1 填到 Android Key 配置。若换电脑或换签名，请同步更新 SHA1。
2. 在开发电脑的 `~/.gradle/gradle.properties` 写 `AMAP_API_KEY=你的AndroidKey`，或在构建进程设置同名环境变量。不要提交 Key。仓库里没有内置 Key，未配置时应用会提示缺少 Key。
3. 手机开启网络和系统定位，测试时保持应用在前台。路线计算需要联网；手机授予精确位置权限。当前测试只覆盖前台。
4. 打开 `android/` 项目，在 Android Studio 中同步 Gradle；或执行 `./gradlew test assembleDebug`。SDK 使用高德合包依赖（导航、地图、定位、搜索），不再重复引入同类 SDK。

## 验收操作

1. 打开首页“高德步行导航”，输入城市（可空）及目的地关键词。首次搜索会展示包含高德隐私政策链接的同意弹窗。
2. 点击搜索，在候选列表选择**正确的具体地点**，检查标题、城市、地址、POI ID。地铁站有多个出入口时优先搜索具体出入口，不直接用站名替代入口。
3. 点击“开始步行导航”，授予精确定位，观察“获取当前位置 → 步行算路成功 → 实时导航中”。原地等待室外卫星定位；没有定位成功就不得标记算路通过。
4. 走一小段安全路线，记录高德文字播报、手机 TTS、剩余距离变化和偏航重算提示。用另一部手机录屏或 `adb logcat -s AmapWalk:I` 留下时间线。
5. 到达终点，观察高德到达回调；若测试路线较长，不要把中途看到地图上的终点当作到达回调。点击“结束导航”，检查播报和定位是否停止。

## 此版本的边界

- 搜索结果的 POI ID 已保留用于精确地点核对，但当前使用 `calculateWalkRoute(NaviLatLng)` 的**坐标算路**。高德文档标注某些带途经点的 POI 步行算路接口为收费能力，故这里没有假定 POI ID 算路可直接使用。
- 高德判断“到达”只表示到达地图终点附近，不证明找到建筑入口；视觉搜索在下一阶段接入。
- 没有在开发机与真机完成构建和运行以前，状态是“代码已接入，待验收”，不能称为“高德已跑通”。验收至少保留：APK 构建通过、真实 POI 返回、定位成功、步行算路回调、启动导航、语音、距离更新和到达/结束事件。

接口依据：[高德步行算路](https://lbs.amap.com/api/android-navi-sdk/guide/route-plan/ride-route-plan/)、[Android Key 与 SHA1](https://lbs.amap.com/api/navigation-sdk-for-android/guide/create-project/get-key)、[隐私接口](https://lbs.amap.com/api/android-navi-sdk/guide/create-project/configuration-considerations)。

package com.blindnav.mobile

import android.Manifest
import android.app.AlertDialog
import android.content.pm.PackageManager
import android.os.Bundle
import android.text.method.LinkMovementMethod
import android.text.util.Linkify
import android.speech.tts.TextToSpeech
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.ListView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.amap.api.location.AMapLocationClient
import com.amap.api.maps.MapsInitializer
import com.amap.api.navi.AMapNavi
import com.amap.api.navi.NaviSetting
import com.amap.api.navi.enums.NaviType
import com.amap.api.navi.model.AMapCalcRouteResult
import com.amap.api.navi.model.AMapNaviLocation
import com.amap.api.navi.model.NaviInfo
import com.amap.api.navi.model.NaviLatLng
import com.amap.api.services.core.PoiItem
import com.amap.api.services.core.ServiceSettings
import com.amap.api.services.poisearch.PoiResult
import com.amap.api.services.poisearch.PoiSearch
import com.blindnav.mobile.amap.NaviListenerAdapter
import java.util.Locale

/**
 * Independent AMap acceptance screen. GPS routing uses the coordinate-based walking API.
 * POI ID is retained for future entrance-aware routing, but is not sent to that API.
 */
class AmapWalkActivity : ComponentActivity(), PoiSearch.OnPoiSearchListener {
    private lateinit var cityInput: EditText
    private lateinit var keywordInput: EditText
    private lateinit var status: TextView
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var resultsView: ListView

    private var results: List<PoiItem> = emptyList()
    private var destination: PoiItem? = null
    private var navi: AMapNavi? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var routeRequested = false
    private var navigationStarted = false
    private var active = false
    private var lastInstruction = ""

    private val locationPermission = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { granted ->
        if (granted[Manifest.permission.ACCESS_FINE_LOCATION] == true) {
            beginWalkingRoute()
        } else {
            showStatus("步行导航需要精确定位权限；请授权后重试。")
        }
    }

    private val listener = object : NaviListenerAdapter() {
        override fun onInitNaviFailure() = onUi { showStatus("高德导航引擎初始化失败。") }

        override fun onLocationChange(location: AMapNaviLocation) {
            if (!active || routeRequested || destination == null || location.coord == null) return
            routeRequested = true
            val point = destination?.latLonPoint ?: return
            val accepted = navi?.calculateWalkRoute(NaviLatLng(point.latitude, point.longitude)) == true
            onUi {
                showStatus(
                    if (accepted) "已收到定位，正在规划到「${destination?.title}」的步行路线…"
                    else "高德未接受步行算路请求，请检查网络及终点。",
                )
            }
        }

        override fun onCalculateRouteSuccess(routeResult: AMapCalcRouteResult) {
            onUi {
                if (!active) return@onUi
                if (!navigationStarted) {
                    val started = navi?.startNavi(NaviType.GPS) == true
                    navigationStarted = started
                    stopButton.isEnabled = started
                    showStatus(
                        if (started) "步行路线已规划，正在启动实时导航：${destination?.title}"
                        else "路线已规划，但实时导航未启动。",
                    )
                } else {
                    showStatus("已更新步行路线，继续导航：${destination?.title}")
                }
            }
        }

        override fun onCalculateRouteFailure(routeResult: AMapCalcRouteResult) = onUi {
            showStatus("步行算路失败：错误码 ${routeResult.errorCode}。请核对高德 Key、网络和目的地。")
        }

        override fun onStartNavi(type: Int) = onUi { showStatus("实时步行导航中：${destination?.title}") }

        override fun onGetNavigationText(type: Int, text: String) = onUi {
            if (active && text.isNotBlank() && text != lastInstruction) {
                lastInstruction = text
                showStatus("高德播报：$text")
                if (ttsReady) tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "amap-walk")
            }
        }

        override fun onNaviInfoUpdate(info: NaviInfo) = onUi {
            if (active && navigationStarted) {
                status.text = "步行导航中 · 剩余 ${info.pathRetainDistance} 米\n" +
                    "下一步 ${info.curStepRetainDistance} 米 · ${info.nextRoadName.orEmpty()}\n" +
                    "最近播报：$lastInstruction"
            }
        }

        override fun onGpsSignalWeak(weak: Boolean) {
            if (weak) onUi { showStatus("GPS 信号较弱，请核对当前位置。") }
        }

        override fun onReCalculateRouteForYaw() = onUi { showStatus("已偏离路线，高德正在重新算路…") }

        override fun onArriveDestination() = onUi {
            showStatus("高德判定已到目的地附近：${destination?.title}。具体入口仍需视觉确认。")
            if (ttsReady) tts?.speak("已到目的地附近，请确认具体入口", TextToSpeech.QUEUE_FLUSH, null, "amap-arrival")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_amap_walk)
        cityInput = findViewById(R.id.amap_city)
        keywordInput = findViewById(R.id.amap_keyword)
        resultsView = findViewById(R.id.amap_results)
        startButton = findViewById(R.id.amap_start)
        stopButton = findViewById(R.id.amap_stop)
        status = findViewById(R.id.amap_status)

        tts = TextToSpeech(this) { code ->
            ttsReady = code == TextToSpeech.SUCCESS &&
                tts?.setLanguage(Locale.SIMPLIFIED_CHINESE)?.let {
                    it != TextToSpeech.LANG_MISSING_DATA && it != TextToSpeech.LANG_NOT_SUPPORTED
                } == true
            if (!ttsReady) onUi { showStatus("系统中文语音不可用，请安装中文 TTS 语音包。") }
        }
        findViewById<Button>(R.id.amap_search).setOnClickListener { searchWithConsent() }
        startButton.setOnClickListener { requestLocationAndStart() }
        stopButton.setOnClickListener { stopWalkingRoute() }
        resultsView.setOnItemClickListener { _, _, index, _ ->
            destination = results.getOrNull(index)
            startButton.isEnabled = destination != null
            showStatus("已选终点：${destination?.title}（POI ID: ${destination?.poiId}）")
        }
        if (!hasKey()) showStatus("缺少高德 Android Key。请按 android/AMAP_WALK_SETUP.md 配置。")
    }

    private fun hasKey(): Boolean {
        val app = packageManager.getApplicationInfo(packageName, PackageManager.GET_META_DATA)
        return !app.metaData?.getString("com.amap.api.v2.apikey").isNullOrBlank()
    }

    private fun searchWithConsent() {
        if (!hasKey()) {
            showStatus("缺少高德 Android Key，无法搜索。")
            return
        }
        if (keywordInput.text.toString().trim().isBlank()) {
            showStatus("请先输入目的地名称。")
            return
        }
        if (getPreferences(MODE_PRIVATE).getBoolean("amap_privacy_agreed", false)) {
            applyAmapPrivacyConsent()
            searchPoi()
            return
        }
        val dialog = AlertDialog.Builder(this)
            .setTitle("使用高德搜索和步行导航")
            .setMessage(
                "搜索、定位和步行算路需要向高德提供地点与位置信息。请阅读高德开放平台隐私政策：" +
                    "https://lbs.amap.com/pages/privacy/ 。同意后才能启动高德 SDK。",
            )
            .setNegativeButton("取消", null)
            .setPositiveButton("已阅读并同意") { _, _ ->
                getPreferences(MODE_PRIVATE).edit().putBoolean("amap_privacy_agreed", true).apply()
                applyAmapPrivacyConsent()
                searchPoi()
            }
            .create()
        dialog.show()
        dialog.findViewById<TextView>(android.R.id.message)?.apply {
            autoLinkMask = Linkify.WEB_URLS
            movementMethod = LinkMovementMethod.getInstance()
        }
    }

    private fun applyAmapPrivacyConsent() {
        MapsInitializer.updatePrivacyShow(this, true, true)
        MapsInitializer.updatePrivacyAgree(this, true)
        ServiceSettings.updatePrivacyShow(this, true, true)
        ServiceSettings.updatePrivacyAgree(this, true)
        AMapLocationClient.updatePrivacyShow(this, true, true)
        AMapLocationClient.updatePrivacyAgree(this, true)
        NaviSetting.updatePrivacyShow(this, true, true)
        NaviSetting.updatePrivacyAgree(this, true)
    }

    private fun searchPoi() {
        destination = null
        results = emptyList()
        startButton.isEnabled = false
        resultsView.adapter = null
        val query = PoiSearch.Query(
            keywordInput.text.toString().trim(), "", cityInput.text.toString().trim(),
        ).apply { pageSize = 10 }
        try {
            PoiSearch(this, query).apply {
                setOnPoiSearchListener(this@AmapWalkActivity)
                searchPOIAsyn()
            }
            showStatus("正在搜索目的地…")
        } catch (error: Exception) {
            showStatus("高德搜索启动失败：${error.message}")
        }
    }

    override fun onPoiSearched(result: PoiResult?, errorCode: Int) = onUi {
        if (errorCode != 1000 || result == null) {
            showStatus("高德搜索失败：错误码 $errorCode。请检查 Key、网络和城市。")
            return@onUi
        }
        results = result.pois.filter { it.latLonPoint != null }
        resultsView.adapter = ArrayAdapter(
            this, android.R.layout.simple_list_item_1,
            results.map { "${it.title} · ${it.cityName} ${it.snippet} · ${it.poiId}" },
        )
        showStatus(if (results.isEmpty()) "没有找到带坐标的目的地。" else "找到 ${results.size} 个结果，请选择准确终点。")
    }

    override fun onPoiItemSearched(item: PoiItem?, errorCode: Int) = Unit

    private fun requestLocationAndStart() {
        if (destination == null) return
        if (!getPreferences(MODE_PRIVATE).getBoolean("amap_privacy_agreed", false)) {
            showStatus("请先同意高德隐私政策并搜索目的地。")
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            beginWalkingRoute()
        } else {
            locationPermission.launch(arrayOf(
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            ))
        }
    }

    private fun beginWalkingRoute() {
        if (active || destination == null) return
        try {
            applyAmapPrivacyConsent()
            val engine = AMapNavi.getInstance(applicationContext)
            navi = engine
            engine.addAMapNaviListener(listener)
            engine.setUseInnerVoice(false, true)
            active = true
            routeRequested = false
            navigationStarted = false
            lastInstruction = ""
            stopButton.isEnabled = true
            if (engine.startGPS()) {
                showStatus("正在获取当前位置，定位成功后规划步行路线…")
            } else {
                stopWalkingRoute()
                showStatus("高德 GPS 未启动。请检查定位开关与权限。")
            }
        } catch (error: Exception) {
            stopWalkingRoute()
            showStatus("高德导航启动失败：${error.message}")
        }
    }

    private fun stopWalkingRoute() {
        active = false
        routeRequested = false
        navigationStarted = false
        navi?.let { engine ->
            engine.removeAMapNaviListener(listener)
            engine.stopNavi()
            engine.stopGPS()
            AMapNavi.destroy()
        }
        navi = null
        tts?.stop()
        stopButton.isEnabled = false
        showStatus("已结束高德步行导航。")
    }

    override fun onDestroy() {
        stopWalkingRoute()
        tts?.shutdown()
        tts = null
        super.onDestroy()
    }

    private fun onUi(block: () -> Unit) = runOnUiThread(block)
    private fun showStatus(message: String) {
        status.text = message
        android.util.Log.i("AmapWalk", message)
    }
}

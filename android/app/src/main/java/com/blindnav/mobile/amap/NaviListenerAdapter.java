package com.blindnav.mobile.amap;

import com.amap.api.navi.AMapNaviListener;
import com.amap.api.navi.model.AMapCalcRouteResult;
import com.amap.api.navi.model.AMapLaneInfo;
import com.amap.api.navi.model.AMapModelCross;
import com.amap.api.navi.model.AMapNaviCameraInfo;
import com.amap.api.navi.model.AMapNaviCross;
import com.amap.api.navi.model.AMapNaviLocation;
import com.amap.api.navi.model.AMapNaviRouteNotifyData;
import com.amap.api.navi.model.AMapNaviTrafficFacilityInfo;
import com.amap.api.navi.model.AMapServiceAreaInfo;
import com.amap.api.navi.model.AimLessModeCongestionInfo;
import com.amap.api.navi.model.AimLessModeStat;
import com.amap.api.navi.model.NaviInfo;

/** Empty implementation so the walking screen only overrides events it uses. */
public class NaviListenerAdapter implements AMapNaviListener {
    @Override public void onInitNaviFailure() {}
    @Override public void onInitNaviSuccess() {}
    @Override public void onStartNavi(int type) {}
    @Override public void onTrafficStatusUpdate() {}
    @Override public void onLocationChange(AMapNaviLocation location) {}
    @Override public void onGetNavigationText(int type, String text) {}
    @Override public void onGetNavigationText(String text) {}
    @Override public void onEndEmulatorNavi() {}
    @Override public void onArriveDestination() {}
    @Override public void onCalculateRouteSuccess(AMapCalcRouteResult result) {}
    @Override public void onCalculateRouteSuccess(int[] routeIds) {}
    @Override public void onCalculateRouteFailure(AMapCalcRouteResult result) {}
    @Override public void onCalculateRouteFailure(int errorInfo) {}
    @Override public void onReCalculateRouteForYaw() {}
    @Override public void onReCalculateRouteForTrafficJam() {}
    @Override public void onArrivedWayPoint(int wayId) {}
    @Override public void onGpsOpenStatus(boolean enabled) {}
    @Override public void onGpsSignalWeak(boolean weak) {}
    @Override public void onNaviInfoUpdate(NaviInfo info) {}
    @Override public void onNaviRouteNotify(AMapNaviRouteNotifyData data) {}
    @Override public void updateCameraInfo(AMapNaviCameraInfo[] infos) {}
    @Override public void updateIntervalCameraInfo(AMapNaviCameraInfo start, AMapNaviCameraInfo end, int status) {}
    @Override public void onServiceAreaUpdate(AMapServiceAreaInfo[] infos) {}
    @Override public void OnUpdateTrafficFacility(AMapNaviTrafficFacilityInfo info) {}
    @Override public void OnUpdateTrafficFacility(AMapNaviTrafficFacilityInfo[] infos) {}
    @Override public void showCross(AMapNaviCross cross) {}
    @Override public void hideCross() {}
    @Override public void showModeCross(AMapModelCross cross) {}
    @Override public void hideModeCross() {}
    @Override public void showLaneInfo(AMapLaneInfo lane) {}
    @Override public void showLaneInfo(AMapLaneInfo[] lanes, byte[] background, byte[] recommended) {}
    @Override public void hideLaneInfo() {}
    @Override public void notifyParallelRoad(int type) {}
    @Override public void updateAimlessModeStatistics(AimLessModeStat stats) {}
    @Override public void updateAimlessModeCongestionInfo(AimLessModeCongestionInfo congestion) {}
    @Override public void onPlayRing(int type) {}
}

# -*- coding: utf-8 -*-
"""
build_map_asset.py —— 生成离线可用的标准中国地图资源
=====================================================
作用：把符合国家标准的中国行政区划 GeoJSON 转成
      assets/maps/china_std.js（内容为 echarts.registerMap('china', {...})），
      使大屏在**完全离线**的情况下也能渲染中国地图。

地图规范（重要）：
  · 底图采用国家标准行政区划数据，包含 34 个省级行政区
    （含台湾省、香港特别行政区、澳门特别行政区）
    以及 adcode=100000_JD 的南海诸岛九段线要素；
  · 全程不使用任何在线地图瓦片服务（Google / OSM / Mapbox 等），
    不内嵌任何地图 API Key；
  · 本项目统计口径为 31 个省级行政区，港澳台以"暂无数据"中性色显示，
    但在地图上仍作为中国领土完整绘制。

运行：python src/build_map_asset.py
      （仅在资源缺失时执行一次，生成后大屏即可永久离线运行）
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

# 标准行政区划 GeoJSON 数据源
GEOJSON_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"
# 本地缓存的原始 GeoJSON（随项目提供，网络不可用时直接复用）
LOCAL_CACHE = os.path.join(cfg.ASSETS_DIR, "maps", "china_full.json")


def load_geojson() -> dict:
    """优先读取本地缓存，没有则联网下载并缓存。"""
    if os.path.exists(LOCAL_CACHE) and os.path.getsize(LOCAL_CACHE) > 10240:
        print(f"[读取] 本地缓存 {os.path.basename(LOCAL_CACHE)}")
        with open(LOCAL_CACHE, encoding="utf-8") as f:
            return json.load(f)

    print(f"[下载] {GEOJSON_URL}")
    try:
        import urllib.request
        with urllib.request.urlopen(GEOJSON_URL, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:                       # noqa: BLE001
        raise SystemExit(
            f"下载失败：{exc}\n"
            f"请联网后重试，或手动下载该 GeoJSON 保存为：{LOCAL_CACHE}"
        ) from exc

    with open(LOCAL_CACHE, "w", encoding="utf-8") as f:
        f.write(raw)
    return json.loads(raw)


def build() -> str:
    geo = load_geojson()
    features = geo.get("features", [])

    # ------------------------------------------------------------------
    # ⚠️ 兼容性修复（必读）：
    #   标准边界 GeoJSON 中"南海诸岛九段线"要素的 properties.name 是**空字符串**。
    #   当它配合 nameMap 一起交给 ECharts 渲染时，空名称会让 ECharts 生成一个
    #   多余的矩形图斑（表现为台湾以东海面上凭空多出一个方框），属于渲染瑕疵。
    #   这里为该要素补一个正式名称，既消除瑕疵，又让悬浮提示可读。
    # ------------------------------------------------------------------
    jd_fixed = 0
    for f in features:
        props = f.setdefault("properties", {})
        if not props.get("name"):
            props["name"] = "南海诸岛"
            jd_fixed += 1
    if jd_fixed:
        print(f"[修复] 为 {jd_fixed} 个无名要素补充名称「南海诸岛」（消除空名称渲染瑕疵）")

    names = [f["properties"].get("name") or "(九段线/南海诸岛)"
             for f in features]
    print(f"[校验] 要素数量 {len(features)}")
    print(f"       行政区划：{len([n for n in names if n != '南海诸岛'])} 个")
    for key in ("台湾省", "香港特别行政区", "澳门特别行政区"):
        print(f"       {key}：{'✓ 已包含' if key in names else '✗ 缺失'}")
    print(f"       九段线/南海诸岛要素：{'✓ 已包含' if '南海诸岛' in names else '✗ 缺失'}")

    os.makedirs(os.path.dirname(cfg.MAP_ASSET), exist_ok=True)
    with open(cfg.MAP_ASSET, "w", encoding="utf-8") as f:
        f.write("/* 符合国家标准的中国地图（含南海诸岛九段线），离线注册 */\n")
        f.write("(function(){var geo=")
        json.dump(geo, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";if(typeof echarts!=='undefined'){echarts.registerMap('china',geo);}"
                "else{window.__CHINA_GEO__=geo;}})();\n")

    size_mb = os.path.getsize(cfg.MAP_ASSET) / 1024 / 1024
    print(f"\n[完成] {cfg.MAP_ASSET}（{size_mb:.2f} MB）")
    print("       大屏将直接以 <script src=\"assets/maps/china_std.js\"> 离线加载")
    return cfg.MAP_ASSET


if __name__ == "__main__":
    build()

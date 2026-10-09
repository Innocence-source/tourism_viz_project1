# -*- coding: utf-8 -*-
"""
config.py —— 项目全局配置
=========================
统一管理：目录路径、中文字体、配色方案、Pyecharts 离线资源。

⚠️ 需要调整的参数都集中在这里，改一处即可全局生效。
"""

from __future__ import annotations

import os
import sys

# ----------------------------------------------------------------------------
# 1. 目录路径
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")            # 原始 & 清洗后 csv
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")        # 全部输出
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")           # 静态分析图 png
CLUSTER_DIR = os.path.join(OUTPUT_DIR, "cluster")        # 聚类结果
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")        # echarts 离线 js
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

DASHBOARD_HTML = os.path.join(OUTPUT_DIR, "全国旅游业发展可视化分析大屏.html")

for _d in (DATA_DIR, OUTPUT_DIR, CHART_DIR, CLUSTER_DIR, ASSETS_DIR, DOCS_DIR):
    os.makedirs(_d, exist_ok=True)

# ----------------------------------------------------------------------------
# 2. 可调参数（论文中如需说明"参数设置"就引用这里）
# ----------------------------------------------------------------------------
RANDOM_SEED = 42            # 随机种子，保证结果可复现

IQR_K = 3.0                 # IQR 异常值检测倍数阈值。
                            # 说明：教科书默认 k=1.5，但本数据集含疫情年份的"真实低谷"
                            # （如 2022 国庆、2020 湖北），k=1.5 会把它们误判成异常。
                            # 因此采用 k=3.0 只捕获"极端异常"（量级错误/哨兵值/符号错误）。
ZSCORE_TH = 3.0             # Z-Score 异常值检测阈值（|z| > 3 判为异常）

KMEANS_K_RANGE = range(2, 9)   # 肘部法则搜索的 K 取值范围 2—8（全部指标都会打印）
# —— 最终 K 的"有效选择区间" ——
# 说明：K=2 时聚类退化为"强/弱"二分，无法支撑论文 4.2.5 的"发展等级划分"；
#       K>6 时类别过于细碎、单类样本过少，缺乏政策解释力。
#       因此把 K 的候选区间限定为 [3, 6]，再在此区间内按综合评分择优。
KMEANS_K_MIN = 3
KMEANS_K_MAX = 6
# 综合评分的权重（轮廓系数 / CH 指数 / 1-DB 指数），三者权重之和建议为 1
KMEANS_SCORE_WEIGHTS = (0.5, 0.25, 0.25)
KMEANS_K = None                # None = 自动择优；也可写死 3 / 4 / 5 / 6
KMEANS_N_INIT = 10             # KMeans 重复初始化次数（取最优）
KMEANS_MAX_ITER = 300          # 单次迭代上限

ANALYSIS_YEAR = 2024        # 聚类 / 排名 / 城市 TOP 分析所采用的截面年份
TOP_N_CITY = 10             # 热门城市模块展示的城市数
TOP_N_PROVINCE = 15         # 动态排名条形图展示的省份数

# ----------------------------------------------------------------------------
# 3. 中文字体（Matplotlib / Seaborn）
# ----------------------------------------------------------------------------
CN_FONT_CANDIDATES = [
    "Microsoft YaHei",   # 微软雅黑（Windows 首选）
    "SimHei",            # 黑体
    "Source Han Sans CN",
    "Noto Sans CJK SC",
    "WenQuanYi Zen Hei",
    "PingFang SC",
    "Arial Unicode MS",
]

_MPL_READY = False


def setup_matplotlib_chinese(verbose: bool = True) -> str:
    """配置 matplotlib 中文字体，返回实际生效的字体名。"""
    global _MPL_READY
    import matplotlib
    import matplotlib.font_manager as fm
    from matplotlib import rcParams

    available = {f.name for f in fm.fontManager.ttflist}
    chosen = next((f for f in CN_FONT_CANDIDATES if f in available), "DejaVu Sans")

    rcParams["font.sans-serif"] = [chosen] + CN_FONT_CANDIDATES
    rcParams["axes.unicode_minus"] = False     # 负号正常显示
    rcParams["font.size"] = 11
    rcParams["figure.dpi"] = 110
    rcParams["savefig.dpi"] = 150
    rcParams["axes.edgecolor"] = "#666666"
    rcParams["axes.linewidth"] = 0.8
    rcParams["figure.facecolor"] = "white"
    rcParams["axes.facecolor"] = "white"

    if verbose:
        if chosen == "DejaVu Sans":
            print("[警告] 未找到中文字体，图表中文可能显示为方块；"
                  "可在 config.py 的 CN_FONT_CANDIDATES 中补充本机字体。")
        else:
            print(f"[字体] Matplotlib 中文字体已设置为：{chosen}")
    _MPL_READY = True
    return chosen


# ----------------------------------------------------------------------------
# 4. 配色方案（静态图 + 大屏共用）
# ----------------------------------------------------------------------------
# 东中西部区域配色（论文中区域对比图固定使用）
REGION_COLORS = {"东部": "#E4572E", "中部": "#17BEBB", "西部": "#3D5A80"}

# 静态图顺序色板
PALETTE = ["#2E86AB", "#E4572E", "#17BEBB", "#FFC914", "#76B041",
           "#8E6C8A", "#D64550", "#4C9F70"]

# 大屏深色主题配色
DARK = {
    "bg": "#0B1B33",            # 大屏主背景（深蓝）
    "panel": "#112A4A",         # 面板背景
    "panel_border": "#1E4B7A",  # 面板描边
    "text": "#E8F1FF",          # 主文字
    "text_sub": "#8FB8E0",      # 次要文字
    "accent": "#22D3EE",        # 强调色（青）
    "accent2": "#FFC53D",       # 强调色（金）
    "accent3": "#FF6B6B",       # 强调色（红）
    "grid": "rgba(120,180,255,0.15)",
    "map_low": "#0E3A5F",
    "map_high": "#FFD166",
}


# ----------------------------------------------------------------------------
# 4.5 中国地图规范
# ----------------------------------------------------------------------------
# 地图规范说明（重要）：
#   本项目大屏使用**符合国家标准的中国地图**作为底图，数据来源为标准行政区划
#   GeoJSON（含 34 个省级行政区 + adcode=100000_JD 的南海诸岛九段线要素）。
#   底图以本地 js 形式加载（echarts.registerMap('china', ...)），不依赖任何
#   在线地图瓦片服务，也不含任何地图 API Key。
#   港澳台在中国地图中作为中国的一部分参与绘制（本项目统计口径为 31 个
#   省级行政区，港澳台无对应统计数据，故以"暂无数据"中性色显示）。
MAP_NAME = "china"
MAP_ASSET = os.path.join(ASSETS_DIR, "maps", "china_std.js")

# 省级行政区"简称 → 标准全称"，用于把统计数据的简称对齐到标准地图名称
PROVINCE_MAP_NAME = {
    "北京": "北京市", "天津": "天津市", "河北": "河北省", "山西": "山西省",
    "内蒙古": "内蒙古自治区", "辽宁": "辽宁省", "吉林": "吉林省", "黑龙江": "黑龙江省",
    "上海": "上海市", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "广西": "广西壮族自治区",
    "海南": "海南省", "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
    "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省", "甘肃": "甘肃省",
    "青海": "青海省", "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
}


# ----------------------------------------------------------------------------
# 5. Pyecharts 离线资源
# ----------------------------------------------------------------------------
def setup_pyecharts_offline() -> None:
    """让 pyecharts 引用本地 assets 目录的 js，实现完全离线渲染。"""
    from pyecharts.globals import CurrentConfig

    # 指向本地 assets 目录（注意结尾必须带 "/"）
    CurrentConfig.ONLINE_HOST = ASSETS_DIR.replace(os.sep, "/") + "/"


def ensure_assets(verbose: bool = True) -> bool:
    """检查 echarts.min.js / maps/china_std.js 是否就绪（缺失时给出生成方式）。"""
    need = {
        "echarts.min.js": ("https://assets.pyecharts.org/assets/v5/echarts.min.js",
                           "curl -L -o \"{path}\" {url}"),
        os.path.join("maps", "china_std.js"): (
            "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json",
            "python src/build_map_asset.py   # 自动下载 GeoJSON 并生成离线 js"),
    }
    ok = True
    for rel, (url, how) in need.items():
        path = os.path.join(ASSETS_DIR, rel)
        if not os.path.exists(path) or os.path.getsize(path) < 1024:
            ok = False
            if verbose:
                print(f"[缺失] assets/{rel.replace(os.sep, '/')}\n"
                      f"        生成方式：{how.format(path=path, url=url)}")
    if ok and verbose:
        print("[资源] 离线资源就绪：assets/echarts.min.js、assets/maps/china_std.js")
    return ok

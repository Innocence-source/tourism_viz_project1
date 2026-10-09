# -*- coding: utf-8 -*-
"""
04_dashboard.py —— 模块4：交互式可视化大屏（核心）
==================================================
对应论文第 5 章「旅游数据可视化大屏设计与实现」。

技术方案：
  · 图表全部由 Pyecharts 生成（Bar / Map / Line / Timeline / Pie）；
  · 由本脚本用一套自定义深色大屏 HTML 骨架拼装成单页大屏，
    骨架负责布局、配色、指标卡片，Pyecharts 负责图表本体；
  · ECharts 与 China 地图 JSON 均为**本地 assets 文件**，
    不依赖任何 CDN，断网双击 HTML 即可正常显示。

大屏六个功能子模块（对应 5.2）：
  ① 旅游总览模块      —— 核心指标卡片（总收入 / 总人次 / 同比增长率 / 占GDP比重）
  ② 全国热力地图模块  —— 分级着色地图，悬浮查看省份旅游收入与游客量
  ③ 趋势分析模块      —— 双轴折线，旅游收入 + 游客量，标注疫情前后区间
  ④ 省份排名动态模块  —— Timeline 动态排序条形图，逐年演示省份排名变化
  ⑤ 节假日对比模块    —— 春节 / 五一 / 国庆 旅游收入分组柱状图
  ⑥ 热门城市模块      —— TOP10 热门旅游城市收入条形图
  （附加）聚类结果模块 —— K-Means 四梯队省份构成，与论文 4.2.5 呼应

输出：output/全国旅游业发展可视化分析大屏.html（含 output/assets/ 离线资源）
运行：python src/04_dashboard.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

cfg.setup_pyecharts_offline()
from pyecharts import options as opts                        # noqa: E402
from pyecharts.charts import Bar, Line, Map, Pie, Timeline    # noqa: E402
from pyecharts.commons.utils import JsCode                   # noqa: E402
from pyecharts.globals import ThemeType                      # noqa: E402

D = cfg.DARK
YEAR = cfg.ANALYSIS_YEAR

# 条形图渐变：青蓝（城市） / 金色（省份排名）
GRAD_CYAN = ("new echarts.graphic.LinearGradient(0,0,1,0,"
             "[{offset:0,color:'#155E8C'},{offset:1,color:'#22D3EE'}])")
GRAD_GOLD = ("new echarts.graphic.LinearGradient(0,0,1,0,"
             "[{offset:0,color:'#A9740A'},{offset:1,color:'#FFD166'}])")

TIP = dict(background_color="rgba(9,26,48,0.95)", border_color=D["panel_border"],
           textstyle_opts=opts.TextStyleOpts(color=D["text"], font_size=12))


# ============================================================================
# 通用工具
# ============================================================================
def init_opts(height: str) -> opts.InitOpts:
    """统一的深色主题初始化；透明背景让大屏面板渐变透出来。"""
    return opts.InitOpts(theme=ThemeType.DARK, width="100%", height=height,
                         bg_color="transparent")


def embed(chart) -> str:
    """把 Pyecharts 图表渲染成可嵌入大屏骨架的 HTML 片段（div + 初始化脚本）。

    做法：调用 render_embed() 拿到完整 HTML，再抽取
      · <div class="chart-container">  （图表挂载点）
      · 非 src 的 <script> 块          （echarts.init + option + setOption）
    这样既能复用 Pyecharts 生成 option 的能力，又能自由控制外层布局，
    同时彻底摆脱它对 CDN 的依赖（echarts 由骨架统一用本地文件引入）。
    """
    html = chart.render_embed()
    div = re.search(r'<div[^>]*class="chart-container"[^>]*>\s*</div>', html)
    scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
    if not div or not scripts:
        raise RuntimeError("Pyecharts 渲染片段解析失败，请确认 pyecharts 版本为 2.x")
    return div.group(0) + "\n<script>" + scripts[-1] + "</script>"


def patch(chart, **option_patch):
    """原生 ECharts option 补丁（Pyecharts 未封装的字段，如 grid / color）。"""
    chart.options.update(option_patch)
    return chart


def tip_opts(trigger="item", **kw):
    return opts.TooltipOpts(trigger=trigger, **{**TIP, **kw})


# ============================================================================
# ① 旅游总览模块 —— 核心指标卡片（纯 HTML，由 build_html 注入）
# ============================================================================
def build_kpi(nat: pd.DataFrame) -> dict:
    """从全国年度表计算核心指标、同比增长率与疫情恢复程度。"""
    cur = nat[nat["年份"] == YEAR].iloc[0]
    prev = nat[nat["年份"] == YEAR - 1].iloc[0]
    base = nat[nat["年份"] == 2019].iloc[0]          # 2019 = 疫情前峰值基准年
    rev, rev_p = float(cur["全国旅游总收入_亿元"]), float(prev["全国旅游总收入_亿元"])
    tou, tou_p = float(cur["国内游客总人次_亿人次"]), float(prev["国内游客总人次_亿人次"])
    return {
        "year": YEAR,
        "rev": rev,
        "rev_text": f"{rev / 10000:.2f}",
        "rev_unit": "万亿元",
        "rev_yoy": (rev / rev_p - 1) * 100,
        "tou": tou,
        "tou_text": f"{tou:.2f}",
        "tou_unit": "亿人次",
        "tou_yoy": (tou / tou_p - 1) * 100,
        "ratio": float(cur["旅游收入占GDP比重_%"]),
        # 相对 2019 年（疫前峰值）的恢复程度
        "recover": rev / float(base["全国旅游总收入_亿元"]) * 100,
        "recover_tou": tou / float(base["国内游客总人次_亿人次"]) * 100,
    }


def kpi_html(k: dict) -> str:
    """生成 4 张关键数字卡片（同比上涨=红、下跌=绿，符合国内惯例）。"""
    def card(label, value, unit, yoy=None, accent=D["accent"], icon="◆"):
        yoy_html = ""
        if yoy is not None:
            cls = "up" if yoy >= 0 else "down"
            arrow = "▲" if yoy >= 0 else "▼"
            yoy_html = (f'<div class="kpi-yoy {cls}">{arrow} 同比增长 '
                        f'{abs(yoy):.2f}%</div>')
        return f"""
        <div class="kpi-card" style="--accent:{accent}">
          <div class="kpi-label"><span class="kpi-dot">{icon}</span>{label}</div>
          <div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>
          {yoy_html}
        </div>"""

    cards = [
        card(f"{k['year']} 年全国旅游总收入", k["rev_text"], k["rev_unit"],
             k["rev_yoy"], D["accent"]),
        card(f"{k['year']} 年国内游客总人次", k["tou_text"], k["tou_unit"],
             k["tou_yoy"], D["accent2"]),
        card("旅游收入占 GDP 比重", f"{k['ratio']:.2f}", "%", None, D["accent3"]),
        card("较 2019 年（疫前峰值）恢复", f"{k['recover']:.1f}", "%", None, "#7DD3FC"),
    ]
    return '<div class="kpi-grid">' + "".join(cards) + "</div>"


# ============================================================================
# ② 全国地理热力地图模块
# ============================================================================
def chart_map(mrg: pd.DataFrame) -> str:
    """分级着色中国地图；悬浮显示省份旅游收入、接待游客量、所属区域与全国占比。

    地图规范：底图由 assets/maps/china_std.js 离线注册（国家标准行政区划，
    含台湾省、香港/澳门特别行政区与南海诸岛九段线要素），不使用在线瓦片服务。
    统计数据使用的是省份简称，这里通过 name_map 对齐到标准地图全称。
    """
    d = mrg[mrg["年份"] == YEAR].sort_values("省份旅游收入_亿元", ascending=False)
    total = float(d["省份旅游收入_亿元"].sum())
    nm = cfg.PROVINCE_MAP_NAME

    data_pair, lut = [], {}
    for _, r in d.iterrows():
        full = nm.get(r["省份"], r["省份"])
        data_pair.append((full, round(float(r["省份旅游收入_亿元"]), 1)))
        lut[full] = {"short": r["省份"],
                     "rev": round(float(r["省份旅游收入_亿元"]), 1),
                     "tou": round(float(r["接待游客数量_万人次"]), 1),
                     "region": r["所属区域"],
                     "pct": round(float(r["省份旅游收入_亿元"] / total * 100), 2)}

    tooltip_js = JsCode("""
    function (p) {
        var d = window.__PROV__[p.name];
        if (!d) { return '<b style="font-size:14px">' + p.name + '</b><br/>'
                        + '<span style="color:#8FB8E0">暂无统计数据</span>'; }
        return '<div style="font-size:14px;font-weight:700;margin-bottom:5px">'
             + d.short + '<span style="font-size:11px;color:#8FB8E0">（' + d.region + '）</span></div>'
             + '旅游总收入：<b style="color:#FFD166">' + d.rev.toLocaleString() + '</b> 亿元<br/>'
             + '接待游客量：<b style="color:#22D3EE">' + d.tou.toLocaleString() + '</b> 万人次<br/>'
             + '全国占比：<b style="color:#FF8A80">' + d.pct + '%</b>';
    }""")

    # 地图面板满高：924（= 网格可用高度），876 = 924 - 48，使地图宽度最大化
    m = Map(init_opts=init_opts("876px"))
    m.add(series_name="旅游总收入（亿元）", data_pair=data_pair,
          maptype=cfg.MAP_NAME, name_map=nm,
          is_map_symbol_show=False, zoom=1.0,
          label_opts=opts.LabelOpts(is_show=False),
          # 无统计数据的地区（港澳台）与九段线用中性色，仅作领土完整绘制
          itemstyle_opts=opts.ItemStyleOpts(area_color="rgba(52,92,134,0.38)",
                                            border_color="rgba(150,205,255,0.5)",
                                            border_width=0.8),
          emphasis_itemstyle_opts=opts.ItemStyleOpts(area_color="#FFC53D",
                                                    border_color="#FFFFFF", border_width=1.4),
          emphasis_label_opts=opts.LabelOpts(is_show=True, color="#FFFFFF", font_size=12))
    m.set_global_opts(
        tooltip_opts=tip_opts("item", formatter=tooltip_js),
        visualmap_opts=opts.VisualMapOpts(
            min_=0, max_=float(d["省份旅游收入_亿元"].max()),
            range_color=["#0E3A5F", "#17618F", "#2E9FC4", "#8FD3C7", "#FFD166", "#FF9F1C"],
            is_piecewise=False, pos_left="3%", pos_bottom="4%",
            item_width=13, item_height=105,
            textstyle_opts=opts.TextStyleOpts(color=D["text_sub"], font_size=10)),
    )
    # 强制地图铺满面板：layoutCenter + layoutSize 比 zoom 更可控，
    # zoom 会以包围盒中心为基准放大，容易把南海诸岛九段线裁出画布。
    m.options["series"][0]["layoutCenter"] = ["50%", "52%"]
    m.options["series"][0]["layoutSize"] = "100%"
    return {"html": embed(m), "lut": lut}
    return pdf


# ============================================================================
# ③ 趋势分析模块
# ============================================================================
def chart_trend(nat: pd.DataFrame) -> str:
    """旅游收入（左轴，亿元）+ 国内游客量（右轴，亿人次）双轴折线，标注疫情区间。"""
    x = [str(y) for y in nat["年份"]]
    rev = [round(float(v), 1) for v in nat["全国旅游总收入_亿元"]]
    tou = [round(float(v), 2) for v in nat["国内游客总人次_亿人次"]]

    line = Line(init_opts=init_opts("276px"))
    line.add_xaxis(x)
    line.add_yaxis(
        "旅游总收入（亿元）", rev, yaxis_index=0, symbol="circle", symbol_size=7,
        is_smooth=True, linestyle_opts=opts.LineStyleOpts(width=3),
        itemstyle_opts=opts.ItemStyleOpts(color=D["accent"]),
        label_opts=opts.LabelOpts(is_show=False),
        markarea_opts=opts.MarkAreaOpts(
            data=[opts.MarkAreaItem(name="疫情期间 2020—2022", x=("2020", "2022"))],
            label_opts=opts.LabelOpts(color="#FFA94D", font_size=11, position="top"),
            itemstyle_opts=opts.ItemStyleOpts(color="#FF6B6B", opacity=0.14)),
        markpoint_opts=opts.MarkPointOpts(
            data=[opts.MarkPointItem(type_="max", name="峰值"),
                  opts.MarkPointItem(type_="min", name="谷值")],
            label_opts=opts.LabelOpts(color="#FFFFFF", font_size=10),
            symbol_size=46),
    )
    line.extend_axis(yaxis=opts.AxisOpts(
        name="游客量（亿人次）",
        name_textstyle_opts=opts.TextStyleOpts(color=D["accent2"], font_size=11),
        axislabel_opts=opts.LabelOpts(color=D["accent2"]),
        splitline_opts=opts.SplitLineOpts(is_show=False)))
    line.add_yaxis(
        "国内游客量（亿人次）", tou, yaxis_index=1, symbol="rect", symbol_size=7,
        is_smooth=True, linestyle_opts=opts.LineStyleOpts(width=3, type_="dashed"),
        itemstyle_opts=opts.ItemStyleOpts(color=D["accent2"]),
        label_opts=opts.LabelOpts(is_show=False))
    line.set_global_opts(
        tooltip_opts=tip_opts("axis", axis_pointer_type="cross"),
        legend_opts=opts.LegendOpts(
            pos_top="0%",
            textstyle_opts=opts.TextStyleOpts(color=D["text_sub"], font_size=11)),
        xaxis_opts=opts.AxisOpts(
            axislabel_opts=opts.LabelOpts(color=D["text_sub"]),
            axisline_opts=opts.AxisLineOpts(
                linestyle_opts=opts.LineStyleOpts(color=D["panel_border"]))),
    )
    # 左轴命名与配色（Pyecharts 未封装的部分用原生 patch 补）
    line.options["yAxis"][0]["name"] = "收入（亿元）"
    line.options["yAxis"][0]["nameTextStyle"] = {"color": D["accent"], "fontSize": 11}
    line.options["yAxis"][0]["axisLabel"] = {"color": D["text_sub"]}
    # 固定像素栅格：布局可控，避免容器的百分比换算把轴标签挤出画布
    line.options["grid"] = {"left": 66, "right": 54, "top": 64, "bottom": 30,
                            "containLabel": False}
    line.options["yAxis"][0]["nameGap"] = 12
    return embed(line)


# ============================================================================
# ④ 省份排名动态条形图模块（Timeline 动态排序）
# ============================================================================
def chart_rank_timeline(mrg: pd.DataFrame) -> str:
    """逐年演示省份旅游收入排名（TOP15），自动播放 + 时间轴可拖动。"""
    tl = Timeline(init_opts=init_opts("344px"))
    years = sorted(int(y) for y in mrg["年份"].unique().tolist())

    for year in years:
        d = (mrg[mrg["年份"] == year]
             .sort_values("省份旅游收入_亿元", ascending=True)
             .tail(cfg.TOP_N_PROVINCE))
        bar = Bar()
        bar.add_xaxis(d["省份"].tolist())
        bar.add_yaxis(
            f"{year} 年旅游收入", [round(float(v), 1) for v in d["省份旅游收入_亿元"]],
            category_gap="26%",
            label_opts=opts.LabelOpts(
                is_show=True, position="right", color=D["text"], font_size=10,
                formatter=JsCode("function(p){return p.value.toLocaleString();}")),
            itemstyle_opts=opts.ItemStyleOpts(color=JsCode(GRAD_GOLD)),
        )
        bar.reversal_axis()
        bar.set_global_opts(
            xaxis_opts=opts.AxisOpts(
                name="亿元",
                name_textstyle_opts=opts.TextStyleOpts(color=D["text_sub"], font_size=10),
                axislabel_opts=opts.LabelOpts(color=D["text_sub"], font_size=10),
                splitline_opts=opts.SplitLineOpts(
                    is_show=True,
                    linestyle_opts=opts.LineStyleOpts(color=D["grid"], type_="dashed"))),
            yaxis_opts=opts.AxisOpts(
                axislabel_opts=opts.LabelOpts(color=D["text"], font_size=10.5)),
            tooltip_opts=tip_opts("axis", axis_pointer_type="shadow"),
        )
        # 固定像素栅格（省份名 2 字需 ~40px；右侧留出数值标签空间）
        bar.options["grid"] = {"left": 58, "right": 82, "top": 8, "bottom": 72,
                               "containLabel": False}
        bar.options["xAxis"][0]["max"] = "dataMax"   # 坐标轴贴合最大值，条形铺满
        bar.options["legend"] = [{"show": False}]    # 年份由时间轴体现，图例冗余
        tl.add(bar, f"{year} 年")

    tl.add_schema(
        axis_type="category", is_auto_play=True, play_interval=1100,
        is_loop_play=True, is_timeline_show=True, is_inverse=False,
        pos_left="center", pos_bottom="0%", width="88%",
        symbol="circle", symbol_size=9,
        label_opts=opts.LabelOpts(color=D["text_sub"], font_size=11),
        itemstyle_opts=opts.ItemStyleOpts(color=D["accent"]),
        # 这两个 StyleOpts 在 pyecharts 2.1 未封装成类，直接传原生 ECharts 配置
        checkpointstyle_opts={"symbol": "pin", "symbolSize": 18,
                              "color": D["accent2"], "borderColor": "#FFFFFF"},
        controlstyle_opts={"color": D["text_sub"], "borderColor": D["panel_border"]},
    )
    tl.options["baseOption"]["color"] = [D["accent2"]]
    return embed(tl)


# ============================================================================
# ⑤ 节假日对比模块
# ============================================================================
def chart_holiday(hol: pd.DataFrame) -> str:
    """春节 / 五一 / 国庆 三节假日的旅游收入对比 + 国庆接待人次折线（右轴）。"""
    years = sorted(int(y) for y in hol[hol["年份"] >= 2019]["年份"].unique().tolist())
    x = [str(y) for y in years]
    color_map = {"春节": "#FF8A65", "五一": "#4DD0E1", "国庆": "#FFD166"}

    bar = Bar(init_opts=init_opts("338px"))
    bar.add_xaxis(x)
    for h in ["春节", "五一", "国庆"]:
        d = hol[hol["节假日类型"] == h].set_index("年份")
        vals = [round(float(d.loc[y, "节假日旅游总收入_亿元"]), 1) if y in d.index else 0
                for y in years]
        bar.add_yaxis(
            f"{h}旅游收入", vals, category_gap="42%",
            itemstyle_opts=opts.ItemStyleOpts(color=color_map[h]),
            label_opts=opts.LabelOpts(is_show=False))

    d_gq = hol[hol["节假日类型"] == "国庆"].set_index("年份")
    line = Line()
    line.add_xaxis(x)
    line.add_yaxis(
        "国庆接待人次（亿人次）",
        [round(float(d_gq.loc[y, "接待人次_亿人次"]), 2) if y in d_gq.index else 0
         for y in years],
        yaxis_index=1, is_smooth=True, symbol="diamond", symbol_size=8,
        linestyle_opts=opts.LineStyleOpts(width=2.5, type_="dashed"),
        itemstyle_opts=opts.ItemStyleOpts(color="#FFFFFF"),
        label_opts=opts.LabelOpts(is_show=False))
    bar.overlap(line)
    bar.extend_axis(yaxis=opts.AxisOpts(
        name="亿人次",
        name_textstyle_opts=opts.TextStyleOpts(color="#FFFFFF", font_size=10),
        axislabel_opts=opts.LabelOpts(color="#FFFFFF")))
    bar.set_global_opts(
        tooltip_opts=tip_opts("axis", axis_pointer_type="shadow"),
        legend_opts=opts.LegendOpts(
            pos_top="0%",
            textstyle_opts=opts.TextStyleOpts(color=D["text_sub"], font_size=10.5)),
        xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(color=D["text_sub"])),
        yaxis_opts=opts.AxisOpts(
            name="亿元",
            name_textstyle_opts=opts.TextStyleOpts(color=D["text_sub"], font_size=10),
            axislabel_opts=opts.LabelOpts(color=D["text_sub"]),
            splitline_opts=opts.SplitLineOpts(
                is_show=True,
                linestyle_opts=opts.LineStyleOpts(color=D["grid"], type_="dashed"))),
    )
    bar.options["grid"] = {"left": 66, "right": 58, "top": 74, "bottom": 30,
                           "containLabel": False}
    return embed(bar)


# ============================================================================
# ⑥ 热门城市模块
# ============================================================================
def chart_city(cit: pd.DataFrame) -> str:
    """TOP10 热门旅游城市旅游收入（横向条形 + 渐变着色）。"""
    d = (cit[cit["年份"] == YEAR]
         .sort_values("城市旅游收入_亿元", ascending=True)
         .tail(cfg.TOP_N_CITY))
    bar = Bar(init_opts=init_opts("260px"))
    bar.add_xaxis(d["热门旅游城市"].tolist())
    bar.add_yaxis(
        f"{YEAR} 年城市旅游收入", [round(float(v), 1) for v in d["城市旅游收入_亿元"]],
        category_gap="34%",
        label_opts=opts.LabelOpts(
            is_show=True, position="right", color=D["text"], font_size=11,
            formatter=JsCode("function(p){return p.value.toLocaleString()+' 亿元';}")),
        itemstyle_opts=opts.ItemStyleOpts(color=JsCode(GRAD_CYAN)))
    bar.reversal_axis()
    bar.set_global_opts(
        tooltip_opts=tip_opts("axis", axis_pointer_type="shadow", formatter=JsCode("""
            function (ps) {
                var p = ps[0], d = (window.__CITY__ || {})[p.name] || {};
                return '<div style="font-size:14px;font-weight:700;margin-bottom:5px">' + p.name
                     + '<span style="font-size:11px;color:#8FB8E0">（' + (d.prov || '-') + '）</span></div>'
                     + '旅游收入：<b style="color:#22D3EE">' + p.value.toLocaleString() + '</b> 亿元<br/>'
                     + '接待游客量：<b style="color:#FFD166">'
                     + (d.tou ? d.tou.toLocaleString() : '-') + '</b> 万人次';
            }""")),
        xaxis_opts=opts.AxisOpts(
            axislabel_opts=opts.LabelOpts(color=D["text_sub"], font_size=10),
            splitline_opts=opts.SplitLineOpts(
                is_show=True,
                linestyle_opts=opts.LineStyleOpts(color=D["grid"], type_="dashed"))),
        yaxis_opts=opts.AxisOpts(
            axislabel_opts=opts.LabelOpts(color=D["text"], font_size=11.5)),
    )
    # 关键修复：横向条形图的类目轴标签必须预留固定宽度，否则会被画布裁掉
    bar.options["grid"] = {"left": 62, "right": 96, "top": 40, "bottom": 24,
                           "containLabel": False}
    return embed(bar)


# ============================================================================
# （附加）聚类结果模块
# ============================================================================
def cluster_html() -> dict:
    """K-Means 四梯队徽章行（对应论文 4.2.5）。

    说明：该面板高度有限（轴向空间窄），用环形图会显得很小；
    改用纯 HTML 徽章行，信息密度更高：梯队名 / 省份数 / 收入均值 / 占比条。
    """
    path = os.path.join(cfg.CLUSTER_DIR, "province_cluster_result.csv")
    if not os.path.exists(path):
        return {"html": '<div class="lvl-empty">聚类结果缺失，请先运行 03_kmeans_cluster.py</div>',
                "lut": {}}
    d = pd.read_csv(path, encoding="utf-8-sig")
    g = (d.groupby("发展等级")
           .agg(n=("省份", "count"),
                avg=("省份旅游收入_亿元", "mean"),
                mem=("省份", lambda x: "、".join(x)))
           .sort_values("avg", ascending=False).reset_index())

    colors = [D["accent2"], D["accent"], "#76B041", "#FF6B6B", "#8E6C8A", "#7DD3FC"]
    total = int(g["n"].sum())
    rows, lut = [], {}
    for i, r in g.iterrows():
        lv, n = r["发展等级"], int(r["n"])
        short = lv.split("（")[0]
        alias = lv.split("（")[1].rstrip("）") if "（" in lv else ""
        lut[lv] = {"n": n, "avg": round(float(r["avg"]), 1), "mem": r["mem"]}
        rows.append(f'''
        <div class="lvl-row" style="--c:{colors[i % len(colors)]};--w:{n / total * 100:.1f}%"
             title="{r['mem']}">
          <span class="lvl-name">{short}<i>{alias}</i></span>
          <span class="lvl-stat"><b>{n}</b> 省 · 均值 {r["avg"]:,.0f} 亿元</span>
        </div>''')
    return {"html": '<div class="lvl-list">' + "".join(rows) + "</div>", "lut": lut}


# ============================================================================
# 大屏 HTML 骨架
# ============================================================================
def build_html(parts: dict, kpi: dict) -> str:
    """把各模块片段、指标卡片与数据字典拼装成完整大屏 HTML。"""
    def panel(title: str, body: str, height: int | None = None,
              extra_class: str = "", note: str = "") -> str:
        """生成一个面板；height 为固定像素高（None 表示自动撑满剩余空间）。"""
        note_html = f'<span class="panel-note">{note}</span>' if note else ""
        style = f' style="flex:0 0 {height}px"' if height else ' style="flex:1 1 auto"'
        return f"""
        <section class="panel {extra_class}"{style}>
          <header class="panel-head"><h2>{title}</h2>{note_html}</header>
          <div class="panel-body">{body}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>全国旅游业发展可视化分析大屏</title>
<script src="assets/echarts.min.js"></script>
<script src="assets/maps/china_std.js"></script>
<script>
  /* 兜底：若地图资源早于 echarts 加载，则在此时补注册 */
  if (window.__CHINA_GEO__ && typeof echarts !== 'undefined') {{
    echarts.registerMap('china', window.__CHINA_GEO__);
  }}
  /* 数据字典：供 tooltip 回调读取（省份 / 城市 / 聚类梯队） */
  window.__PROV__    = {json.dumps(parts['prov_lut'], ensure_ascii=False)};
  window.__CITY__    = {json.dumps(parts['city_lut'], ensure_ascii=False)};
  window.__CLUSTER__ = {json.dumps(parts['cluster_lut'], ensure_ascii=False)};
</script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{
    width:100%; height:100%; overflow:hidden; background:{D['bg']};
    font-family:"Microsoft YaHei","Source Han Sans CN","PingFang SC",sans-serif;
  }}
  /* 大屏主体：1920×1080 设计稿，等比缩放自适应任意屏幕 */
  #screen {{
    position:absolute; left:50%; top:50%;
    width:1920px; height:1080px; transform-origin:center center;
    padding:14px 16px 16px;
    background:
      radial-gradient(1200px 620px at 18% -10%, rgba(34,211,238,.14), transparent 60%),
      radial-gradient(1000px 560px at 88% 108%, rgba(255,197,61,.10), transparent 62%),
      linear-gradient(180deg,#0B1B33 0%,#08152A 100%);
    display:flex; flex-direction:column; gap:12px;
  }}

  /* ---------- 顶部标题栏 ---------- */
  #header {{
    height:80px; flex:0 0 80px; position:relative;
    display:flex; align-items:center; justify-content:center; border-radius:10px;
    background:linear-gradient(90deg,rgba(17,42,74,0) 0%,rgba(23,60,105,.92) 18%,
               rgba(23,60,105,.92) 82%,rgba(17,42,74,0) 100%);
  }}
  #header::after {{
    content:""; position:absolute; left:8%; right:8%; bottom:0; height:2px;
    background:linear-gradient(90deg,transparent,{D['accent']},{D['accent2']},transparent);
  }}
  #header h1 {{
    font-size:36px; letter-spacing:5px; font-weight:700;
    background:linear-gradient(180deg,#FFFFFF 12%,{D['accent']} 92%);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }}
  #header .side {{ position:absolute; color:{D['text_sub']}; font-size:12.5px; line-height:1.6; }}
  #header .side.l {{ left:24px; }} #header .side.r {{ right:24px; text-align:right; }}
  #header .side b {{ color:{D['accent2']}; }}

  /* ---------- 三列栅格 ---------- */
  #grid {{ flex:1 1 auto; display:grid; gap:12px;
           grid-template-columns:470px 890px 1fr; min-height:0; }}
  .col {{ display:flex; flex-direction:column; gap:12px; min-height:0; }}

  /* ---------- 面板 ---------- */
  .panel {{
    position:relative; border-radius:10px; overflow:hidden;
    background:linear-gradient(180deg,rgba(23,60,105,.86) 0%,rgba(11,30,54,.92) 100%);
    border:1px solid {D['panel_border']};
    box-shadow:inset 0 0 26px rgba(34,211,238,.07), 0 4px 18px rgba(0,0,0,.28);
    display:flex; flex-direction:column;
  }}
  .panel::before {{
    content:""; position:absolute; top:0; left:0; width:100%; height:2px;
    background:linear-gradient(90deg,{D['accent']},transparent 72%); opacity:.85;
  }}
  .panel-head {{
    flex:0 0 36px; display:flex; align-items:center; gap:10px;
    padding:0 12px; border-bottom:1px solid rgba(30,75,122,.7);
  }}
  .panel-head h2 {{
    font-size:15px; font-weight:700; color:{D['text']}; letter-spacing:1.2px;
    display:flex; align-items:center; gap:8px;
  }}
  .panel-head h2::before {{
    content:""; width:4px; height:15px; border-radius:2px;
    background:linear-gradient(180deg,{D['accent']},{D['accent2']});
  }}
  .panel-note {{ margin-left:auto; font-size:11.5px; color:{D['text_sub']}; }}
  .panel-body {{ flex:1 1 auto; min-height:0; padding:4px 6px 6px; position:relative; }}

  /* ---------- KPI 指标卡片 ---------- */
  .panel.kpi {{ flex:0 0 184px; }}
  .panel.kpi .panel-body {{ padding:0; }}
  .kpi-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; height:100%; padding:8px; }}
  .kpi-card {{
    position:relative; border-radius:8px; padding:8px 11px;
    background:linear-gradient(135deg,rgba(255,255,255,.055),rgba(255,255,255,.01));
    border:1px solid rgba(120,180,255,.18);
    display:flex; flex-direction:column; justify-content:center; overflow:hidden;
  }}
  .kpi-card::after {{
    content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
    background:var(--accent); box-shadow:0 0 12px var(--accent);
  }}
  .kpi-label {{ font-size:12px; color:{D['text_sub']}; display:flex; align-items:center; gap:6px; }}
  .kpi-dot {{ color:var(--accent); font-size:9px; }}
  .kpi-value {{
    font-size:27px; font-weight:800; color:var(--accent); line-height:1.2;
    font-family:"Consolas","Microsoft YaHei",monospace; letter-spacing:.5px;
    text-shadow:0 0 16px rgba(34,211,238,.28);
  }}
  .kpi-unit {{ font-size:12px; color:{D['text_sub']}; margin-left:5px; font-weight:400; }}
  .kpi-yoy {{ font-size:11.5px; margin-top:2px; }}
  .kpi-yoy.up {{ color:#FF8A80; }}    /* 上涨=红（国内惯例） */
  .kpi-yoy.down {{ color:#69F0AE; }}  /* 下跌=绿 */

  /* ---------- K-Means 梯队徽章行 ---------- */
  .lvl-list {{ display:flex; flex-direction:column; gap:6px; height:100%; padding:6px 8px; }}
  .lvl-row {{
    position:relative; flex:1 1 auto; min-height:0;
    display:flex; align-items:center; justify-content:space-between; gap:8px;
    padding:4px 10px; border-radius:6px; overflow:hidden;
    background:rgba(255,255,255,.035);
    border:1px solid rgba(120,180,255,.14); border-left:3px solid var(--c);
  }}
  .lvl-row::before {{
    content:""; position:absolute; left:0; top:0; bottom:0;
    width:var(--w); background:var(--c); opacity:.13;
  }}
  .lvl-name {{
    position:relative; font-size:12.5px; color:{D['text']}; font-weight:600;
    white-space:nowrap; display:flex; align-items:baseline; gap:6px;
  }}
  .lvl-name i {{
    font-style:normal; font-size:11px; font-weight:400; color:{D['text_sub']};
  }}
  .lvl-stat {{ position:relative; font-size:11.5px; color:{D['text_sub']}; white-space:nowrap; }}
  .lvl-stat b {{ color:var(--c); font-size:14px; margin-right:1px; }}
  .lvl-empty {{
    height:100%; display:flex; align-items:center; justify-content:center;
    color:{D['text_sub']}; font-size:12.5px;
  }}

  #foot {{
    flex:0 0 22px; text-align:center; font-size:11.5px;
    color:rgba(143,184,224,.72); letter-spacing:.6px;
  }}
</style>
</head>
<body>
<div id="screen">
  <header id="header">
    <div class="side l">数据范围：2015—2024 年 · 31 个省级行政区<br>
      数据来源：文化和旅游部 / 国家统计局 / 各省统计年鉴（模拟构造）</div>
    <h1>全国旅游业发展可视化分析大屏</h1>
    <div class="side r">分析截面年份：<b>{YEAR}</b><br>
      K-Means 聚类 K=4 · 四梯队划分</div>
  </header>

  <div id="grid">
    <div class="col">
      {panel("① 旅游总览", kpi_html(kpi), height=184, extra_class="kpi")}
      {panel("③ 趋势分析", parts['trend'], height=324,
             note="收入 / 游客量 双轴 · 疫情区间标注")}
      {panel("④ 省份排名动态", parts['rank'], height=392,
             note="自动播放 · 可拖动时间轴")}
    </div>
    <div class="col">
      {panel(f"② 全国旅游收入分布热力图（{YEAR} 年）", parts['map'],
             note="悬浮查看省份旅游收入与游客量")}
    </div>
    <div class="col">
      {panel("⑤ 节假日对比", parts['holiday'], height=386, note="春节 / 五一 / 国庆")}
      {panel(f"⑥ 热门旅游城市 TOP{cfg.TOP_N_CITY}", parts['city'], height=308,
             note=f"{YEAR} 年旅游收入")}
      {panel("（附加）K-Means 旅游发展梯队", parts['cluster'], height=206,
             note="对应论文 4.2.5")}
    </div>
  </div>

  <div id="foot">
    全国旅游业发展可视化分析系统 · 交互式可视化大屏 &nbsp;|&nbsp;
    技术栈：Python 3.9+ · Pandas / NumPy · Scikit-learn · Matplotlib / Seaborn · Pyecharts &nbsp;|&nbsp;
    本页为纯静态 HTML，无需后端服务，双击即可离线打开
  </div>
</div>

<script>
  /* 等比缩放：1920×1080 设计稿 → 自适应窗口 */
  (function () {{
    var W = 1920, H = 1080, el = document.getElementById('screen');
    function fit() {{
      var s = Math.min(window.innerWidth / W, window.innerHeight / H);
      el.style.transform = 'translate(-50%,-50%) scale(' + s + ')';
    }}
    fit();
    window.addEventListener('resize', fit);
    window.addEventListener('load', function () {{
      setTimeout(function () {{
        document.querySelectorAll('.chart-container').forEach(function (n) {{
          var inst = echarts.getInstanceByDom(n);
          if (inst) inst.resize();
        }});
      }}, 150);
    }});
  }})();
</script>
</body>
</html>
"""


# ============================================================================
# 主流程
# ============================================================================
def main() -> str:
    print("=" * 76)
    print("模块4：交互式可视化大屏（Pyecharts）")
    print("=" * 76)

    if not cfg.ensure_assets():
        raise SystemExit("缺少离线 echarts 资源，无法保证离线运行。")

    def rd(name):
        return pd.read_csv(os.path.join(cfg.DATA_DIR, name), encoding="utf-8-sig")

    nat, mrg, hol, cit = (rd("cleaned_national.csv"), rd("merged_province_full.csv"),
                          rd("cleaned_holiday.csv"), rd("cleaned_city.csv"))

    kpi = build_kpi(nat)
    print(f"\n[总览指标] {kpi['year']} 年：旅游总收入 {kpi['rev']:,.0f} 亿元"
          f"（同比 {kpi['rev_yoy']:+.2f}%）；游客 {kpi['tou']:.2f} 亿人次"
          f"（同比 {kpi['tou_yoy']:+.2f}%）；占GDP {kpi['ratio']:.2f}%")

    # tooltip 数据字典（城市）
    city_lut = {r["热门旅游城市"]: {"prov": r["所属省份"],
                                    "tou": round(float(r["接待游客量_万人次"]), 1)}
                for _, r in cit[cit["年份"] == YEAR].iterrows()}

    print("\n正在生成图表 ...")
    cluster = cluster_html()
    mp = chart_map(mrg)
    parts = {"prov_lut": mp["lut"], "city_lut": city_lut, "cluster_lut": cluster["lut"]}

    parts["map"] = mp["html"];            print("  · ② 全国热力地图（悬浮交互）")
    parts["trend"] = chart_trend(nat);    print("  · ③ 趋势分析（双轴折线 + 疫情区间）")
    parts["rank"] = chart_rank_timeline(mrg)
    print(f"  · ④ 省份排名动态条形图（{mrg['年份'].nunique()} 帧，自动播放）")
    parts["holiday"] = chart_holiday(hol); print("  · ⑤ 节假日对比（春节/五一/国庆）")
    parts["city"] = chart_city(cit);      print(f"  · ⑥ 热门城市 TOP{cfg.TOP_N_CITY}")
    parts["cluster"] = cluster["html"];   print("  · （附加）K-Means 四梯队徽章")

    with open(cfg.DASHBOARD_HTML, "w", encoding="utf-8") as f:
        f.write(build_html(parts, kpi))

    # 输出目录自带 assets，保证 output/ 可整体拷走离线使用
    out_assets = os.path.join(cfg.OUTPUT_DIR, "assets", "maps")
    os.makedirs(out_assets, exist_ok=True)
    shutil.copy2(os.path.join(cfg.ASSETS_DIR, "echarts.min.js"),
                 os.path.join(cfg.OUTPUT_DIR, "assets", "echarts.min.js"))
    shutil.copy2(cfg.MAP_ASSET, os.path.join(out_assets, "china_std.js"))

    size_kb = os.path.getsize(cfg.DASHBOARD_HTML) / 1024
    print(f"\n[完成] 大屏已生成：{cfg.DASHBOARD_HTML}")
    print(f"       文件大小 {size_kb:,.1f} KB；离线资源已同步至 output/assets/")
    print("       双击该 HTML 即可在浏览器打开（无需任何后端服务）")
    return cfg.DASHBOARD_HTML


if __name__ == "__main__":
    main()

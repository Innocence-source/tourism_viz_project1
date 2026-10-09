# -*- coding: utf-8 -*-
"""
02_analysis_charts.py —— 模块2：全国旅游业统计分析（静态图表）
==============================================================
对应论文第 4 章「全国旅游业发展分析」：
    4.1 全国旅游发展总体趋势分析      → 图4-1 / 图4-2 / 图4-3 / 图4-4
    4.2 各省市旅游发展对比分析        → 图4-5 / 图4-7
    4.3 节假日旅游市场分析            → 图4-8
    4.4 热门旅游城市分析              → 图4-9
    4.5 旅游经济影响因素分析          → 图4-6（散点+相关系数矩阵热力图）

绘图库：Matplotlib + Seaborn
输入：data/cleaned_*.csv、data/merged_province_full.csv（由 01_preprocess.py 生成）
输出：output/charts/*.png（150 dpi，可直接插入论文）

运行：python src/02_analysis_charts.py
"""

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

CN = cfg.CN_FONT_CANDIDATES[0]

# Seaborn 主题（白色网格、适合论文黑白打印）
sns.set_theme(style="whitegrid", font=CN, rc={
    "axes.unicode_minus": False,
    "font.sans-serif": cfg.CN_FONT_CANDIDATES,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})
P = cfg.PALETTE
_yi = FuncFormatter(lambda v, _: f"{v:,.0f}")


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
def save(fig, filename: str) -> None:
    """保存图片并打印路径。"""
    path = os.path.join(cfg.CHART_DIR, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[输出] output/charts/{filename}")


def load() -> dict:
    """读取清洗后的数据。"""
    def rd(name):
        return pd.read_csv(os.path.join(cfg.DATA_DIR, name), encoding="utf-8-sig")

    return {
        "nat": rd("cleaned_national.csv"),
        "pro": rd("cleaned_province.csv"),
        "hol": rd("cleaned_holiday.csv"),
        "cit": rd("cleaned_city.csv"),
        "mrg": rd("merged_province_full.csv"),
    }


def label_bars(ax, bars, fmt="{:.0f}", dy_ratio=0.015, fontsize=8.5, color="#333333"):
    """在柱状图顶部标注数值。"""
    top = max(b.get_height() for b in bars) if len(bars) else 1
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h),
                    xy=(b.get_x() + b.get_width() / 2, h),
                    xytext=(0, 3 if h >= 0 else -12),
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=fontsize, color=color)


def pearson(x, y):
    """计算 Pearson 相关系数 r 与 p 值（优先 scipy，失败则手算 r）。"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    try:
        from scipy import stats
        r, p = stats.pearsonr(x, y)
        return float(r), float(p)
    except Exception:
        r = float(np.corrcoef(x, y)[0, 1])
        return r, float("nan")


# ============================================================================
# 4.1 全国旅游发展总体趋势分析
# ============================================================================
def fig_4_1_national_revenue(nat: pd.DataFrame) -> None:
    """图4-1 全国旅游总收入年度变化趋势（折线 + 面积）"""
    fig, ax = plt.subplots(figsize=(9, 4.6))
    x, y = nat["年份"].to_numpy(), nat["全国旅游总收入_亿元"].to_numpy()

    ax.plot(x, y, marker="o", ms=7, lw=2.4, color=P[0], label="全国旅游总收入", zorder=3)
    ax.fill_between(x, y, alpha=0.15, color=P[0], zorder=2)
    for xi, yi in zip(x, y):
        ax.annotate(f"{yi:,.0f}", (xi, yi), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8.5, color="#1a3d5c")

    # 疫情区间高亮（2020—2022）
    ax.axvspan(2019.5, 2022.5, color="#FF6B6B", alpha=0.10, zorder=1)
    ax.text(2021, y.max() * 0.92, "疫情期间（2020—2022）", ha="center",
            fontsize=10, color="#C0392B")

    ax.set_title("图4-1  全国旅游总收入年度变化趋势（2015—2024）", fontsize=13, pad=12)
    ax.set_xlabel("年份"); ax.set_ylabel("旅游总收入（亿元）")
    ax.set_xticks(x); ax.yaxis.set_major_formatter(_yi)
    ax.legend(loc="lower right", frameon=True)
    save(fig, "图4-1_全国旅游总收入年度变化趋势.png")


def fig_4_2_tourists(nat: pd.DataFrame) -> None:
    """图4-2 国内游客量年度变化"""
    fig, ax = plt.subplots(figsize=(9, 4.6))
    x, y = nat["年份"].to_numpy(), nat["国内游客总人次_亿人次"].to_numpy()

    bars = ax.bar(x, y, width=0.58, color=P[0], alpha=0.85, zorder=3, label="国内游客总人次")
    ax.plot(x, y, marker="s", ms=6, lw=2, color=P[1], zorder=4, label="趋势线")
    label_bars(ax, bars, fmt="{:.1f}", fontsize=8.5)

    ax.axvspan(2019.5, 2022.5, color="#FF6B6B", alpha=0.10, zorder=1)
    ax.set_title("图4-2  国内游客量年度变化（2015—2024）", fontsize=13, pad=12)
    ax.set_xlabel("年份"); ax.set_ylabel("国内游客总人次（亿人次）")
    ax.set_xticks(x); ax.set_ylim(0, y.max() * 1.18)
    ax.legend(loc="lower left", frameon=True)
    save(fig, "图4-2_国内游客量年度变化.png")


def fig_4_3_ratio(nat: pd.DataFrame) -> None:
    """图4-3 旅游收入占GDP比重变化（柱 + 折线双轴）"""
    fig, ax1 = plt.subplots(figsize=(9, 4.6))
    x = nat["年份"].to_numpy()

    bars = ax1.bar(x, nat["全国GDP_亿元"], width=0.58, color="#BFD7EA",
                   label="全国GDP（亿元）", zorder=2)
    ax1.set_ylabel("全国GDP（亿元）", color="#33667F")
    ax1.yaxis.set_major_formatter(_yi)
    ax1.set_xticks(x)

    ax2 = ax1.twinx()
    ax2.plot(x, nat["旅游收入占GDP比重_%"], marker="o", ms=7, lw=2.4,
             color=P[1], zorder=4, label="旅游收入占GDP比重")
    ax2.set_ylabel("旅游收入占GDP比重（%）", color=P[1])
    for xi, yi in zip(x, nat["旅游收入占GDP比重_%"]):
        ax2.annotate(f"{yi:.2f}", (xi, yi), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=8.5, color=P[1])
    ax2.set_ylim(0, nat["旅游收入占GDP比重_%"].max() * 1.35)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", frameon=True)
    ax1.set_title("图4-3  旅游收入占GDP比重变化（2015—2024）", fontsize=13, pad=12)
    ax1.set_xlabel("年份")
    ax1.grid(False); ax2.grid(False)
    save(fig, "图4-3_旅游收入占GDP比重变化.png")


def fig_4_4_pre_post_covid(nat: pd.DataFrame) -> None:
    """图4-4 疫情前后旅游指标对比（分组柱状图）"""
    key_years = [2019, 2020, 2022, 2023, 2024]
    labels = ["2019\n（疫前峰值）", "2020\n（疫情初期）", "2022\n（疫情谷底）",
              "2023\n（恢复首年）", "2024\n（恢复后期）"]
    d = nat.set_index("年份").loc[key_years]
    rev = d["全国旅游总收入_亿元"].to_numpy()
    tou = d["国内游客总人次_亿人次"].to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    for ax, vals, title, unit in zip(
            axes, [rev, tou],
            ["旅游总收入对比", "国内游客人次对比"],
            ["亿元", "亿人次"]):
        base = vals[0]
        colors = ["#4C9F70" if v >= base else "#D64550" for v in vals]
        bars = ax.bar(labels, vals, color=colors, width=0.6, zorder=3)
        ax.bar_label(bars, fmt="%.0f" if unit == "亿元" else "%.2f",
                     padding=4, fontsize=9)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v / base * 100 - 100:+.1f}%",
                        xy=(b.get_x() + b.get_width() / 2, v * 0.5),
                        ha="center", fontsize=8.5, color="white", weight="bold")
        ax.set_title(title, fontsize=12)
        ax.set_ylabel(unit)
        ax.set_ylim(0, vals.max() * 1.22)
        ax.tick_params(axis="x", labelsize=8.5)

    fig.suptitle("图4-4  疫情前后旅游关键指标对比（以 2019 年为基准）", fontsize=13.5, y=1.02)
    save(fig, "图4-4_疫情前后旅游指标对比.png")


# ============================================================================
# 4.2 各省市旅游发展对比分析
# ============================================================================
def fig_4_5_region_compare(mrg: pd.DataFrame, year: int = cfg.ANALYSIS_YEAR) -> None:
    """图4-5 东中西部旅游收入、游客量对比（分组柱状图）"""
    d = mrg[mrg["年份"] == year]
    g = d.groupby("所属区域", as_index=False).agg(
        旅游收入=("省份旅游收入_亿元", "sum"),
        游客量=("接待游客数量_万人次", "sum"),
        省份数=("省份", "count"))
    order = ["东部", "中部", "西部"]
    g["所属区域"] = pd.Categorical(g["所属区域"], order, ordered=True)
    g = g.sort_values("所属区域")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    for ax, col, title, unit in zip(
            axes, ["旅游收入", "游客量"],
            [f"{year} 年东中西部旅游收入合计", f"{year} 年东中西部接待游客量合计"],
            ["亿元", "万人次"]):
        vals = g[col].to_numpy()
        colors = [cfg.REGION_COLORS[r] for r in g["所属区域"]]
        bars = ax.bar(g["所属区域"].astype(str), vals, color=colors, width=0.58, zorder=3)
        ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=9.5)
        ax.set_title(title, fontsize=12)
        ax.set_ylabel(unit)
        ax.set_ylim(0, vals.max() * 1.20)
        # 占比标注
        for b, v in zip(bars, vals):
            ax.annotate(f"{v / vals.sum() * 100:.1f}%",
                        xy=(b.get_x() + b.get_width() / 2, v * 0.45),
                        ha="center", fontsize=10, color="white", weight="bold")

    fig.suptitle(f"图4-5  {year} 年东中西部旅游发展水平对比", fontsize=13.5, y=1.02)
    save(fig, "图4-5_东中西部旅游发展对比.png")


def fig_4_7_province_rank(mrg: pd.DataFrame, year: int = cfg.ANALYSIS_YEAR) -> None:
    """图4-7 各省份旅游收入排名（TOP15 横向条形图）"""
    d = (mrg[mrg["年份"] == year]
         .sort_values("省份旅游收入_亿元", ascending=False)
         .head(15))
    fig, ax = plt.subplots(figsize=(9, 6.4))
    colors = [cfg.REGION_COLORS[r] for r in d["所属区域"]]
    bars = ax.barh(d["省份"][::-1], d["省份旅游收入_亿元"][::-1],
                   color=colors[::-1], height=0.66, zorder=3)
    ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=9)
    ax.set_xlabel("省份旅游收入（亿元）")
    ax.set_title(f"图4-7  {year} 年各省份旅游收入排名 TOP15", fontsize=13, pad=12)
    ax.set_xlim(0, d["省份旅游收入_亿元"].max() * 1.16)
    handles = [plt.Rectangle((0, 0), 1, 1, color=cfg.REGION_COLORS[r])
               for r in ["东部", "中部", "西部"]]
    ax.legend(handles, ["东部", "中部", "西部"], loc="lower right", frameon=True)
    save(fig, "图4-7_各省份旅游收入排名TOP15.png")


# ============================================================================
# 4.5 旅游经济影响因素分析
# ============================================================================
def fig_4_6_correlation(mrg: pd.DataFrame, year: int = cfg.ANALYSIS_YEAR) -> dict:
    """图4-6 相关性分析：散点图（含回归线）+ 相关系数矩阵热力图"""
    d = mrg[mrg["年份"] == year].copy()
    pairs = [("省份GDP_亿元", "地区生产总值（亿元）"),
             ("常住人口_万人", "常住人口（万人）")]
    stats_out = {}

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 4.9),
                             gridspec_kw={"width_ratios": [1, 1, 1.15]})

    for ax, (col, label) in zip(axes[:2], pairs):
        r, p = pearson(d[col], d["省份旅游收入_亿元"])
        stats_out[col] = {"r": r, "p": p}
        sns.regplot(x=d[col], y=d["省份旅游收入_亿元"], ax=ax,
                    scatter_kws={"s": 52, "alpha": 0.75, "color": P[0],
                                 "edgecolor": "white", "linewidths": 0.6},
                    line_kws={"color": P[1], "lw": 2.2})
        # 标注省份名（仅标出旅游收入 TOP6，避免拥挤）
        top = d.nlargest(6, "省份旅游收入_亿元")
        for _, row in top.iterrows():
            ax.annotate(row["省份"], (row[col], row["省份旅游收入_亿元"]),
                        textcoords="offset points", xytext=(5, 4), fontsize=8.5,
                        color="#555555")
        ax.set_title(f"旅游收入 与 {label}\nPearson r = {r:.3f}（p = {p:.2e}）", fontsize=11.5)
        ax.set_xlabel(label); ax.set_ylabel("省份旅游收入（亿元）")
        ax.yaxis.set_major_formatter(_yi)

    # 相关系数矩阵热力图
    mat_cols = ["省份旅游收入_亿元", "接待游客数量_万人次",
                "省份GDP_亿元", "常住人口_万人", "人均旅游收入_元"]
    mat_cn = ["旅游收入", "接待游客量", "地区GDP", "常住人口", "人均旅游收入"]
    corr = d[mat_cols].corr(method="pearson")
    corr.index, corr.columns = mat_cn, mat_cn
    sns.heatmap(corr, ax=axes[2], annot=True, fmt=".3f", cmap="RdYlBu_r",
                vmin=-1, vmax=1, square=True, linewidths=0.6,
                cbar_kws={"shrink": 0.78, "label": "Pearson 相关系数"},
                annot_kws={"fontsize": 9.5})
    axes[2].set_title("相关系数矩阵热力图", fontsize=11.5)
    axes[2].tick_params(labelsize=9.5)
    axes[2].grid(False)

    fig.suptitle(f"图4-6  {year} 年旅游收入与经济社会因素的相关性分析（31 个省级行政区）",
                 fontsize=13.5, y=1.03)
    save(fig, "图4-6_旅游收入相关性分析.png")
    return stats_out


# ============================================================================
# 4.3 节假日旅游市场分析
# ============================================================================
def fig_4_8_holiday(hol: pd.DataFrame) -> None:
    """图4-8 春节 / 五一 / 国庆 节假日旅游数据对比"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.0))
    order = ["春节", "五一", "国庆"]
    hcolors = {"春节": P[1], "五一": P[2], "国庆": P[0]}

    # 左：2024 年三大节假日横向对比
    d24 = hol[hol["年份"] == cfg.ANALYSIS_YEAR].set_index("节假日类型").loc[order]
    x = np.arange(len(order)); w = 0.36
    ax = axes[0]
    b1 = ax.bar(x - w / 2, d24["节假日旅游总收入_亿元"], w,
                label="旅游总收入（亿元）", color=P[0], zorder=3)
    ax2 = ax.twinx()
    b2 = ax2.bar(x + w / 2, d24["接待人次_亿人次"], w,
                 label="接待人次（亿人次）", color=P[2], zorder=3)
    ax.bar_label(b1, fmt="{:,.0f}", padding=3, fontsize=9)
    ax2.bar_label(b2, fmt="{:.2f}", padding=3, fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(order, fontsize=11)
    ax.set_ylabel("旅游总收入（亿元）", color=P[0])
    ax2.set_ylabel("接待人次（亿人次）", color=P[2])
    ax.set_ylim(0, d24["节假日旅游总收入_亿元"].max() * 1.30)
    ax2.set_ylim(0, d24["接待人次_亿人次"].max() * 1.30)
    ax.set_title(f"{cfg.ANALYSIS_YEAR} 年三大节假日旅游数据对比", fontsize=12)
    ax.legend(loc="upper left", fontsize=9); ax2.legend(loc="upper right", fontsize=9)

    # 右：收入趋势（2020—2024，剔除疫情前后落差干扰）
    ax = axes[1]
    for h in order:
        dd = hol[(hol["节假日类型"] == h) & (hol["年份"] >= 2019)].sort_values("年份")
        ax.plot(dd["年份"], dd["节假日旅游总收入_亿元"], marker="o", ms=6.5, lw=2.2,
                label=h, color=hcolors[h])
    ax.set_title("三大节假日旅游总收入变化趋势（2019—2024）", fontsize=12)
    ax.set_xlabel("年份"); ax.set_ylabel("旅游总收入（亿元）")
    ax.yaxis.set_major_formatter(_yi)
    ax.legend(frameon=True)
    ax.set_xticks(range(2019, 2025))

    fig.suptitle("图4-8  节假日旅游市场对比分析", fontsize=13.5, y=1.02)
    save(fig, "图4-8_节假日旅游数据对比.png")


# ============================================================================
# 4.4 热门旅游城市分析
# ============================================================================
def fig_4_9_city(cit: pd.DataFrame, year: int = cfg.ANALYSIS_YEAR) -> None:
    """图4-9 热门旅游城市 TOP10 旅游收入"""
    d = (cit[cit["年份"] == year]
         .sort_values("城市旅游收入_亿元", ascending=False)
         .head(cfg.TOP_N_CITY))
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    cmap = plt.get_cmap("YlGnBu")
    colors = [cmap(0.35 + 0.5 * i / max(len(d) - 1, 1)) for i in range(len(d))]
    bars = ax.bar(d["热门旅游城市"], d["城市旅游收入_亿元"],
                  color=colors, width=0.6, zorder=3)
    ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=9)
    ax.set_ylabel("城市旅游收入（亿元）")
    ax.set_title(f"图4-9  {year} 年热门旅游城市 TOP{cfg.TOP_N_CITY} 旅游收入",
                 fontsize=13, pad=12)
    ax.set_ylim(0, d["城市旅游收入_亿元"].max() * 1.18)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    save(fig, "图4-9_热门旅游城市TOP10.png")


# ============================================================================
# 主流程
# ============================================================================
def main() -> dict:
    print("=" * 76)
    print("模块2：全国旅游业统计分析（静态图表）")
    print("=" * 76)
    cfg.setup_matplotlib_chinese()

    for f in ("cleaned_national.csv", "merged_province_full.csv"):
        if not os.path.exists(os.path.join(cfg.DATA_DIR, f)):
            raise SystemExit("请先运行 python src/01_preprocess.py 生成清洗数据")

    D = load()
    print(f"\n数据加载完成：全国表 {D['nat'].shape}，省级表 {D['mrg'].shape}，"
          f"节假日表 {D['hol'].shape}，城市表 {D['cit'].shape}\n")

    print("--- 4.1 全国旅游发展总体趋势分析 ---")
    fig_4_1_national_revenue(D["nat"])
    fig_4_2_tourists(D["nat"])
    fig_4_3_ratio(D["nat"])
    fig_4_4_pre_post_covid(D["nat"])

    print("\n--- 4.2 各省市旅游发展对比分析 ---")
    fig_4_5_region_compare(D["mrg"])
    fig_4_7_province_rank(D["mrg"])

    print("\n--- 4.3 节假日旅游市场分析 ---")
    fig_4_8_holiday(D["hol"])

    print("\n--- 4.4 热门旅游城市分析 ---")
    fig_4_9_city(D["cit"])

    print("\n--- 4.5 旅游经济影响因素分析 ---")
    stats_out = fig_4_6_correlation(D["mrg"])
    print("\n[相关性检验结果] 30 个省级行政区截面（%d 年）" % cfg.ANALYSIS_YEAR)
    for k, v in stats_out.items():
        print(f"  · 旅游收入 与 {k:<16} Pearson r = {v['r']:.4f}, p = {v['p']:.3e}")

    print(f"\n[完成] 共 9 张静态分析图已输出至：{cfg.CHART_DIR}")
    return D


if __name__ == "__main__":
    main()

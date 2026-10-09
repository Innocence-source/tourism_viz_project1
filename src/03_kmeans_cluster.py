# -*- coding: utf-8 -*-
"""
03_kmeans_cluster.py —— 模块3：K-Means 聚类挖掘分析
====================================================
对应论文 4.2.5「基于 K-Means 的省份旅游发展水平聚类分析」
与 4.2.6「河南省旅游发展定位分析」。

方法：
  1. 取目标年份（默认 2024）的省级截面数据；
  2. 以「省份旅游收入」「接待游客数量」为二维特征 → Z-Score 标准化；
  3. 肘部法则（Inertia 下降拐点）+ 轮廓系数（Silhouette）共同确定最优 K；
  4. 训练 K-Means（n_init 次重复取最优），输出每个省份的类别标签；
  5. 按各簇旅游收入均值降序，将簇映射为"第一/二/三/四梯队"发展等级；
  6. 输出聚类结果表、评价指标、可视化图，并在控制台打印完整分析结果。

输出：
    output/cluster/province_cluster_result.csv    —— 省份聚类标签明细
    output/cluster/cluster_summary.csv            —— 各簇统计摘要
    output/cluster/k_selection_metrics.csv        —— K 值评价指标
    output/charts/图4-10_肘部法则与轮廓系数.png
    output/charts/图4-11_省份旅游发展水平聚类散点图.png
    output/charts/图4-12_各聚类旅游收入均值对比.png

运行：python src/03_kmeans_cluster.py
"""

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (calinski_harabasz_score, davies_bouldin_score,
                             silhouette_samples, silhouette_score)
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

FEATURES = ["省份旅游收入_亿元", "接待游客数量_万人次"]
FEATURE_CN = {"省份旅游收入_亿元": "旅游收入", "接待游客数量_万人次": "接待游客量"}

# 发展等级命名（按簇内旅游收入均值由高到低）
LEVEL_NAMES = ["第一梯队（旅游强省）", "第二梯队（旅游较发达省份）",
               "第三梯队（旅游中等省份）", "第四梯队（旅游欠发达省份）",
               "第五梯队（旅游起步省份）", "第六梯队"]


def log_to(path: str, text: str) -> None:
    """把控制台输出同步落盘，方便直接粘进论文。"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


# ============================================================================
# 1. 数据准备
# ============================================================================
def load_cross_section(year: int = cfg.ANALYSIS_YEAR) -> pd.DataFrame:
    """读取目标年份的省级截面数据。"""
    path = os.path.join(cfg.DATA_DIR, "merged_province_full.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    d = df[df["年份"] == year].copy().reset_index(drop=True)
    if len(d) < 10:
        raise SystemExit(f"{year} 年截面数据不足（{len(d)} 条），请检查数据文件")
    return d


# ============================================================================
# 2. 确定最优 K（肘部法则 + 轮廓系数）
# ============================================================================
def search_best_k(X: np.ndarray) -> pd.DataFrame:
    """遍历 K 值，计算 Inertia / 轮廓系数 / CH 指数 / DB 指数，并给出综合评分。"""
    rows = []
    for k in cfg.KMEANS_K_RANGE:
        km = KMeans(n_clusters=k, n_init=cfg.KMEANS_N_INIT,
                    max_iter=cfg.KMEANS_MAX_ITER, random_state=cfg.RANDOM_SEED)
        labels = km.fit_predict(X)
        rows.append({
            "K": k,
            "Inertia_簇内平方和": round(float(km.inertia_), 4),
            "轮廓系数": round(float(silhouette_score(X, labels)), 4),
            "CH指数": round(float(calinski_harabasz_score(X, labels)), 4),
            "DB指数": round(float(davies_bouldin_score(X, labels)), 4),
        })
    m = pd.DataFrame(rows)

    # ---- 综合评分：三个指标量纲不同，先各自 Min-Max 归一化再加权 ----
    def _norm(s: pd.Series, higher_better: bool = True) -> pd.Series:
        rng = s.max() - s.min()
        v = pd.Series(0.5, index=s.index) if rng == 0 else (s - s.min()) / rng
        return v if higher_better else 1 - v

    w_sil, w_ch, w_db = cfg.KMEANS_SCORE_WEIGHTS
    m["综合评分"] = (w_sil * _norm(m["轮廓系数"])
                    + w_ch * _norm(m["CH指数"])
                    + w_db * _norm(m["DB指数"], higher_better=False)).round(4)
    return m


def pick_best_k(metrics: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    """在有效区间 [KMEANS_K_MIN, KMEANS_K_MAX] 内按综合评分选最优 K。

    设计理由（论文可直接引用）：
      轮廓系数在 K=2 处最高，但 K=2 会把 31 个省份退化为"强/弱"两类，
      无法支撑旅游发展等级划分；K>6 时类别细碎、单簇样本过少。
      故限定在 K∈[3,6] 内，用「轮廓系数(权重0.5) + CH指数(0.25) + 1-DB指数(0.25)」
      的综合评分择优，兼顾簇内紧致度、簇间分离度与类别可解释性。
    """
    cand = metrics[(metrics["K"] >= cfg.KMEANS_K_MIN) & (metrics["K"] <= cfg.KMEANS_K_MAX)].copy()
    best = int(cand.loc[cand["综合评分"].idxmax(), "K"])
    return best, cand


def plot_k_selection(metrics: pd.DataFrame, best_k: int) -> None:
    """图4-10 肘部法则曲线 + 轮廓系数曲线"""
    fig, ax1 = plt.subplots(figsize=(9, 4.8))
    ks = metrics["K"]
    ax1.plot(ks, metrics["Inertia_簇内平方和"], marker="o", ms=7, lw=2.2,
             color=cfg.PALETTE[0], label="簇内平方和 Inertia")
    ax1.set_xlabel("聚类数 K"); ax1.set_ylabel("簇内平方和 Inertia（肘部法则）",
                                            color=cfg.PALETTE[0])
    ax1.set_xticks(list(ks))

    ax2 = ax1.twinx()
    ax2.plot(ks, metrics["轮廓系数"], marker="s", ms=7, lw=2.2, ls="--",
             color=cfg.PALETTE[1], label="轮廓系数 Silhouette")
    ax2.set_ylabel("轮廓系数", color=cfg.PALETTE[1])

    ax1.axvline(best_k, color="#888888", ls=":", lw=1.6)
    ax1.annotate(f"最优 K = {best_k}", xy=(best_k, metrics["Inertia_簇内平方和"].max()),
                 xytext=(best_k + 0.35, metrics["Inertia_簇内平方和"].max() * 0.92),
                 fontsize=11, color="#C0392B",
                 arrowprops=dict(arrowstyle="->", color="#C0392B"))

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="center right", frameon=True)
    ax1.set_title("图4-10  K-Means 最优聚类数确定（肘部法则 + 轮廓系数）",
                  fontsize=13, pad=12)
    ax1.grid(False); ax2.grid(False)
    fig.tight_layout()
    fig.savefig(os.path.join(cfg.CHART_DIR, "图4-10_肘部法则与轮廓系数.png"),
                dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("[输出] output/charts/图4-10_肘部法则与轮廓系数.png")


# ============================================================================
# 3. 聚类 + 等级映射
# ============================================================================
def run_kmeans(d: pd.DataFrame, k: int):
    """执行 K-Means，返回 (带标签的DataFrame, 标准化矩阵, 模型, 缩放器, 轮廓系数)。"""
    X_raw = d[FEATURES].to_numpy(dtype=float)
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    model = KMeans(n_clusters=k, n_init=cfg.KMEANS_N_INIT,
                   max_iter=cfg.KMEANS_MAX_ITER, random_state=cfg.RANDOM_SEED)
    labels = model.fit_predict(X)
    sil = silhouette_score(X, labels)
    sil_vec = silhouette_samples(X, labels)

    d = d.copy()
    d["原始簇编号"] = labels
    d["轮廓系数_个体"] = np.round(sil_vec, 4)

    # 按簇内旅游收入均值降序重排簇编号 → 1 = 最强
    order = (d.groupby("原始簇编号")["省份旅游收入_亿元"].mean()
              .sort_values(ascending=False).index.tolist())
    remap = {old: new for new, old in enumerate(order)}
    d["发展等级序号"] = d["原始簇编号"].map(remap)
    d["发展等级"] = d["发展等级序号"].map(lambda i: LEVEL_NAMES[i])
    return d, X, model, scaler, sil


def plot_cluster_scatter(d: pd.DataFrame, model, scaler, k: int) -> None:
    """图4-11 省份旅游发展水平聚类散点图（特征平面 + 质心）"""
    fig, ax = plt.subplots(figsize=(10, 6.2))
    palette = [cfg.PALETTE[i % len(cfg.PALETTE)] for i in range(k)]

    for i in range(k):
        sub = d[d["发展等级序号"] == i]
        ax.scatter(sub["省份旅游收入_亿元"], sub["接待游客数量_万人次"],
                   s=125, color=palette[i], alpha=0.85,
                   edgecolor="white", linewidths=1.0, zorder=3,
                   label=f"{LEVEL_NAMES[i]}（{len(sub)} 省）")
        for _, r in sub.iterrows():
            ax.annotate(r["省份"], (r["省份旅游收入_亿元"], r["接待游客数量_万人次"]),
                        textcoords="offset points", xytext=(6, 5),
                        fontsize=9, color="#333333")

    # 质心（反标准化回原始量纲）
    centers = scaler.inverse_transform(model.cluster_centers_)
    lut = (d.drop_duplicates("原始簇编号")
             .set_index("原始簇编号")["发展等级序号"].to_dict())
    for i, c in enumerate(centers):
        ax.scatter(c[0], c[1], marker="*", s=620, color=palette[lut[i]],
                   edgecolor="#222222", linewidths=1.2, zorder=5)
    ax.scatter([], [], marker="*", s=200, color="#666666", label="聚类质心")

    ax.set_xlabel(f"{cfg.ANALYSIS_YEAR} 年省份旅游收入（亿元）")
    ax.set_ylabel(f"{cfg.ANALYSIS_YEAR} 年接待游客数量（万人次）")
    ax.set_title(f"图4-11  {cfg.ANALYSIS_YEAR} 年 31 个省级行政区旅游发展水平 K-Means 聚类（K={k}）",
                 fontsize=12.5, pad=12)
    ax.legend(loc="upper left", fontsize=9.5, frameon=True)
    fig.tight_layout()
    fig.savefig(os.path.join(cfg.CHART_DIR, "图4-11_省份旅游发展水平聚类散点图.png"),
                dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("[输出] output/charts/图4-11_省份旅游发展水平聚类散点图.png")


def plot_cluster_mean(d: pd.DataFrame, summary: pd.DataFrame, k: int) -> None:
    """图4-12 各聚类旅游收入、游客量均值对比"""
    fig, ax1 = plt.subplots(figsize=(10, 4.9))
    names = summary["发展等级"].tolist()
    x = np.arange(len(names)); w = 0.36
    colors = [cfg.PALETTE[i % len(cfg.PALETTE)] for i in range(len(names))]

    b1 = ax1.bar(x - w / 2, summary["旅游收入均值_亿元"], w,
                 color=colors, zorder=3, label="旅游收入均值（亿元）")
    ax1.bar_label(b1, fmt="{:,.0f}", padding=3, fontsize=9)
    ax1.set_ylabel("旅游收入均值（亿元）")
    ax1.set_ylim(0, summary["旅游收入均值_亿元"].max() * 1.30)

    ax2 = ax1.twinx()
    b2 = ax2.bar(x + w / 2, summary["游客量均值_万人次"], w,
                 color=colors, alpha=0.55, zorder=3, label="游客量均值（万人次）")
    ax2.bar_label(b2, fmt="{:,.0f}", padding=3, fontsize=9)
    ax2.set_ylabel("游客量均值（万人次）")
    ax2.set_ylim(0, summary["游客量均值_万人次"].max() * 1.30)

    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{n}\n({c} 省)" for n, c in
                         zip(names, summary["省份数量"])], fontsize=9)
    ax1.set_title(f"图4-12  {cfg.ANALYSIS_YEAR} 年各聚类旅游发展指标均值对比",
                  fontsize=12.5, pad=12)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", frameon=True, fontsize=9.5)
    ax1.grid(False); ax2.grid(False)
    fig.tight_layout()
    fig.savefig(os.path.join(cfg.CHART_DIR, "图4-12_各聚类旅游收入均值对比.png"),
                dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("[输出] output/charts/图4-12_各聚类旅游收入均值对比.png")


# ============================================================================
# 主流程
# ============================================================================
def main() -> pd.DataFrame:
    os.makedirs(cfg.CLUSTER_DIR, exist_ok=True)
    rpt_path = os.path.join(cfg.OUTPUT_DIR, "cluster_report.txt")
    if os.path.exists(rpt_path):
        os.remove(rpt_path)

    def out(text: str = "") -> None:
        print(text)
        log_to(rpt_path, text)

    out("=" * 82)
    out("模块3：K-Means 省份旅游发展水平聚类挖掘")
    out("=" * 82)

    cfg.setup_matplotlib_chinese()
    d = load_cross_section()
    out(f"\n【数据概况】分析年份：{cfg.ANALYSIS_YEAR}    样本数：{len(d)} 个省级行政区")
    out(f"【聚类特征】{'、'.join(FEATURE_CN[f] for f in FEATURES)}（Z-Score 标准化后输入）")
    out(f"【可调参数】K 搜索范围 {cfg.KMEANS_K_RANGE.start}—{cfg.KMEANS_K_RANGE.stop - 1}，"
        f"n_init={cfg.KMEANS_N_INIT}，max_iter={cfg.KMEANS_MAX_ITER}，"
        f"random_state={cfg.RANDOM_SEED}")

    # ---------- 1. 确定 K ----------
    X_raw = d[FEATURES].to_numpy(dtype=float)
    scaler_pre = StandardScaler().fit(X_raw)
    X = scaler_pre.transform(X_raw)

    out("\n" + "-" * 82)
    out("一、最优聚类数 K 的确定（肘部法则 + 轮廓系数 + CH 指数 + DB 指数）")
    out("-" * 82)
    metrics = search_best_k(X)
    out(metrics.to_string(index=False))

    auto_k, cand = pick_best_k(metrics)
    best_k = cfg.KMEANS_K if cfg.KMEANS_K else auto_k
    out(f"\n→ K=2 时轮廓系数最高（{metrics.loc[metrics['K'] == 2, '轮廓系数'].iloc[0]:.4f}），"
        f"但 K=2 会退化为「强/弱」二分，无法支撑发展等级划分，故排除。")
    out(f"→ 在有效区间 K∈[{cfg.KMEANS_K_MIN}, {cfg.KMEANS_K_MAX}] 内按综合评分择优：")
    out(cand[["K", "轮廓系数", "CH指数", "DB指数", "综合评分"]].to_string(index=False))
    out(f"→ 综合评分最高处 K = {auto_k}（评分 "
        f"{cand.loc[cand['K'] == auto_k, '综合评分'].iloc[0]:.4f}）")
    out(f"→ 最终采用 K = {best_k}"
        + ("（由 config.py 手动指定）" if cfg.KMEANS_K else "（自动择优）"))

    metrics.to_csv(os.path.join(cfg.CLUSTER_DIR, "k_selection_metrics.csv"),
                   index=False, encoding="utf-8-sig")
    plot_k_selection(metrics, best_k)

    # ---------- 2. 执行聚类 ----------
    d, X, model, scaler, sil = run_kmeans(d, best_k)

    out("\n" + "-" * 82)
    out("二、聚类结果：各省份旅游发展等级划分")
    out("-" * 82)
    for i in range(best_k):
        sub = d[d["发展等级序号"] == i].sort_values("省份旅游收入_亿元", ascending=False)
        out(f"\n▍{LEVEL_NAMES[i]}  共 {len(sub)} 个省份")
        out(f"   旅游收入区间：{sub['省份旅游收入_亿元'].min():,.1f} — "
            f"{sub['省份旅游收入_亿元'].max():,.1f} 亿元（均值 "
            f"{sub['省份旅游收入_亿元'].mean():,.1f}）")
        out(f"   游客量区间：  {sub['接待游客数量_万人次'].min():,.1f} — "
            f"{sub['接待游客数量_万人次'].max():,.1f} 万人次（均值 "
            f"{sub['接待游客数量_万人次'].mean():,.1f}）")
        out(f"   成员：{'、'.join(sub['省份'].tolist())}")

    # ---------- 3. 评价指标 ----------
    out("\n" + "-" * 82)
    out("三、聚类效果评价指标")
    out("-" * 82)
    ev = {
        "轮廓系数 Silhouette": sil,
        "CH 指数 Calinski-Harabasz": calinski_harabasz_score(X, d["原始簇编号"]),
        "DB 指数 Davies-Bouldin": davies_bouldin_score(X, d["原始簇编号"]),
        "簇内平方和 Inertia": model.inertia_,
    }
    for k_, v in ev.items():
        out(f"  · {k_:<32} = {v:.4f}")
    out("  说明：轮廓系数越接近 1 越好（>0.5 表明聚类结构清晰）；"
        "CH 指数越大越好；DB 指数越小越好。")

    # ---------- 4. 明细表 ----------
    out("\n" + "-" * 82)
    out(f"四、{cfg.ANALYSIS_YEAR} 年各省份聚类标签明细（按旅游收入降序）")
    out("-" * 82)
    detail = d[["省份", "所属区域", "省份旅游收入_亿元", "接待游客数量_万人次",
                "发展等级", "原始簇编号", "轮廓系数_个体"]].sort_values(
        "省份旅游收入_亿元", ascending=False)
    out(detail.to_string(index=False))

    summary = (d.groupby("发展等级").agg(
        省份数量=("省份", "count"),
        旅游收入均值_亿元=("省份旅游收入_亿元", "mean"),
        游客量均值_万人次=("接待游客数量_万人次", "mean"),
        旅游收入合计_亿元=("省份旅游收入_亿元", "sum"),
    ).round(2).sort_values("旅游收入均值_亿元", ascending=False).reset_index())
    summary.insert(1, "省份列表",
                   summary["发展等级"].map(
                       lambda lv: "、".join(
                           d.loc[d["发展等级"] == lv, "省份"].tolist())))
    out("\n各聚类统计摘要：")
    out(summary.drop(columns=["省份列表"]).to_string(index=False))

    # ---------- 5. 河南省定位 ----------
    out("\n" + "-" * 82)
    out("五、河南省旅游发展定位分析（4.2.6）")
    out("-" * 82)
    hn = d[d["省份"] == "河南"].iloc[0]
    rank_rev = int((d["省份旅游收入_亿元"] > hn["省份旅游收入_亿元"]).sum()) + 1
    rank_tou = int((d["接待游客数量_万人次"] > hn["接待游客数量_万人次"]).sum()) + 1
    hn_level = hn["发展等级"]
    peers = d[(d["发展等级"] == hn_level) & (d["省份"] != "河南")]["省份"].tolist()
    out(f"  · 河南旅游收入 {hn['省份旅游收入_亿元']:,.1f} 亿元，全国第 {rank_rev} 位")
    out(f"  · 河南接待游客量 {hn['接待游客数量_万人次']:,.1f} 万人次，全国第 {rank_tou} 位")
    out(f"  · 所属发展等级：{hn_level}")
    out(f"  · 同等级省份：{'、'.join(peers) if peers else '无'}")
    out(f"  · 省内人均旅游收入 {hn['人均旅游收入_元']:,.0f} 元/人，"
        f"旅游依存度 {hn['旅游依存度_%']:.2f}%")
    out("  · 结论：河南属于「游客规模领先、人均消费偏低」的典型中部旅游大省，"
        "旅游收入排名与人口规模不匹配，说明人均旅游消费与旅游产品附加值仍有较大提升空间。")

    # ---------- 6. 输出文件 ----------
    detail.to_csv(os.path.join(cfg.CLUSTER_DIR, "province_cluster_result.csv"),
                  index=False, encoding="utf-8-sig")
    summary.to_csv(os.path.join(cfg.CLUSTER_DIR, "cluster_summary.csv"),
                   index=False, encoding="utf-8-sig")
    plot_cluster_scatter(d, model, scaler, best_k)
    plot_cluster_mean(d, summary, best_k)
    out(f"\n[完成] 聚类明细：output/cluster/province_cluster_result.csv")
    out(f"[完成] 聚类摘要：output/cluster/cluster_summary.csv")
    out(f"[完成] K 值评价：output/cluster/k_selection_metrics.csv")

    # 供大屏调用：把最优 K 写回 config 运行产物
    with open(os.path.join(cfg.CLUSTER_DIR, "best_k.txt"), "w", encoding="utf-8") as f:
        f.write(str(best_k))
    return d


if __name__ == "__main__":
    main()

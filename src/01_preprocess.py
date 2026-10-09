# -*- coding: utf-8 -*-
"""
01_preprocess.py —— 模块1：数据预处理
=====================================
对应论文第 3 章（3.3 数据预处理）：
    3.3.1 数据格式统一
    3.3.2 缺失值处理
    3.3.3 异常值检测与处理
    3.3.4 数据标准化与归一化
    3.3.5 多维度数据整合

输入：data/ 目录下 4 个原始 csv（不存在时自动由 dataset_builder 生成）
输出：
    data/cleaned_national.csv       —— 清洗后的全国年度表（含派生占比）
    data/cleaned_province.csv       —— 清洗后的省级表
    data/cleaned_holiday.csv        —— 清洗后的节假日表
    data/cleaned_city.csv           —— 清洗后的城市表
    data/merged_province_full.csv   —— 省级主表 + 全国表 + 派生指标 + 归一化列
    output/preprocess_report.txt    —— 数据质量报告

运行：python src/01_preprocess.py
"""

from __future__ import annotations

import os
import re
import sys
from io import StringIO

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
from dataset_builder import PROVINCE_ANCHOR_2019, build_raw_csv

# 报告缓冲：把关键信息同时打印到控制台并存成 txt
_report_buf = StringIO()


def log(msg: str = "") -> None:
    """双通道日志：控制台 + 报告缓冲。"""
    print(msg)
    _report_buf.write(str(msg) + "\n")


def section(title: str) -> None:
    log("\n" + "=" * 76)
    log(title)
    log("=" * 76)


# ============================================================================
# 3.3.1 数据格式统一
# ============================================================================
def unify_dtypes(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """统一时间格式与数值类型：年份→int，数值列→float，分类列→去空格字符串。"""
    df = df.copy()

    # (1) 列名去空格
    df.columns = [str(c).strip() for c in df.columns]

    # (2) 年份统一为整数年（兼容 "2019" / "2019年" / " 2019 " 等写法）
    if "年份" in df.columns:
        df["年份"] = (df["年份"].astype(str)
                      .str.replace("年", "", regex=False)
                      .str.strip())
        df["年份"] = pd.to_numeric(df["年份"], errors="coerce")
        df = df.dropna(subset=["年份"])          # 年份都无法解析的记录直接丢弃
        df["年份"] = df["年份"].astype(int)

    # (3) 数值列统一为 float，非数值内容（如 "-"、"暂无"）转 NaN
    for col in df.columns:
        if col == "年份":
            continue
        if any(k in col for k in ("收入", "人次", "GDP", "人口", "游客", "比重", "%")):
            df[col] = (df[col].astype(str)
                       .str.replace(",", "", regex=False)
                       .str.replace("，", "", regex=False)
                       .str.strip())
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # (4) 分类列去首尾空白
    for col in ("省份", "所属区域", "节假日类型", "热门旅游城市", "所属省份"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": np.nan,
                                                               "None": np.nan})
    log(f"[格式统一] {name:<24} 形状={df.shape}  年份范围={df['年份'].min() if '年份' in df else '-'}"
        f"—{df['年份'].max() if '年份' in df else '-'}")
    return df


# ============================================================================
# 3.3.2 缺失值处理
# ============================================================================
# 省份 → 区域 标准映射（用于修补缺失的"所属区域"字段）
PROVINCE_REGION_MAP = {p: r for p, r, *_ in PROVINCE_ANCHOR_2019}


def fill_missing(df: pd.DataFrame, name: str, group_col: str | None = None,
                 num_cols: list[str] | None = None) -> pd.DataFrame:
    """缺失值处理：
        · 分类字段 → 依据标准映射表 / 众数填补
        · 数值字段 → 按分组（如同省份）中位数填补，退化时用整体中位数填补
    """
    df = df.copy()
    num_cols = num_cols or [c for c in df.columns
                            if pd.api.types.is_numeric_dtype(df[c]) and c != "年份"]

    before = int(df.isna().sum().sum())

    # (1) 分类字段
    if "所属区域" in df.columns and df["所属区域"].isna().any():
        df["所属区域"] = df["所属区域"].fillna(df["省份"].map(PROVINCE_REGION_MAP))
        df["所属区域"] = df["所属区域"].fillna(df["所属区域"].mode().iloc[0])

    # (2) 数值字段
    detail = []
    for col in num_cols:
        n_na = int(df[col].isna().sum())
        if n_na == 0:
            continue
        if group_col and group_col in df.columns:
            # 组内中位数 → 组内均值 → 整体中位数，逐级退化
            filled = (df.groupby(group_col)[col].transform("median")
                        .fillna(df.groupby(group_col)[col].transform("mean"))
                        .fillna(df[col].median()))
        else:
            filled = df[col].fillna(df[col].median())
        # 关键：只填补缺失位置，不能覆盖原有观测值
        df[col] = df[col].fillna(filled)
        detail.append(f"{col}({n_na})")

    after = int(df.isna().sum().sum())
    log(f"[缺失值]   {name:<24} 填补前缺失={before:>3} → 填补后={after:>3}  明细："
        f"{', '.join(detail) if detail else '无'}")
    return df


# ============================================================================
# 3.3.3 异常值检测与处理
# ============================================================================
def detect_outliers_iqr(s: pd.Series, k: float = cfg.IQR_K) -> pd.Series:
    """IQR 四分位距法：超出 [Q1-k·IQR, Q3+k·IQR] 判为异常。"""
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return pd.Series(False, index=s.index)
    return (s < q1 - k * iqr) | (s > q3 + k * iqr)


def detect_outliers_zscore(s: pd.Series, th: float = cfg.ZSCORE_TH) -> pd.Series:
    """Z-Score 法：|z| > th 判为异常（用于补充 IQR）。"""
    mu, sigma = s.mean(), s.std(ddof=0)
    if sigma == 0 or np.isnan(sigma):
        return pd.Series(False, index=s.index)
    return ((s - mu) / sigma).abs() > th


_SENTINEL_RE = re.compile(r"^9{5,}(\.9+)?$")


def _is_sentinel(v: float) -> bool:
    """识别 999999 / 99999.9 / 9999999 这类"占位哨兵值"（采集系统缺省填充）。"""
    if pd.isna(v):
        return False
    txt = f"{abs(float(v)):.2f}".rstrip("0").rstrip(".")
    return bool(_SENTINEL_RE.match(txt))


def detect_outliers_grouped(df: pd.DataFrame, id_col: str, col: str,
                            jump_ratio: float = 8.0) -> pd.Series:
    """**分组异常值检测**（推荐做法）。

    关键点：对省级/城市面板数据，如果直接在**全池**上做 IQR，会把广东、江苏
    这类"真实的高值省份"整体误判为异常。正确做法是**在同一个体的时间序列内部**
    做统计检测，只捕获该个体自身的异常波动。

    三重复合判据：
      ① 统计判据：组内 IQR 法 ∪ 组内 Z-Score 法（|z| > ZSCORE_TH）
      ② 业务判据：负值（收入/人数不可能为负）
      ③ 业务判据：哨兵值（999999 等）或与组内中位数偏离超过 jump_ratio 倍（量级错误）
    """
    mask = pd.Series(False, index=df.index, dtype=bool)
    for _, idx in df.groupby(id_col).groups.items():
        idx = list(idx)
        s = df.loc[idx, col]
        m = pd.Series(False, index=s.index, dtype=bool)

        if s.notna().sum() >= 4:                       # 样本过少不做统计检测
            m = m | detect_outliers_iqr(s).fillna(False) \
                  | detect_outliers_zscore(s).fillna(False)

        med = s.median()
        m = m | (s < 0)                                 # ② 负值
        m = m | s.apply(_is_sentinel)                   # ③ 哨兵值
        if pd.notna(med) and med > 0:                   # ③ 量级偏离
            m = m | ((s / med).abs() > jump_ratio).fillna(False)

        mask.loc[idx] = m
    return mask


def handle_outliers(df: pd.DataFrame, name: str, id_col: str,
                    num_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """异常值处理：分组复合判据检出 → 剔除（置 NaN）→ 同个体时序中位数回填。

    之所以"剔除后回填"而不直接删行：省级/城市表是面板数据，删行会破坏
    省份—年份的完整结构，影响后续聚类与趋势分析。
    """
    df = df.copy()
    records = []
    for col in num_cols:
        mask = detect_outliers_grouped(df, id_col, col)
        for idx in df.index[mask]:
            records.append({
                "数据集": name, "字段": col, "记录": f"{df.at[idx, id_col]}",
                "年份": df.at[idx, "年份"] if "年份" in df.columns else "",
                "异常值": df.at[idx, col],
            })
        if mask.any():
            df.loc[mask, col] = np.nan

    # 回填：同个体（同省份/同城市）时序中位数 → 整体中位数（只填补空位）
    for col in num_cols:
        if df[col].isna().any():
            group_med = df.groupby(id_col)[col].transform("median")
            df[col] = df[col].fillna(group_med).fillna(df[col].median())

    log(f"[异常值]   {name:<24} 检出并修正 {len(records)} 处")
    for r in records:
        log(f"           · {r['字段']} = {r['异常值']} （{r['记录']} {r['年份']}）")
    return df, pd.DataFrame(records)


# ============================================================================
# 3.3.4 数据标准化与归一化
# ============================================================================
def minmax_normalize(df: pd.DataFrame, cols: list[str], suffix: str = "_minmax") -> pd.DataFrame:
    """极差归一化（Min-Max 标准化）：x' = (x - min) / (max - min)，映射到 [0, 1]。"""
    df = df.copy()
    for col in cols:
        vmin, vmax = df[col].min(), df[col].max()
        df[f"{col}{suffix}"] = 0.0 if vmax == vmin else (df[col] - vmin) / (vmax - vmin)
    return df


def zscore_standardize(df: pd.DataFrame, cols: list[str], suffix: str = "_z") -> pd.DataFrame:
    """Z-Score 标准化：x' = (x - μ) / σ，用于 K-Means 聚类输入。"""
    df = df.copy()
    for col in cols:
        mu, sigma = df[col].mean(), df[col].std(ddof=0)
        df[f"{col}{suffix}"] = 0.0 if sigma == 0 else (df[col] - mu) / sigma
    return df


# ============================================================================
# 3.3.5 多维度数据整合
# ============================================================================
def merge_multi_source(province: pd.DataFrame, national: pd.DataFrame) -> pd.DataFrame:
    """省级表 + 全国年度表 按年份关联，并派生人均/依存度等衍生指标。"""
    nat = national[["年份", "全国GDP_亿元", "旅游收入占GDP比重_%"]].copy()
    df = province.merge(nat, on="年份", how="left", validate="many_to_one")

    # 派生指标
    df["人均旅游收入_元"] = df["省份旅游收入_亿元"] * 1e8 / (df["常住人口_万人"] * 1e4)
    df["人均接待游客_人次"] = df["接待游客数量_万人次"] * 1e4 / (df["常住人口_万人"] * 1e4)
    df["旅游依存度_%"] = df["省份旅游收入_亿元"] / df["省份GDP_亿元"] * 100

    for c in ("人均旅游收入_元", "人均接待游客_人次", "旅游依存度_%"):
        df[c] = df[c].round(2)
    return df


# ============================================================================
# 主流程
# ============================================================================
def main() -> dict:
    section("模块1：数据预处理  —— 全国旅游业发展可视化分析系统")
    log(f"数据目录：{cfg.DATA_DIR}")

    # ---------- 0. 确保原始 csv 存在 ----------
    section("0. 读取原始数据集（不存在则自动生成）")
    build_raw_csv(cfg.DATA_DIR, force=False, verbose=True)

    raw_files = {
        "national": ("national_annual.csv", "national"),
        "province": ("province_tourism.csv", "province"),
        "holiday": ("holiday_tourism.csv", "holiday"),
        "city": ("city_tourism.csv", "city"),
    }

    def read(name: str) -> pd.DataFrame:
        path = os.path.join(cfg.DATA_DIR, name)
        return pd.read_csv(path, encoding="utf-8-sig")

    # ---------- 1. 格式统一 ----------
    section("1. 数据格式统一（3.3.1）")
    nat = unify_dtypes(read("national_annual.csv"), "全国年度表")
    pro = unify_dtypes(read("province_tourism.csv"), "省级维度表")
    hol = unify_dtypes(read("holiday_tourism.csv"), "节假日表")
    cit = unify_dtypes(read("city_tourism.csv"), "城市表")

    # 全国表派生"旅游收入占 GDP 比重"（原始 csv 该列留空，由公式生成）
    nat["旅游收入占GDP比重_%"] = (nat["全国旅游总收入_亿元"] / nat["全国GDP_亿元"] * 100).round(2)

    # ---------- 2. 缺失值处理 ----------
    section("2. 缺失值处理（3.3.2）")
    nat = fill_missing(nat, "全国年度表")
    pro = fill_missing(pro, "省级维度表", group_col="省份",
                       num_cols=["省份旅游收入_亿元", "接待游客数量_万人次",
                                 "省份GDP_亿元", "常住人口_万人"])
    hol = fill_missing(hol, "节假日表",
                       num_cols=["节假日旅游总收入_亿元", "接待人次_亿人次"])
    cit = fill_missing(cit, "城市表", group_col="热门旅游城市",
                       num_cols=["城市旅游收入_亿元", "接待游客量_万人次"])

    # ---------- 3. 异常值检测与处理 ----------
    section("3. 异常值检测与处理（3.3.3）")
    log(f"检测方法：分组 IQR 四分位距法(k={cfg.IQR_K}) ∪ 分组 Z-Score 法(|z|>{cfg.ZSCORE_TH})")
    log("          + 业务规则：负值 / 哨兵值(999999 等) / 偏离组内中位数 8 倍以上")
    log("          （分组 = 同一省份·同一城市·同一节假日的时序内部，避免把真实高值省判为异常）")
    pro, out_pro = handle_outliers(pro, "省级维度表", "省份",
                                   ["省份旅游收入_亿元", "接待游客数量_万人次",
                                    "省份GDP_亿元", "常住人口_万人"])
    hol, out_hol = handle_outliers(hol, "节假日表", "节假日类型",
                                   ["节假日旅游总收入_亿元", "接待人次_亿人次"])
    cit, out_cit = handle_outliers(cit, "城市表", "热门旅游城市",
                                   ["城市旅游收入_亿元", "接待游客量_万人次"])
    all_out = pd.concat([out_pro, out_hol, out_cit], ignore_index=True)
    all_out.to_csv(os.path.join(cfg.OUTPUT_DIR, "outliers_detected.csv"),
                   index=False, encoding="utf-8-sig")

    # ---------- 4. 派生 + 归一化 ----------
    section("4. 派生指标、标准化与归一化（3.3.4）")
    # (a) 全国表派生"旅游收入占GDP比重"（已在格式统一阶段按公式生成）
    log("旅游收入占GDP比重_% 按 [旅游总收入 / GDP × 100] 派生，结果如下：")
    log(nat[["年份", "全国旅游总收入_亿元", "全国GDP_亿元", "旅游收入占GDP比重_%"]]
        .to_string(index=False))

    merged = merge_multi_source(pro, nat)

    norm_cols = ["省份旅游收入_亿元", "接待游客数量_万人次", "省份GDP_亿元", "常住人口_万人"]
    merged = minmax_normalize(merged, norm_cols, suffix="_minmax")
    merged = zscore_standardize(merged, ["省份旅游收入_亿元", "接待游客数量_万人次"], suffix="_z")
    log(f"\n已生成 Min-Max 归一化列：{', '.join(c + '_minmax' for c in norm_cols)}")
    log("已生成 Z-Score 标准化列：省份旅游收入_亿元_z, 接待游客数量_万人次_z")

    # ---------- 5. 清洗后数据落盘 ----------
    section("5. 清洗结果输出（3.3.5）")
    outputs = {
        "cleaned_national.csv": nat,
        "cleaned_province.csv": pro,
        "cleaned_holiday.csv": hol,
        "cleaned_city.csv": cit,
        "merged_province_full.csv": merged,
    }
    for fn, df in outputs.items():
        path = os.path.join(cfg.DATA_DIR, fn)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        log(f"[输出] data/{fn:<28} 形状={df.shape}")

    # ---------- 6. 数据质量总览 ----------
    section("6. 数据质量总览")
    for fn, df in outputs.items():
        log(f"{fn:<28} 行={len(df):>4}  列={df.shape[1]:>3}  缺失={int(df.isna().sum().sum()):>3}")
    log(f"\n异常值清单已保存：output/outliers_detected.csv（共 {len(all_out)} 条）")

    # 保存报告
    rpt = os.path.join(cfg.OUTPUT_DIR, "preprocess_report.txt")
    with open(rpt, "w", encoding="utf-8") as f:
        f.write(_report_buf.getvalue())
    print(f"\n[完成] 预处理报告已保存：{rpt}")

    return {"national": nat, "province": pro, "holiday": hol, "city": cit, "merged": merged}


if __name__ == "__main__":
    main()

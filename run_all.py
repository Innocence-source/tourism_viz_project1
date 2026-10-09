# -*- coding: utf-8 -*-
"""
run_all.py —— 一键运行入口
==========================
按依赖顺序依次执行全部 4 个模块，任何一步失败即中断并给出提示。

    python run_all.py

执行链路：
    00 数据集构建（内置数据 → data/*.csv，仅首次生成）
    01 数据预处理      → data/cleaned_*.csv、data/merged_province_full.csv
    02 统计分析绘图     → output/charts/图4-1 ~ 图4-9
    03 K-Means 聚类     → output/cluster/*、output/charts/图4-10 ~ 图4-12
    04 可视化大屏       → output/全国旅游业发展可视化分析大屏.html

可用参数：
    python run_all.py --force-data    # 强制重建原始 csv（会覆盖 data/ 下原始表）
    python run_all.py --skip-data     # 跳过数据预处理，直接从绘图开始
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
sys.path.insert(0, SRC)


def load(module_file: str, module_name: str):
    """按文件路径动态加载模块（模块名以数字开头，无法用 import 语句）。"""
    spec = importlib.util.spec_from_file_location(module_name,
                                                  os.path.join(SRC, module_file))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def banner(step: str, title: str) -> None:
    print("\n" + "#" * 78)
    print(f"#  {step}  {title}")
    print("#" * 78)


def main() -> None:
    argv = sys.argv[1:]
    force_data = "--force-data" in argv
    skip_data = "--skip-data" in argv

    t0 = time.time()
    print("=" * 78)
    print("  基于Python的全国旅游业发展可视化分析系统 —— 一键运行")
    print(f"  项目根目录：{HERE}")
    print("=" * 78)

    # ---------------- 00 数据集构建 ----------------
    banner("STEP 00", "数据集构建（内置数据 → csv）")
    builder = load("dataset_builder.py", "dataset_builder")
    builder.build_raw_csv(builder.DATA_DIR, force=force_data, verbose=True)

    # ---------------- 01 数据预处理 ----------------
    if skip_data:
        print("\n[跳过] 已指定 --skip-data，跳过数据预处理")
    else:
        banner("STEP 01", "数据预处理（模块1 / 论文第3章）")
        load("01_preprocess.py", "preprocess").main()

    # ---------------- 02 统计分析 ----------------
    banner("STEP 02", "统计分析绘图（模块2 / 论文第4章 4.1—4.5）")
    load("02_analysis_charts.py", "analysis").main()

    # ---------------- 03 聚类挖掘 ----------------
    banner("STEP 03", "K-Means 聚类挖掘（模块3 / 论文 4.2.5）")
    load("03_kmeans_cluster.py", "kmeans").main()

    # ---------------- 04 可视化大屏 ----------------
    banner("STEP 04", "交互式可视化大屏（模块4 / 论文第5章）")
    html = load("04_dashboard.py", "dashboard").main()

    # ---------------- 汇总 ----------------
    print("\n" + "=" * 78)
    print(f"  全部完成，耗时 {time.time() - t0:.1f} 秒")
    print("=" * 78)
    print("  静态分析图：output/charts/    （共 12 张 png）")
    print("  聚类结果：  output/cluster/   （标签明细 + 摘要 + K 值指标）")
    print("  可视化大屏：output/全国旅游业发展可视化分析大屏.html")
    print("             ↑ 双击该文件即可在浏览器打开（纯静态，无需后端）")
    print("=" * 78)


if __name__ == "__main__":
    main()

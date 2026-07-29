# -*- coding: utf-8 -*-
"""
选股+配比 主入口
串联：多因子打分 → 仓位配置 → 研报生成

用法:
    cd D:\肖老师公开课笔记+代码\FinAssistant
    python competition/run_selection.py

    # 传入 LLM Token 消耗（JiuwenSwarm Agent 调用时）：
    LLM_MODEL=glm-5.1 LLM_INPUT_TOKENS=56443 LLM_OUTPUT_TOKENS=746 \
    LLM_TOTAL_TOKENS=57189 LLM_CACHE_TOKENS=53248 \
    python competition/run_selection.py

输出:
    competition/output/Portfolio.json        — 持仓配比
    competition/output/个股投资研报/*.md      — 个股研报
    competition/output/resource_log.json     — 资源消耗日志
"""

import os
import sys
import time
import json
import psutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stock_scorer import score_all_stocks, print_ranking, ALL_STOCKS
from portfolio_builder import build_full_portfolio, save_portfolio, print_portfolio
from report_generator import save_all_reports, save_summary_report


def collect_resource_log(start_time, step_times, output_dir):
    """收集资源消耗日志
    支持通过环境变量传入 LLM Token 消耗（JiuwenSwarm Agent 调用时设置）：
        LLM_MODEL          — 模型名称，如 glm-5.1
        LLM_INPUT_TOKENS   — 输入 Token 数
        LLM_OUTPUT_TOKENS  — 输出 Token 数
        LLM_TOTAL_TOKENS   — 总 Token 数
        LLM_CACHE_TOKENS   — 缓存 Token 数（可选）
    未设置时默认为 0（纯 Python 脚本模式）。
    """
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    cpu_percent = process.cpu_percent(interval=0.1)

    # 从环境变量读取 LLM Token 消耗
    llm_model = os.environ.get("LLM_MODEL", "")
    input_tokens = int(os.environ.get("LLM_INPUT_TOKENS", "0") or "0")
    output_tokens = int(os.environ.get("LLM_OUTPUT_TOKENS", "0") or "0")
    total_tokens = int(os.environ.get("LLM_TOTAL_TOKENS", "0") or "0")
    cache_tokens = int(os.environ.get("LLM_CACHE_TOKENS", "0") or "0")

    if total_tokens > 0:
        token_info = {
            "note": f"JiuwenSwarm Agent调用{llm_model}大模型，Token消耗来自usage_metadata",
            "model": llm_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cache_tokens": cache_tokens,
        }
    else:
        token_info = {
            "note": "纯Python脚本执行，未调用LLM API，Token消耗为0",
            "total_tokens": 0,
        }

    log = {
        "total_runtime_seconds": round(time.time() - start_time, 2),
        "step_times": {k: round(v, 2) for k, v in step_times.items()},
        "peak_memory_mb": round(mem_info.rss / 1024 / 1024, 2),
        "peak_cpu_percent": cpu_percent,
        "cpu_count": psutil.cpu_count(),
        "token_consumption": token_info,
    }
    log_path = os.path.join(output_dir, "output/resource_log.json")
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"  资源消耗日志: {log_path}")
    return log


def main():
    print("=" * 60)
    print("FinAssistant — 比赛选股+配比")
    print("=" * 60)

    overall_start = time.time()
    step_times = {}

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    report_dir = os.path.join(output_dir, "个股投资研报")
    os.makedirs(report_dir, exist_ok=True)

    # Step 1: 多因子打分
    print(f"\n[Step 1] 对{len(ALL_STOCKS)}只股票进行多因子打分...")
    t1 = time.time()
    results = score_all_stocks()
    step_times['scoring'] = time.time() - t1
    print(f"\n打分完成，耗时 {step_times['scoring']:.1f}秒")

    # 打印排名
    print_ranking(results, top_n=20)

    # Step 2: 仓位配置（全量49只，入选的权重>0，其余=0）
    print("\n[Step 2] 生成仓位配置...")
    t2 = time.time()
    portfolio = build_full_portfolio(results, top_n=8, max_weight=0.20, cash_ratio=0.0)
    step_times['portfolio'] = time.time() - t2
    print_portfolio(portfolio, results)

    # 保存 Portfolio.json（全量49只）
    portfolio_path = os.path.join(output_dir, "Portfolio.json")
    save_portfolio(portfolio, portfolio_path)

    # 生成投资报告.md（与 output 数据保持一致）
    summary_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "投资报告.md")
    save_summary_report(portfolio, results, summary_path)

    # Step 3: 生成全部个股研报
    print("\n[Step 3] 生成全部个股研报...")
    t3 = time.time()
    save_all_reports(results, report_dir)
    step_times['reports'] = time.time() - t3

    # Step 4: 资源消耗日志
    print("\n[Step 4] 记录资源消耗...")
    log = collect_resource_log(overall_start, step_times, output_dir)

    # 完成
    print("\n" + "=" * 60)
    print("完成！输出文件:")
    print(f"  Portfolio.json:   {portfolio_path}")
    print(f"  投资报告:         {summary_path}")
    print(f"  个股研报目录:     {report_dir}")
    print(f"  资源消耗日志:     {os.path.join(output_dir, 'output/resource_log.json')}")
    print(f"  总耗时:           {log['total_runtime_seconds']:.1f}秒")
    print("=" * 60)


if __name__ == '__main__':
    main()

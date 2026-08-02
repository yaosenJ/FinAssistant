# -*- coding: utf-8 -*-
"""
图表生成模块
使用 matplotlib 生成金融分析图表，保存为 PNG 图片供 Markdown 引用
"""

import os
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 中文字体配置
def _setup_chinese_font():
    """配置 matplotlib 中文字体"""
    font_candidates = [
        'SimHei', 'Microsoft YaHei', 'STSong', 'SimSun',
        'Arial Unicode MS', 'WenQuanYi Micro Hei'
    ]
    for font_name in font_candidates:
        try:
            font_path = fm.findfont(fm.FontProperties(family=font_name))
            if font_path and os.path.exists(font_path):
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False
                return font_name
        except Exception:
            continue
    # 如果没找到中文字体，使用默认
    plt.rcParams['axes.unicode_minus'] = False
    return None

_setup_chinese_font()

# 配色方案
COLORS = {
    'primary': '#2563EB',
    'success': '#16A34A',
    'warning': '#F59E0B',
    'danger': '#DC2626',
    'info': '#6366F1',
    'gray': '#9CA3AF',
}

GRADE_COLORS = {
    '优': COLORS['success'],
    '良': COLORS['primary'],
    '中': COLORS['warning'],
    '差': COLORS['danger'],
    '低估': COLORS['success'],
    '合理': COLORS['primary'],
    '偏高': COLORS['warning'],
    '高估': COLORS['danger'],
    '偏多': COLORS['success'],
    '中性': COLORS['gray'],
    '偏空': COLORS['danger'],
    '强势': COLORS['success'],
    '偏强': COLORS['primary'],
    '偏弱': COLORS['warning'],
    '弱势': COLORS['danger'],
    '放量': COLORS['success'],
    '温和放量': COLORS['primary'],
    '温和缩量': COLORS['warning'],
    '缩量': COLORS['danger'],
}


def _save_fig(fig, filepath):
    """保存图表并关闭"""
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    fig.savefig(filepath, dpi=120, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return filepath


def generate_profitability_chart(name, fund, output_dir):
    """生成盈利能力柱状图

    Args:
        name: 股票名称
        fund: 基本面数据 dict
        output_dir: 输出目录

    Returns:
        str: 图片相对路径
    """
    # 银行股用营业利润率，非银行股用毛利率
    margin_name = '毛利率' if fund.get('毛利率') is not None else '营业利润率'
    metrics = [margin_name, '净利率', 'ROE']
    values = [fund.get(m) or 0 for m in metrics]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar(metrics, values, color=[COLORS['primary'], COLORS['info'], COLORS['success'], COLORS['warning']],
                  width=0.6, edgecolor='white')

    # 在柱子上显示数值
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f'{val:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('百分比 (%)')
    ax.set_title(f'{name} 盈利能力指标')
    ax.set_ylim(0, max(values) * 1.2 + 5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3)

    filepath = os.path.join(output_dir, f'{name}_profitability.png')
    return _save_fig(fig, filepath)


def generate_momentum_chart(name, tech, output_dir):
    """生成动量趋势折线图

    Args:
        name: 股票名称
        tech: 技术面数据 dict
        output_dir: 输出目录

    Returns:
        str: 图片相对路径
    """
    periods = ['近5日', '近10日', '近20日']
    pct_5d = tech.get('pct_5d') or 0
    pct_10d = tech.get('pct_10d') or 0
    pct_20d = tech.get('pct_20d') or 0
    values = [pct_5d, pct_10d, pct_20d]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    color = COLORS['success'] if values[-1] >= 0 else COLORS['danger']
    ax.plot(periods, values, marker='o', linewidth=2.5, markersize=8, color=color)
    ax.fill_between(range(len(periods)), values, alpha=0.15, color=color)
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)

    for i, v in enumerate(values):
        ax.annotate(f'{v:+.1f}%', (i, v), textcoords="offset points",
                    xytext=(0, 12), ha='center', fontsize=10, fontweight='bold')

    ax.set_ylabel('收益率 (%)')
    ax.set_title(f'{name} 短期动量趋势')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3)

    filepath = os.path.join(output_dir, f'{name}_momentum.png')
    return _save_fig(fig, filepath)


def generate_valuation_scatter(name, val, output_dir):
    """生成估值散点图（PE分位 vs PB分位）

    Args:
        name: 股票名称
        val: 估值数据 dict
        output_dir: 输出目录

    Returns:
        str: 图片相对路径
    """
    pe_pct = val.get('pe_ttm_percentile') or 50
    pb_pct = val.get('pb_percentile') or 50

    fig, ax = plt.subplots(figsize=(5, 5))

    # 象限背景色
    ax.axhline(y=50, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    ax.axvline(x=50, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)

    # 象限标注
    ax.text(25, 75, '低PE高PB', ha='center', va='center', fontsize=9, color='gray', alpha=0.6)
    ax.text(75, 75, '高PE高PB\n(高估区)', ha='center', va='center', fontsize=9, color=COLORS['danger'], alpha=0.5)
    ax.text(25, 25, '低PE低PB\n(低估区)', ha='center', va='center', fontsize=9, color=COLORS['success'], alpha=0.5)
    ax.text(75, 25, '高PE低PB', ha='center', va='center', fontsize=9, color='gray', alpha=0.6)

    # 绘制散点
    ax.scatter(pe_pct, pb_pct, s=200, c=COLORS['primary'], edgecolors='white', linewidth=2, zorder=5)
    ax.annotate(name, (pe_pct, pb_pct), textcoords="offset points",
                xytext=(10, 10), ha='left', fontsize=10, fontweight='bold')

    ax.set_xlabel('PE_TTM 历史分位 (%)')
    ax.set_ylabel('PB 历史分位 (%)')
    ax.set_title(f'{name} 估值象限图')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(alpha=0.2)

    filepath = os.path.join(output_dir, f'{name}_valuation.png')
    return _save_fig(fig, filepath)


def generate_sector_pie(sector_stats, output_dir):
    """生成板块分布饼图（用于投资报告）

    Args:
        sector_stats: {sector: {'count': int, 'weight': float}, ...}
        output_dir: 输出目录

    Returns:
        str: 图片相对路径
    """
    labels = list(sector_stats.keys())
    weights = [info['weight'] * 100 for info in sector_stats.values()]
    counts = [info['count'] for info in sector_stats.values()]

    display_labels = [f'{l}\n({c}只, {w:.1f}%)' for l, c, w in zip(labels, counts, weights)]

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = plt.cm.Set3(range(len(labels)))
    wedges, texts, autotexts = ax.pie(
        weights, labels=display_labels, autopct='', startangle=90,
        colors=colors, pctdistance=0.85, labeldistance=1.15
    )

    for text in texts:
        text.set_fontsize(9)

    ax.set_title('投资组合板块分布', fontsize=13, fontweight='bold')

    filepath = os.path.join(output_dir, 'sector_distribution.png')
    return _save_fig(fig, filepath)


def generate_top_stocks_bar(selected, output_dir):
    """生成入选股票仓位柱状图（用于投资报告）

    Args:
        selected: [{'name': str, 'weight': float, 'overall_rank': int}, ...]
        output_dir: 输出目录

    Returns:
        str: 图片相对路径
    """
    names = [s['name'] for s in selected]
    weights = [s['weight'] * 100 for s in selected]
    ranks = [s.get('overall_rank', '--') for s in selected]

    fig, ax = plt.subplots(figsize=(max(6, len(names) * 0.8), 4))
    bars = ax.bar(names, weights, color=COLORS['primary'], width=0.6, edgecolor='white')

    for bar, w, r in zip(bars, weights, ranks):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f'{w:.1f}%\n#{r}', ha='center', va='bottom', fontsize=9)

    ax.set_ylabel('仓位占比 (%)')
    ax.set_title('入选股票仓位配置')
    ax.set_ylim(0, max(weights) * 1.3 + 5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.3)
    plt.xticks(rotation=30, ha='right')

    filepath = os.path.join(output_dir, 'portfolio_allocation.png')
    return _save_fig(fig, filepath)


def generate_radar_chart(name, dim_avgs, output_dir):
    """生成多维度雷达图（用于个股研报）

    Args:
        name: 股票名称
        dim_avgs: {'fundamental': float, 'valuation': float, 'technical': float, 'momentum': float, 'risk': float}
        output_dir: 输出目录

    Returns:
        str: 图片相对路径
    """
    labels = ['基本面', '估值', '技术面', '动量', '风险']
    keys = ['fundamental', 'valuation', 'technical', 'momentum', 'risk']

    # 排名转分数：排名越小越好，转为 0-100 分数 (49只中)
    values = []
    for k in keys:
        rank = dim_avgs.get(k)
        if rank is not None:
            score = max(0, 100 - (rank - 1) * (100 / 48))
            values.append(round(score, 1))
        else:
            values.append(50)

    # 闭合雷达图
    values += values[:1]
    labels += labels[:1]

    angles = [n / float(len(labels) - 1) * 2 * 3.14159 for n in range(len(labels))]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color=COLORS['primary'], alpha=0.2)
    ax.plot(angles, values, color=COLORS['primary'], linewidth=2, marker='o', markersize=6)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels[:-1], fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_title(f'{name} 多维度评分雷达图', fontsize=12, fontweight='bold', pad=20)

    filepath = os.path.join(output_dir, f'{name}_radar.png')
    return _save_fig(fig, filepath)


def generate_stock_charts(name, details, output_dir):
    """为单只股票生成全部图表

    Args:
        name: 股票名称
        details: score_result.get('details', {}) 包含 fundamental, valuation, technical 等
        output_dir: 输出目录

    Returns:
        dict: {'profitability': path, 'momentum': path, 'valuation': path, 'radar': path}
    """
    fund = details.get('fundamental', {})
    val = details.get('valuation', {})
    tech = details.get('technical', {})
    scores = details.get('scores', {})

    # 构建维度分数用于雷达图
    dim_avgs = {
        'fundamental': scores.get('fundamental', 50),
        'valuation': scores.get('valuation', 50),
        'technical': scores.get('technical', 50),
        'momentum': 50,  # 默认值
        'risk': scores.get('anomaly', 80),
    }

    charts = {}
    charts['profitability'] = generate_profitability_chart(name, fund, output_dir)
    charts['momentum'] = generate_momentum_chart(name, tech, output_dir)
    charts['valuation'] = generate_valuation_scatter(name, val, output_dir)
    charts['radar'] = generate_radar_chart(name, dim_avgs, output_dir)

    return charts


if __name__ == '__main__':
    # 测试图表生成
    test_fund = {'毛利率': 55.3, '净利率': 33.5, 'ROE': 25.8}
    test_tech = {'pct_5d': 3.2, 'pct_10d': 5.8, 'pct_20d': 8.1}
    test_val = {'pe_ttm_percentile': 35, 'pb_percentile': 42}

    output_dir = 'output/charts'
    os.makedirs(output_dir, exist_ok=True)

    print("生成盈利能力图...")
    generate_profitability_chart('贵州茅台', test_fund, output_dir)

    print("生成动量图...")
    generate_momentum_chart('贵州茅台', test_tech, output_dir)

    print("生成估值散点图...")
    generate_valuation_scatter('贵州茅台', test_val, output_dir)

    print("测试完成")

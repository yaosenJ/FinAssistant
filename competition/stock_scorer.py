# -*- coding: utf-8 -*-
"""
多因子选股打分模块
对比赛指定的49只股票进行综合评分
"""

import os
import sys
import json
import logging

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from tools.stock_fundamental import calc_fundamental_indicators
from tools.stock_valuation import calc_valuation_percentile
from tools.stock_technical import calc_technical_indicators, calc_technical_summary
from tools.financial_anomaly import detect_anomalies

logger = logging.getLogger(__name__)

# 比赛指定的49只股票
STOCK_LIST = {
    '金融板块': [
        ('601318.SH', '中国平安'), ('600036.SH', '招商银行'), ('601688.SH', '华泰证券'),
        ('601398.SH', '工商银行'), ('601288.SH', '农业银行'), ('601988.SH', '中国银行'),
        ('600000.SH', '浦发银行'), ('601998.SH', '中信银行'),
    ],
    '消费板块': [
        ('600519.SH', '贵州茅台'), ('000858.SZ', '五粮液'), ('600887.SH', '伊利股份'),
        ('603288.SH', '海天味业'), ('600660.SH', '福耀玻璃'), ('000333.SZ', '美的集团'),
        ('000651.SZ', '格力电器'), ('601888.SH', '中国中免'), ('600809.SH', '山西汾酒'),
    ],
    '新能源/电力板块': [
        ('300750.SZ', '宁德时代'), ('002594.SZ', '比亚迪'), ('601012.SH', '隆基绿能'),
        ('300274.SZ', '阳光电源'), ('600900.SH', '长江电力'), ('600438.SH', '通威股份'),
        ('600089.SH', '特变电工'), ('600212.SH', '绿能慧充'),
    ],
    '科技/AI/半导体板块': [
        ('688981.SH', '中芯国际'), ('600584.SH', '长电科技'), ('600183.SH', '生益科技'),
        ('300308.SZ', '中际旭创'), ('300394.SZ', '天孚通信'), ('603501.SH', '韦尔股份'),
        ('600703.SH', '三安光电'), ('600570.SH', '恒生电子'), ('600845.SH', '宝信软件'),
        ('688041.SH', '海光信息'), ('603986.SH', '兆易创新'), ('002475.SZ', '立讯精密'),
    ],
    '周期/资源板块': [
        ('601899.SH', '紫金矿业'), ('600309.SH', '万华化学'), ('601600.SH', '中国铝业'),
        ('600028.SH', '中国石化'), ('601088.SH', '中国神华'), ('600547.SH', '山东黄金'),
        ('600426.SH', '华鲁恒升'), ('601168.SH', '西部矿业'),
    ],
    '高端制造/基建板块': [
        ('600031.SH', '三一重工'), ('601766.SH', '中国中车'),
        ('601668.SH', '中国建筑'), ('601186.SH', '中国铁建'),
    ],
}

# 所有股票平铺
ALL_STOCKS = []
for sector, stocks in STOCK_LIST.items():
    for ts_code, name in stocks:
        ALL_STOCKS.append((ts_code, name, sector))


def _safe_float(val, default=None):
    """安全转 float"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def score_fundamental(indicators):
    """基本面评分 (0-100)

    基于 ROE、毛利率/营业利润率、净利率、杜邦三因子、现金流质量、应收账款占比、资产负债率、增长率
    """
    score = 50  # 基准分

    roe = _safe_float(indicators.get('ROE'))
    # 银行股用营业利润率，非银行股用毛利率
    gross_margin = _safe_float(indicators.get('毛利率') or indicators.get('营业利润率'))
    net_margin = _safe_float(indicators.get('净利率'))
    cf_ratio = _safe_float(indicators.get('经营现金流净利润比'))
    rev_growth = _safe_float(indicators.get('营收同比增长率'))
    np_growth = _safe_float(indicators.get('净利润同比增长率'))

    # 杜邦三因子
    dupont_margin = _safe_float(indicators.get('杜邦_净利率'))
    dupont_turnover = _safe_float(indicators.get('杜邦_总资产周转率'))
    dupont_leverage = _safe_float(indicators.get('杜邦_权益乘数'))

    # 应收账款占比、资产负债率
    ar_ratio = _safe_float(indicators.get('应收账款占比'))
    debt_ratio = _safe_float(indicators.get('资产负债率'))

    # ═══════════ 模块1：盈利能力 (基准分 50, 最高 +30) ═══════════

    # ROE 评分（权重最高）
    if roe is not None:
        if roe > 20:
            score += 20
        elif roe > 15:
            score += 15
        elif roe > 10:
            score += 10
        elif roe > 5:
            score += 5
        elif roe < 0:
            score -= 20

    # 毛利率/营业利润率
    if gross_margin is not None:
        if gross_margin > 50:
            score += 10
        elif gross_margin > 30:
            score += 5
        elif gross_margin < 10:
            score -= 5

    # ═══════════ 模块2：现金流质量 (最高 +10) ═══════════

    if cf_ratio is not None:
        if cf_ratio > 1.2:
            score += 10
        elif cf_ratio > 0.8:
            score += 5
        elif cf_ratio < 0:
            score -= 10

    # 应收账款占比（越低越好）
    if ar_ratio is not None:
        if ar_ratio < 10:
            score += 5
        elif ar_ratio < 20:
            score += 0
        elif ar_ratio > 30:
            score -= 5

    # ═══════════ 模块3：偿债能力 (最高 +5) ═══════════

    # 资产负债率（越低越安全，银行除外因为银行本身就是高杠杆）
    if debt_ratio is not None:
        is_bank = indicators.get('is_bank', False)
        if not is_bank:
            if debt_ratio < 30:
                score += 5
            elif debt_ratio < 50:
                score += 0
            elif debt_ratio > 70:
                score -= 5

    # ═══════════ 模块4：成长性 (最高 +16) ═══════════

    if rev_growth is not None:
        if rev_growth > 20:
            score += 8
        elif rev_growth > 10:
            score += 4
        elif rev_growth < -10:
            score -= 8

    if np_growth is not None:
        if np_growth > 30:
            score += 8
        elif np_growth > 15:
            score += 4
        elif np_growth < -20:
            score -= 10

    return max(0, min(100, score))


def score_valuation(val_data):
    """估值评分 (0-100)

    PE/PB 历史百分位越低越好（低估加分）
    """
    score = 50

    pe_pct = _safe_float(val_data.get('pe_ttm_percentile'))
    pb_pct = _safe_float(val_data.get('pb_percentile'))

    # PE 百分位
    if pe_pct is not None:
        if pe_pct < 20:
            score += 25  # 极度低估
        elif pe_pct < 40:
            score += 15
        elif pe_pct < 60:
            score += 5
        elif pe_pct < 80:
            score -= 5
        else:
            score -= 15  # 高估

    # PB 百分位
    if pb_pct is not None:
        if pb_pct < 20:
            score += 15
        elif pb_pct < 40:
            score += 8
        elif pb_pct < 60:
            score += 0
        elif pb_pct < 80:
            score -= 5
        else:
            score -= 10

    return max(0, min(100, score))


def score_technical(tech_data):
    """技术面评分 (0-100)

    基于 MA 趋势、MACD 信号、RSI 信号
    """
    score = 50

    ma_trend = tech_data.get('ma_trend', '')
    macd_signal = tech_data.get('macd_signal', '')
    rsi6_signal = tech_data.get('rsi6_signal', '')

    # MA 趋势
    if '多头' in str(ma_trend):
        score += 15
    elif '空头' in str(ma_trend):
        score -= 15

    # MACD
    if '金叉' in str(macd_signal):
        score += 12
    elif '死叉' in str(macd_signal):
        score -= 12
    elif '红柱' in str(macd_signal):
        score += 5
    elif '绿柱' in str(macd_signal):
        score -= 5

    # RSI
    if '超卖' in str(rsi6_signal):
        score += 8  # 超卖可能反弹
    elif '超买' in str(rsi6_signal):
        score -= 8  # 超买风险

    return max(0, min(100, score))


def score_anomaly(anomaly_text):
    """异常检测扣分 (0-100)

    无异常=100分，有异常按严重程度扣分
    """
    score = 100

    high_count = anomaly_text.count('[HIGH]')
    medium_count = anomaly_text.count('[MEDIUM]')

    score -= high_count * 20
    score -= medium_count * 8

    return max(0, min(100, score))


def score_momentum(tech_data):
    """动量评分 (0-100)

    基于近5/10/20日收益率、量比、波动率
    短期动量强势加分，波动率过高扣分
    """
    score = 50

    pct_5d = _safe_float(tech_data.get('pct_5d'))
    pct_10d = _safe_float(tech_data.get('pct_10d'))
    pct_20d = _safe_float(tech_data.get('pct_20d'))
    vol_ratio = _safe_float(tech_data.get('vol_ratio'))
    volatility = _safe_float(tech_data.get('volatility_20d'))

    # 短期动量（近5日收益率）
    if pct_5d is not None:
        if pct_5d > 5:
            score += 15
        elif pct_5d > 2:
            score += 10
        elif pct_5d > 0:
            score += 5
        elif pct_5d < -5:
            score -= 15
        elif pct_5d < -2:
            score -= 10

    # 中期动量（近10日收益率）
    if pct_10d is not None:
        if pct_10d > 8:
            score += 10
        elif pct_10d > 3:
            score += 5
        elif pct_10d < -8:
            score -= 10
        elif pct_10d < -3:
            score -= 5

    # 趋势确认（近20日收益率）
    if pct_20d is not None:
        if pct_20d > 10:
            score += 10
        elif pct_20d > 5:
            score += 5
        elif pct_20d < -10:
            score -= 10
        elif pct_20d < -5:
            score -= 5

    # 量比（资金流入）
    if vol_ratio is not None:
        if vol_ratio > 1.5:
            score += 8  # 明显放量
        elif vol_ratio > 1.0:
            score += 4  # 温和放量
        elif vol_ratio < 0.5:
            score -= 5  # 明显缩量

    # 波动率（越低越稳定）
    if volatility is not None:
        if volatility < 20:
            score += 5  # 低波动
        elif volatility > 40:
            score -= 8  # 高波动风险

    return max(0, min(100, score))


def score_single_stock(ts_code, name):
    """对单只股票进行全维度打分"""
    result = {
        'ts_code': ts_code,
        'name': name,
        'scores': {},
        'details': {},
    }

    # 1. 基本面
    try:
        fund = calc_fundamental_indicators(ts_code)
        if 'error' not in fund:
            result['scores']['fundamental'] = score_fundamental(fund)
            result['details']['fundamental'] = fund
        else:
            result['scores']['fundamental'] = 30
    except Exception as e:
        logger.warning(f"{ts_code} 基本面分析失败: {e}")
        result['scores']['fundamental'] = 30

    # 2. 估值
    try:
        val = calc_valuation_percentile(ts_code)
        if 'error' not in val:
            result['scores']['valuation'] = score_valuation(val)
            result['details']['valuation'] = val
        else:
            result['scores']['valuation'] = 50
    except Exception as e:
        logger.warning(f"{ts_code} 估值分析失败: {e}")
        result['scores']['valuation'] = 50

    # 3. 技术面 + 动量（共用 tech 数据）
    try:
        tech = calc_technical_indicators(ts_code)
        if 'error' not in tech:
            result['scores']['technical'] = score_technical(tech)
            result['scores']['momentum'] = score_momentum(tech)
            result['details']['technical'] = tech
        else:
            result['scores']['technical'] = 50
            result['scores']['momentum'] = 50
    except Exception as e:
        logger.warning(f"{ts_code} 技术面/动量分析失败: {e}")
        result['scores']['technical'] = 50
        result['scores']['momentum'] = 50

    # 4. 异常检测
    try:
        anomaly = detect_anomalies(ts_code)
        result['scores']['anomaly'] = score_anomaly(anomaly)
        result['details']['anomaly'] = anomaly
    except Exception as e:
        logger.warning(f"{ts_code} 异常检测失败: {e}")
        result['scores']['anomaly'] = 80

    # 综合加权评分
    weights = {
        'fundamental': 0.20,
        'valuation': 0.15,
        'technical': 0.30,
        'momentum': 0.25,
        'anomaly': 0.10,
    }

    total = 0
    total_weight = 0
    for factor, weight in weights.items():
        s = result['scores'].get(factor)
        if s is not None:
            total += s * weight
            total_weight += weight

    if total_weight > 0:
        result['total_score'] = round(total / total_weight * (sum(weights.values()) / total_weight), 1)
    else:
        result['total_score'] = 0

    # 简化 details（避免输出过大）
    tech = result['details'].get('technical', {})
    result['summary'] = {
        'fundamental': f"ROE={_safe_float(result['details'].get('fundamental', {}).get('ROE'), '--')}% "
                       f"毛利率={_safe_float(result['details'].get('fundamental', {}).get('毛利率'), '--')}%",
        'valuation': f"PE分位={_safe_float(result['details'].get('valuation', {}).get('pe_ttm_percentile'), '--')}% "
                     f"PB分位={_safe_float(result['details'].get('valuation', {}).get('pb_percentile'), '--')}%",
        'technical': f"趋势={tech.get('ma_trend', '--')} "
                     f"MACD={tech.get('macd_signal', '--')}",
        'momentum': f"5日涨幅={_safe_float(tech.get('pct_5d'), '--')}% "
                    f"20日涨幅={_safe_float(tech.get('pct_20d'), '--')}%",
    }

    return result


def score_all_stocks():
    """对所有49只股票打分并排名

    排名规则：浮点分数排序后，分配唯一整数排名1-49（无并列）
    板块排名：每个板块内部分配唯一整数排名1-N
    """
    results = []
    total = len(ALL_STOCKS)

    for i, (ts_code, name, sector) in enumerate(ALL_STOCKS, 1):
        print(f"[{i}/{total}] 正在分析 {name}({ts_code})...", end="", flush=True)
        try:
            r = score_single_stock(ts_code, name)
            r['sector'] = sector
            results.append(r)
            print(f" 综合评分: {r['total_score']}")
        except Exception as e:
            print(f" 失败: {e}")
            results.append({
                'ts_code': ts_code, 'name': name, 'sector': sector,
                'total_score': 0, 'scores': {}, 'summary': {},
            })

    # 按综合评分排序（浮点分数）
    results.sort(key=lambda x: x.get('total_score', 0), reverse=True)

    # 分配唯一整数排名（1-49，无并列）
    for i, r in enumerate(results):
        r['rank'] = i + 1

    # 各维度全局排名（1-49）
    dimensions = ['fundamental', 'valuation', 'technical', 'momentum', 'anomaly']
    for dim in dimensions:
        # 按该维度分数排序（anomaly 分数越高越好，其他也是越高越好）
        sorted_by_dim = sorted(results, key=lambda x: x.get('scores', {}).get(dim, 0), reverse=True)
        for i, r in enumerate(sorted_by_dim):
            if 'dim_ranks' not in r:
                r['dim_ranks'] = {}
            r['dim_ranks'][dim] = i + 1

    # 板块内排名
    sector_groups = {}
    for r in results:
        sector = r.get('sector', '未知')
        if sector not in sector_groups:
            sector_groups[sector] = []
        sector_groups[sector].append(r)

    for sector, stocks in sector_groups.items():
        # 综合排名
        stocks.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        for i, r in enumerate(stocks):
            r['sector_rank'] = i + 1

        # 各维度板块内排名
        for dim in dimensions:
            sorted_by_dim = sorted(stocks, key=lambda x: x.get('scores', {}).get(dim, 0), reverse=True)
            for i, r in enumerate(sorted_by_dim):
                if 'dim_sector_ranks' not in r:
                    r['dim_sector_ranks'] = {}
                r['dim_sector_ranks'][dim] = i + 1

    return results


def print_ranking(results, top_n=None):
    """打印排名表"""
    if top_n:
        display = results[:top_n]
    else:
        display = results

    print(f"\n{'='*90}")
    print(f"{'排名':<4} {'股票':<12} {'板块':<16} {'综合分':<8} {'基本面':<8} {'估值':<8} {'技术面':<8} {'动量':<8} {'异常':<8}")
    print(f"{'-'*90}")

    for i, r in enumerate(display, 1):
        scores = r.get('scores', {})
        print(f"{i:<4} {r['name']:<10} {r.get('sector', ''):<14} "
              f"{r.get('total_score', 0):<8.1f} "
              f"{scores.get('fundamental', '--'):<8} "
              f"{scores.get('valuation', '--'):<8} "
              f"{scores.get('technical', '--'):<8} "
              f"{scores.get('momentum', '--'):<8} "
              f"{scores.get('anomaly', '--'):<8}")

    print(f"{'='*90}")


if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='多因子选股打分')
    parser.add_argument('--output', '-o', help='输出JSON文件路径')
    parser.add_argument('--top', '-t', type=int, default=49, help='显示前N名')
    args = parser.parse_args()

    print(f"开始对{len(ALL_STOCKS)}只股票进行多因子打分...")
    results = score_all_stocks()
    print_ranking(results, top_n=args.top)

    if args.output:
        import os
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n结果已保存到: {args.output}")

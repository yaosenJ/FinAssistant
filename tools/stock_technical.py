#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术指标计算工具
从 MySQL market_data.stock_kline 表获取 OHLCV 数据，计算各种技术指标

═══════════════════════════════════════════════════════════════════
技术指标详解
═══════════════════════════════════════════════════════════════════

1. MA（移动平均线, Moving Average）
─────────────────────────────────────────────────────────────────
   公式: MA(N) = 最近N日收盘价的算术平均值
   常用周期: MA5（周线）、MA10（半月线）、MA20（月线）、MA60（季线）

   选股用途:
   - 趋势判断: 股价在MA之上为多头趋势，之下为空头趋势
   - 支撑/阻力: MA常作为动态支撑位或阻力位
   - 金叉/死叉: 短期MA上穿长期MA为金叉（买入信号），下穿为死叉（卖出信号）

2. MACD（指数平滑异同移动平均线）
─────────────────────────────────────────────────────────────────
   公式:
   - DIF（快线）= EMA(12) - EMA(26)
   - DEA（慢线）= DIF的9日EMA
   - MACD柱 = (DIF - DEA) × 2

   选股用途:
   - 金叉买入: DIF上穿DEA，且MACD柱由负转正
   - 死叉卖出: DIF下穿DEA，且MACD柱由正转负
   - 背离信号: 股价创新高但MACD不创新高，为顶背离（卖出信号）
   - 零轴上方: DIF>0表示短期趋势强于长期

3. RSI（相对强弱指数, Relative Strength Index）
─────────────────────────────────────────────────────────────────
   公式:
   - RS = N日平均涨幅 / N日平均跌幅
   - RSI = 100 - 100/(1+RS)
   常用周期: RSI(6)短期、RSI(12)中期、RSI(24)长期

   选股用途:
   - 超买信号: RSI > 80，可能面临回调
   - 超卖信号: RSI < 20，可能存在反弹机会
   - 趋势确认: RSI在50以上为多头市场，50以下为空头市场
   - 背离信号: 股价新高但RSI不创新高，为顶背离

4. BOLL（布林带, Bollinger Bands）
─────────────────────────────────────────────────────────────────
   公式:
   - 中轨 = MA(20)
   - 上轨 = MA(20) + 2×标准差
   - 下轨 = MA(20) - 2×标准差

   选股用途:
   - 超买/超卖: 股价触及上轨可能回调，触及下轨可能反弹
   - 波动率: 带宽扩大表示波动加剧，收窄表示盘整
   - 趋势跟踪: 股价沿上轨运行为强势，沿下轨为弱势

5. KDJ（随机指标, Stochastic Oscillator）
─────────────────────────────────────────────────────────────────
   公式:
   - RSV = (收盘价 - N日最低价) / (N日最高价 - N日最低价) × 100
   - K = 2/3 × 前一日K + 1/3 × RSV
   - D = 2/3 × 前一日D + 1/3 × K
   - J = 3K - 2D
   常用参数: N=9, M1=3, M2=3

   选股用途:
   - 超买信号: K>80, D>80, J>100
   - 超卖信号: K<20, D<20, J<0
   - 金叉买入: K上穿D，且在超卖区
   - 死叉卖出: K下穿D，且在超买区

═══════════════════════════════════════════════════════════════════
综合研判建议
═══════════════════════════════════════════════════════════════════

   单一指标容易产生假信号，建议多指标交叉验证：

   ┌─────────────────────────────────────────────────────────────┐
   │ 买入信号（至少满足2-3个）                                    │
   ├─────────────────────────────────────────────────────────────┤
   │ ✓ 股价站上MA20，MA金叉（MA5>MA10>MA20）                      │
   │ ✓ MACD金叉（DIF上穿DEA），且MACD柱转正                       │
   │ ✓ RSI从超卖区回升（<20 → >20）                               │
   │ ✓ 股价触及布林带下轨后反弹                                    │
   │ ✓ KDJ金叉（K上穿D），且在超卖区                               │
   └─────────────────────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────────────────────┐
   │ 卖出信号（至少满足2-3个）                                    │
   ├─────────────────────────────────────────────────────────────┤
   │ ✗ 股价跌破MA20，MA死叉（MA5<MA10<MA20）                      │
   │ ✗ MACD死叉（DIF下穿DEA），且MACD柱转负                       │
   │ ✗ RSI进入超买区（>80）后回落                                  │
   │ ✗ 股价触及布林带上轨后回落                                    │
   │ ✗ KDJ死叉（K下穿D），且在超买区                               │
   └─────────────────────────────────────────────────────────────┘

数据来源: market_data.stock_kline 表的 open, high, low, close, volume 字段

用法:
    from tools.stock_technical import calc_technical_indicators, calc_technical_summary
    result = calc_technical_indicators('600519.SH')
    print(result['ma5'], result['macd_dif'], result['rsi6'])
"""

import logging
from datetime import datetime, timedelta

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)


def _safe_float(val):
    """安全转 float"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def get_kline_data(ts_code, days=120):
    """从MySQL获取K线数据

    Args:
        ts_code: 股票代码，如 600519.SH
        days: 获取天数，默认120天（足够计算MA60）

    Returns:
        list: [{'trade_date': '2026-07-18', 'open': 1800.0, 'high': 1810.0,
                'low': 1790.0, 'close': 1805.0, 'volume': 50000}, ...]
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            sql = """
                SELECT trade_date, open, high, low, close, volume
                FROM stock_kline
                WHERE ts_code = %s
                  AND trade_date >= %s
                  AND close IS NOT NULL
                ORDER BY trade_date
            """
            cursor.execute(sql, (ts_code, start_date))
            rows = cursor.fetchall()

            if not rows:
                return []

            result = []
            for row in rows:
                result.append({
                    'trade_date': str(row[0]),
                    'open': _safe_float(row[1]),
                    'high': _safe_float(row[2]),
                    'low': _safe_float(row[3]),
                    'close': _safe_float(row[4]),
                    'volume': _safe_float(row[5]),
                })

            return result
    finally:
        conn.close()


def _calc_ma(closes, period):
    """计算移动平均线 MA

    公式: MA(N) = 最近N日收盘价的算术平均值

    Args:
        closes: 收盘价列表
        period: 周期（如5, 10, 20, 60）

    Returns:
        float: MA值，数据不足返回None
    """
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def _calc_ema(data, period):
    """计算指数移动平均线 EMA

    公式: EMA(today) = α × Price(today) + (1-α) × EMA(yesterday)
    其中: α = 2 / (period + 1)

    Args:
        data: 价格列表
        period: 周期

    Returns:
        list: EMA序列
    """
    if len(data) < period:
        return []

    multiplier = 2 / (period + 1)
    ema = [sum(data[:period]) / period]  # 第一个EMA用SMA初始化

    for i in range(period, len(data)):
        value = (data[i] - ema[-1]) * multiplier + ema[-1]
        ema.append(value)

    return ema


def _calc_macd(closes, fast=12, slow=26, signal=9):
    """计算MACD指标

    公式:
    - DIF = EMA(fast) - EMA(slow)
    - DEA = DIF的signal日EMA
    - MACD柱 = (DIF - DEA) × 2

    Args:
        closes: 收盘价列表
        fast: 快线周期，默认12
        slow: 慢线周期，默认26
        signal: 信号线周期，默认9

    Returns:
        dict: {'dif': float, 'dea': float, 'macd_hist': float}
    """
    if len(closes) < slow + signal:
        return {'dif': None, 'dea': None, 'macd_hist': None}

    ema_fast = _calc_ema(closes, fast)
    ema_slow = _calc_ema(closes, slow)

    # 对齐长度
    diff = len(ema_fast) - len(ema_slow)
    ema_fast = ema_fast[diff:]

    # 计算DIF
    dif = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]

    # 计算DEA
    dea = _calc_ema(dif, signal)

    # 对齐DIF和DEA
    diff2 = len(dif) - len(dea)
    dif = dif[diff2:]

    if not dif or not dea:
        return {'dif': None, 'dea': None, 'macd_hist': None}

    # MACD柱 = (DIF - DEA) × 2
    macd_hist = (dif[-1] - dea[-1]) * 2

    return {
        'dif': round(dif[-1], 4),
        'dea': round(dea[-1], 4),
        'macd_hist': round(macd_hist, 4),
    }


def _calc_rsi(closes, period=6):
    """计算RSI指标

    公式:
    - RS = N日平均涨幅 / N日平均跌幅
    - RSI = 100 - 100/(1+RS)

    Args:
        closes: 收盘价列表
        period: 周期，默认6

    Returns:
        float: RSI值
    """
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    recent = changes[-period:]

    gains = [c for c in recent if c > 0]
    losses = [-c for c in recent if c < 0]

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.001  # 避免除零

    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)

    return round(rsi, 2)


def _calc_boll(closes, period=20, std_dev=2):
    """计算布林带

    公式:
    - 中轨 = MA(period)
    - 上轨 = MA + std_dev × 标准差
    - 下轨 = MA - std_dev × 标准差

    Args:
        closes: 收盘价列表
        period: 周期，默认20
        std_dev: 标准差倍数，默认2

    Returns:
        dict: {'upper': float, 'middle': float, 'lower': float}
    """
    if len(closes) < period:
        return {'upper': None, 'middle': None, 'lower': None}

    recent = closes[-period:]
    middle = sum(recent) / period
    variance = sum((x - middle) ** 2 for x in recent) / period
    std = variance ** 0.5

    return {
        'upper': round(middle + std_dev * std, 2),
        'middle': round(middle, 2),
        'lower': round(middle - std_dev * std, 2),
    }


def _calc_kdj(highs, lows, closes, n=9, m1=3, m2=3):
    """计算KDJ指标

    公式:
    - RSV = (收盘价 - N日最低价) / (N日最高价 - N日最低价) × 100
    - K = 2/3 × 前一日K + 1/3 × RSV (初始值50)
    - D = 2/3 × 前一日D + 1/3 × K (初始值50)
    - J = 3K - 2D

    Args:
        highs: 最高价列表
        lows: 最低价列表
        closes: 收盘价列表
        n: RSV周期，默认9
        m1: K平滑周期，默认3
        m2: D平滑周期，默认3

    Returns:
        dict: {'k': float, 'd': float, 'j': float}
    """
    if len(closes) < n:
        return {'k': None, 'd': None, 'j': None}

    k, d = 50.0, 50.0

    for i in range(n - 1, len(closes)):
        high_n = max(highs[i-n+1:i+1])
        low_n = min(lows[i-n+1:i+1])

        if high_n == low_n:
            rsv = 50
        else:
            rsv = (closes[i] - low_n) / (high_n - low_n) * 100

        k = (2/3) * k + (1/3) * rsv
        d = (2/3) * d + (1/3) * k

    j = 3 * k - 2 * d

    return {
        'k': round(k, 2),
        'd': round(d, 2),
        'j': round(j, 2),
    }


def _get_ma_trend(ma5, ma10, ma20):
    """判断均线趋势

    Returns:
        str: '多头排列' / '空头排列' / '交叉盘整'
    """
    if ma5 is None or ma10 is None or ma20 is None:
        return None

    if ma5 > ma10 > ma20:
        return '多头排列'
    elif ma5 < ma10 < ma20:
        return '空头排列'
    else:
        return '交叉盘整'


def _get_macd_signal(dif, dea, macd_hist):
    """判断MACD信号

    Returns:
        str: '金叉' / '死叉' / '中性'
    """
    if dif is None or dea is None:
        return None

    if dif > dea and macd_hist > 0:
        return '金叉'
    elif dif < dea and macd_hist < 0:
        return '死叉'
    else:
        return '中性'


def _get_rsi_signal(rsi):
    """判断RSI信号

    Returns:
        str: '超买' / '超卖' / '中性'
    """
    if rsi is None:
        return None

    if rsi > 80:
        return '超买'
    elif rsi < 20:
        return '超卖'
    else:
        return '中性'


def _get_kdj_signal(k, d, j):
    """判断KDJ信号

    Returns:
        str: '超买' / '超卖' / '金叉' / '死叉' / '中性'
    """
    if k is None or d is None or j is None:
        return None

    if k > 80 and d > 80:
        return '超买'
    elif k < 20 and d < 20:
        return '超卖'
    elif k > d and j > k:
        return '金叉'
    elif k < d and j < k:
        return '死叉'
    else:
        return '中性'


def calc_technical_indicators(ts_code, days=120):
    """计算技术指标

    Args:
        ts_code: 股票代码，如 600519.SH
        days: 获取K线天数，默认120天

    Returns:
        dict: {
            ts_code, trade_date, close,
            ma5, ma10, ma20, ma60, ma_trend,
            macd_dif, macd_dea, macd_hist, macd_signal,
            rsi6, rsi12, rsi24, rsi6_signal,
            boll_upper, boll_middle, boll_lower,
            kdj_k, kdj_d, kdj_j, kdj_signal
        }
    """
    kline = get_kline_data(ts_code, days)

    if not kline or len(kline) < 30:
        return {'ts_code': ts_code, 'error': 'K线数据不足'}

    closes = [k['close'] for k in kline if k['close'] is not None]
    highs = [k['high'] for k in kline if k['high'] is not None]
    lows = [k['low'] for k in kline if k['low'] is not None]

    if len(closes) < 30:
        return {'ts_code': ts_code, 'error': '有效K线数据不足'}

    # MA
    ma5 = _calc_ma(closes, 5)
    ma10 = _calc_ma(closes, 10)
    ma20 = _calc_ma(closes, 20)
    ma60 = _calc_ma(closes, 60) if len(closes) >= 60 else None
    ma_trend = _get_ma_trend(ma5, ma10, ma20)

    # MACD
    macd = _calc_macd(closes)
    macd_signal = _get_macd_signal(macd['dif'], macd['dea'], macd['macd_hist'])

    # RSI
    rsi6 = _calc_rsi(closes, 6)
    rsi12 = _calc_rsi(closes, 12)
    rsi24 = _calc_rsi(closes, 24) if len(closes) >= 25 else None
    rsi6_signal = _get_rsi_signal(rsi6)

    # BOLL
    boll = _calc_boll(closes)

    # KDJ
    kdj = _calc_kdj(highs, lows, closes)
    kdj_signal = _get_kdj_signal(kdj['k'], kdj['d'], kdj['j'])

    result = {
        'ts_code': ts_code,
        'trade_date': kline[-1]['trade_date'],
        'close': closes[-1],

        # MA
        'ma5': ma5,
        'ma10': ma10,
        'ma20': ma20,
        'ma60': ma60,
        'ma_trend': ma_trend,

        # MACD
        'macd_dif': macd['dif'],
        'macd_dea': macd['dea'],
        'macd_hist': macd['macd_hist'],
        'macd_signal': macd_signal,

        # RSI
        'rsi6': rsi6,
        'rsi12': rsi12,
        'rsi24': rsi24,
        'rsi6_signal': rsi6_signal,

        # BOLL
        'boll_upper': boll['upper'],
        'boll_middle': boll['middle'],
        'boll_lower': boll['lower'],

        # KDJ
        'kdj_k': kdj['k'],
        'kdj_d': kdj['d'],
        'kdj_j': kdj['j'],
        'kdj_signal': kdj_signal,
    }

    return result


def calc_technical_summary(ts_code, days=120):
    """生成技术指标摘要（适合直接输出）

    Args:
        ts_code: 股票代码
        days: 获取K线天数

    Returns:
        str: 格式化的技术指标摘要文本
    """
    result = calc_technical_indicators(ts_code, days)

    if 'error' in result:
        return f"{ts_code}: {result['error']}"

    lines = [
        f"=== {ts_code} 技术指标分析 ({result['trade_date']}) ===",
        f"收盘价: {result['close']}",
        "",
        "【移动平均线 MA】",
        f"  MA5:  {result['ma5']}",
        f"  MA10: {result['ma10']}",
        f"  MA20: {result['ma20']}",
        f"  MA60: {result['ma60']}",
        f"  均线趋势: {result['ma_trend']}",
        "",
        "【MACD】",
        f"  DIF: {result['macd_dif']}",
        f"  DEA: {result['macd_dea']}",
        f"  MACD柱: {result['macd_hist']}",
        f"  信号: {result['macd_signal']}",
        "",
        "【RSI】",
        f"  RSI(6):  {result['rsi6']}",
        f"  RSI(12): {result['rsi12']}",
        f"  RSI(24): {result['rsi24']}",
        f"  RSI(6)信号: {result['rsi6_signal']}",
        "",
        "【布林带 BOLL】",
        f"  上轨: {result['boll_upper']}",
        f"  中轨: {result['boll_middle']}",
        f"  下轨: {result['boll_lower']}",
        "",
        "【KDJ】",
        f"  K: {result['kdj_k']}",
        f"  D: {result['kdj_d']}",
        f"  J: {result['kdj_j']}",
        f"  信号: {result['kdj_signal']}",
    ]

    # 综合研判
    signals = []
    if result['ma_trend'] == '多头排列':
        signals.append('MA多头排列')
    elif result['ma_trend'] == '空头排列':
        signals.append('MA空头排列')

    if result['macd_signal'] == '金叉':
        signals.append('MACD金叉')
    elif result['macd_signal'] == '死叉':
        signals.append('MACD死叉')

    if result['rsi6_signal'] == '超买':
        signals.append('RSI超买')
    elif result['rsi6_signal'] == '超卖':
        signals.append('RSI超卖')

    if result['kdj_signal'] in ['金叉', '超买', '超卖', '死叉']:
        signals.append(f"KDJ{result['kdj_signal']}")

    if signals:
        lines.append("")
        lines.append("【综合研判】")
        lines.append(f"  当前信号: {', '.join(signals)}")

    return "\n".join(lines)


if __name__ == '__main__':
    import json

    test_stocks = [
        ('600519.SH', '贵州茅台'),
        ('000858.SZ', '五粮液'),
    ]

    print("=" * 60)
    print("技术指标计算测试")
    print("=" * 60)

    for code, name in test_stocks:
        print(f"\n--- {name} ({code}) ---")
        result = calc_technical_indicators(code)
        # 隐藏内部字段
        display = {k: v for k, v in result.items() if not k.startswith('_')}
        print(json.dumps(display, ensure_ascii=False, indent=2))

    # 测试摘要输出
    print("\n" + "=" * 60)
    print("技术指标摘要测试")
    print("=" * 60)
    print(calc_technical_summary('600519.SH'))

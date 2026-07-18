---
name: stock-analysis
description: 个股全景分析技能，综合基本面、估值、技术面三个维度进行全方位分析。核心能力：基本面指标计算、估值百分位判断、技术指标解读、综合评级、生成分析报告。当用户询问某只股票的分析、估值、走势、技术面、操作建议时触发本技能。
---

# 个股全景分析技能

## 触发条件

用户询问某只股票的分析、估值、走势、技术面、操作建议时触发。典型问题：

**基本面查询**：
- "贵州茅台的ROE是多少？"
- "比亚迪最近一个季度的毛利率怎么样？"
- "宁德时代的现金流状况如何？"

**估值查询**：
- "茅台现在估值高吗？"
- "平安银行的PE处于历史什么水平？"
- "哪些股票估值比较低？"

**技术面查询**：
- "比亚迪的技术面怎么样？"
- "茅台的MACD是什么信号？"
- "哪些股票出现了金叉？"

**综合分析**：
- "分析一下贵州茅台"
- "帮我看看600519.SH值不值得买"
- "生成一份比亚迪的个股分析报告"
- "给我一份宁德时代的投资建议"

## 依赖工具组

| 工具组 | 包含工具 | 功能 |
|--------|----------|------|
| `stock-fundamental` | calc_fundamental_indicators, calc_fundamental_trend, get_financial_data, get_report_dates | 基本面指标计算（ROE、毛利率、资产负债率、增长率等） |
| `stock-valuation` | calc_valuation_percentile, calc_valuation_summary, get_valuation_history, get_latest_valuation | 估值百分位分析（PE/PB/PCF 高估/低估判断） |
| `stock-technical` | calc_technical_indicators, calc_technical_summary, get_kline_data | 技术指标计算（MA、MACD、RSI、KDJ、布林带） |
| `stock-analysis` | generate_stock_report | 综合分析报告（整合三维数据生成全景报告） |

## 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ts_code` | str | 是 | 股票代码，如 600519.SH |
| `report_type` | str | 否 | 报告类型：brief(简要) / detail(详细)，默认 brief |

## 执行流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     个股全景分析流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: 获取基本面指标                                         │
│  ├── calc_fundamental_indicators(ts_code)                       │
│  │   → ROE, 毛利率, 净利率, 资产负债率, 经营现金流净利润比       │
│  └── calc_fundamental_trend(ts_code, periods=4)                 │
│      → 营收同比增长率, 净利润同比增长率, 环比增长率              │
│                                                                 │
│  Step 2: 获取估值数据                                           │
│  └── calc_valuation_percentile(ts_code)                         │
│      → PE_TTM, PB, PCF 及其百分位和估值水平                     │
│                                                                 │
│  Step 3: 获取技术指标                                           │
│  └── calc_technical_indicators(ts_code)                         │
│      → MA, MACD, RSI, BOLL, KDJ 及信号判断                     │
│                                                                 │
│  Step 4: 综合分析与评级                                         │
│  ├── 基本面评级 (基于ROE/毛利率/现金流/增长率)                  │
│  ├── 估值评级 (基于PE/PB/PCF百分位)                             │
│  ├── 技术面评级 (基于MA/MACD/RSI/KDJ信号)                       │
│  └── 综合评级 (三维加权)                                        │
│                                                                 │
│  Step 5: 生成分析报告                                           │
│  └── 输出结构化的个股全景分析报告                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 评级标准

### 基本面评级

| 评级 | 条件 |
|------|------|
| 优秀 | ROE > 15%，毛利率 > 40%，经营现金流净利润比 > 0.8，营收同比增长 > 10% |
| 良好 | ROE > 10%，毛利率 > 30%，经营现金流净利润比 > 0.5，营收同比增长 > 0% |
| 一般 | ROE > 5%，毛利率 > 20%，经营现金流净利润比 > 0 |
| 较差 | ROE < 5% 或 毛利率 < 20% 或 经营现金流为负 |

### 估值评级

| 评级 | 条件 |
|------|------|
| 低估 | PE/PB/PCF 百分位均 < 30% |
| 合理 | PE/PB/PCF 百分位在 30%-70% |
| 偏高 | PE/PB/PCF 百分位均 > 70% |
| 高估 | PE/PB/PCF 百分位均 > 80% |

### 技术面评级

| 评级 | 条件 |
|------|------|
| 强势 | MA多头排列 + MACD金叉 + RSI在40-70区间 |
| 偏强 | MA多头排列 或 MACD金叉 |
| 中性 | 无明显多空信号 |
| 偏弱 | MA空头排列 或 MACD死叉 |
| 弱势 | MA空头排列 + MACD死叉 + RSI<30或>70 |

## 报告模板

### 简要报告 (brief)

```
═══════════════════════════════════════════════════════════════════
            {股票名称} ({股票代码}) 个股全景分析报告
═══════════════════════════════════════════════════════════════════
报告日期: {当前日期}
最新收盘: {收盘价}

┌─────────────────────────────────────────────────────────────────┐
│                        综合评级                                 │
├─────────────────────────────────────────────────────────────────┤
│  基本面: {评级}    估值: {评级}    技术面: {评级}                │
│  综合建议: {买入/持有/观望/减持}                                │
└─────────────────────────────────────────────────────────────────┘

一、基本面分析
─────────────────────────────────────────────────────────────────
  ROE: {值}%          毛利率: {值}%
  净利率: {值}%       资产负债率: {值}%
  经营现金流/净利润: {值}

  增长情况:
  - 营收同比增长: {值}%
  - 净利润同比增长: {值}%

  基本面点评: {1-2句话总结基本面状况}

二、估值分析
─────────────────────────────────────────────────────────────────
  PE_TTM: {值} (百分位: {值}%, {估值水平})
  PB: {值} (百分位: {值}%, {估值水平})
  PCF: {值} (百分位: {值}%, {估值水平})

  估值点评: {1-2句话总结估值状况}

三、技术面分析
─────────────────────────────────────────────────────────────────
  均线趋势: {多头排列/空头排列/交叉盘整}
  MACD: {金叉/死叉/中性}
  RSI(6): {值} ({超买/超卖/中性})
  KDJ: K={值} D={值} J={值} ({信号})

  技术面点评: {1-2句话总结技术面状况}

四、风险提示
─────────────────────────────────────────────────────────────────
  - {风险点1}
  - {风险点2}

═══════════════════════════════════════════════════════════════════
```

### 详细报告 (detail)

在简要报告基础上，增加：

1. **历史趋势分析** — 最近4期基本面指标变化趋势
2. **估值历史区间** — PE/PB/PCF的历史最低、最高、均值
3. **技术指标详解** — 各指标的详细解读
4. **买卖信号汇总** — 当前存在的所有信号
5. **投资逻辑梳理** — 综合三维分析的投资逻辑

## 输出示例

```
═══════════════════════════════════════════════════════════════════
            贵州茅台 (600519.SH) 个股全景分析报告
═══════════════════════════════════════════════════════════════════
报告日期: 2026-07-18
最新收盘: 1258.99

┌─────────────────────────────────────────────────────────────────┐
│                        综合评级                                 │
├─────────────────────────────────────────────────────────────────┤
│  基本面: 优秀    估值: 合理偏低    技术面: 偏强                  │
│  综合建议: 持有                                                 │
└─────────────────────────────────────────────────────────────────┘

一、基本面分析
─────────────────────────────────────────────────────────────────
  ROE: 10.39%         毛利率: 89.91%
  净利率: 51.47%      资产负债率: 12.12%
  经营现金流/净利润: 0.96

  增长情况:
  - 营收同比增长: 6.34%
  - 净利润同比增长: 1.37%

  基本面点评: 毛利率极高(89.91%)体现品牌护城河，ROE稳健，
  现金流充沛，但增长放缓(营收+6.34%)。

二、估值分析
─────────────────────────────────────────────────────────────────
  PE_TTM: 19.03 (百分位: 21.88%, 合理偏低)
  PB: 5.81 (百分位: 17.19%, 低估)
  PCF: 25.58 (百分位: 69.53%, 合理偏高)

  估值点评: PE和PB均处于历史低位，估值具有安全边际；
  PCF偏高反映现金流溢价，整体估值合理偏低。

三、技术面分析
─────────────────────────────────────────────────────────────────
  均线趋势: 多头排列 (MA5>MA10>MA20)
  MACD: 金叉 (DIF>-3.33, MACD柱=21.52)
  RSI(6): 81.78 (超买)
  KDJ: K=84.69 D=76.65 J=100.77 (超买)

  技术面点评: 均线多头排列+MACD金叉，短期趋势向上；
  但RSI和KDJ均进入超买区，注意回调风险。

四、风险提示
─────────────────────────────────────────────────────────────────
  - RSI/KDJ超买，短期存在技术性回调压力
  - 营收增速放缓，需关注业绩持续性
  - PCF估值偏高，现金流溢价可能回落

═══════════════════════════════════════════════════════════════════
```

## 代码实现参考

```python
# tools/stock_analysis.py

from tools.stock_fundamental import calc_fundamental_indicators, calc_fundamental_trend
from tools.stock_valuation import calc_valuation_percentile
from tools.stock_technical import calc_technical_indicators


def generate_stock_report(ts_code, report_type='brief'):
    """生成个股全景分析报告

    Args:
        ts_code: 股票代码，如 600519.SH
        report_type: 报告类型，brief(简要) / detail(详细)

    Returns:
        str: 格式化的分析报告
    """
    # Step 1: 获取基本面数据
    fundamental = calc_fundamental_indicators(ts_code)
    trend = calc_fundamental_trend(ts_code, periods=4)

    # Step 2: 获取估值数据
    valuation = calc_valuation_percentile(ts_code)

    # Step 3: 获取技术指标
    technical = calc_technical_indicators(ts_code)

    # Step 4: 综合评级
    fundamental_score = _rate_fundamental(fundamental)
    valuation_score = _rate_valuation(valuation)
    technical_score = _rate_technical(technical)

    # Step 5: 生成报告
    if report_type == 'detail':
        return _generate_detail_report(ts_code, fundamental, trend, valuation, technical)
    else:
        return _generate_brief_report(ts_code, fundamental, valuation, technical)


def _rate_fundamental(data):
    """基本面评级"""
    roe = data.get('ROE', 0)
    margin = data.get('毛利率', 0)
    cf_ratio = data.get('经营现金流净利润比', 0)

    if roe > 15 and margin > 40 and cf_ratio > 0.8:
        return '优秀'
    elif roe > 10 and margin > 30 and cf_ratio > 0.5:
        return '良好'
    elif roe > 5 and margin > 20 and cf_ratio > 0:
        return '一般'
    else:
        return '较差'


def _rate_valuation(data):
    """估值评级"""
    pe_pct = data.get('pe_ttm_percentile', 50)
    pb_pct = data.get('pb_percentile', 50)
    pcf_pct = data.get('pcf_percentile', 50)
    avg_pct = (pe_pct + pb_pct + pcf_pct) / 3

    if avg_pct < 30:
        return '低估'
    elif avg_pct < 50:
        return '合理偏低'
    elif avg_pct < 70:
        return '合理'
    elif avg_pct < 80:
        return '合理偏高'
    else:
        return '高估'


def _rate_technical(data):
    """技术面评级"""
    ma_trend = data.get('ma_trend', '')
    macd_signal = data.get('macd_signal', '')
    rsi = data.get('rsi6', 50)

    if ma_trend == '多头排列' and macd_signal == '金叉' and 40 < rsi < 70:
        return '强势'
    elif ma_trend == '多头排列' or macd_signal == '金叉':
        return '偏强'
    elif ma_trend == '空头排列' and macd_signal == '死叉':
        return '弱势'
    elif ma_trend == '空头排列' or macd_signal == '死叉':
        return '偏弱'
    else:
        return '中性'
```

## 注意事项

1. **数据时效性**：基本面数据基于最新财报，估值和技术指标基于最新交易日
2. **银行股处理**：银行股的毛利率计算方式不同（净利息收入），已自动识别
3. **新股处理**：上市不足1年的股票，部分指标可能缺失
4. **ST股票**：需特别提示风险，评级应下调
5. **免责声明**：报告仅供参考，不构成投资建议

# {sector_name} 行业研究报告

## 一、板块概况

| 项目 | 内容 |
|------|------|
| 板块名称 | {sector_name} |
| 成分股数量 | {stock_count} |
| 板块类型 | {sector_type} |
| 数据日期 | {trade_date} |

### 板块市场表现

| 指标 | 数值 | 排名 |
|------|------|------|
| 板块涨跌幅 | {pct_chg} | {pct_chg_rank} |
| 成交额 | {turnover} | {turnover_rank} |
| 换手率 | {turnover_rate} | -- |
| 5日累计涨幅 | {pct_5d} | -- |
| 20日累计涨幅 | {pct_20d} | -- |

---

## 二、成分股排名

### 综合排名（前10）

| 排名 | 代码 | 名称 | 综合评分 | 基本面 | 估值 | 技术面 | 动量 |
|------|------|------|----------|--------|------|--------|------|
{top_stocks_table}

### 板块内各维度龙头

| 维度 | 第一名 | 代码 | 得分 |
|------|--------|------|------|
| 基本面 | {top_fundamental_name} | {top_fundamental_code} | {top_fundamental_score} |
| 估值 | {top_valuation_name} | {top_valuation_code} | {top_valuation_score} |
| 技术面 | {top_technical_name} | {top_technical_code} | {top_technical_score} |
| 动量 | {top_momentum_name} | {top_momentum_code} | {top_momentum_score} |

---

## 三、板块财务聚合分析

### 盈利能力统计

| 指标 | 均值 | 中位数 | 最大值 | 最小值 |
|------|------|--------|--------|--------|
| 毛利率 | {avg_gross_margin} | {median_gross_margin} | {max_gross_margin} | {min_gross_margin} |
| 净利率 | {avg_net_margin} | {median_net_margin} | {max_net_margin} | {min_net_margin} |
| ROE | {avg_roe} | {median_roe} | {max_roe} | {min_roe} |

### 成长性统计

| 指标 | 均值 | 中位数 | 正增长占比 |
|------|------|--------|------------|
| 营收同比增长率 | {avg_revenue_yoy} | {median_revenue_yoy} | {revenue_positive_pct} |
| 净利润同比增长率 | {avg_np_yoy} | {median_np_yoy} | {np_positive_pct} |

### 财务健康度

| 指标 | 均值 | 风险个股数 |
|------|------|------------|
| 经营现金流/净利润 | {avg_cf_ratio} | {cf_risk_count} |
| 资产负债率 | {avg_debt_ratio} | {debt_risk_count} |
| 应收账款/营收 | {avg_ar_ratio} | {ar_risk_count} |

---

## 四、板块估值分布

### 估值统计

| 指标 | 均值 | 中位数 | 低估占比 | 合理占比 | 高估占比 |
|------|------|--------|----------|----------|----------|
| PE_TTM百分位 | {avg_pe_pct} | {median_pe_pct} | {pe_low_pct} | {pe_mid_pct} | {pe_high_pct} |
| PB百分位 | {avg_pb_pct} | {median_pb_pct} | {pb_low_pct} | {pb_mid_pct} | {pb_high_pct} |

### 估值象限分布

| 象限 | 股票数 | 代表个股 |
|------|--------|----------|
| 低PE低PB（低估区） | {quadrant_ll_count} | {quadrant_ll_stocks} |
| 低PE高PB | {quadrant_lh_count} | {quadrant_lh_stocks} |
| 高PE低PB | {quadrant_hl_count} | {quadrant_hl_stocks} |
| 高PE高PB（高估区） | {quadrant_hh_count} | {quadrant_hh_stocks} |

---

## 五、板块轮动趋势

### 近期表现

| 周期 | 涨跌幅 | 排名 | 资金流向 |
|------|--------|------|----------|
| 近5日 | {rotation_5d} | {rotation_5d_rank} | {flow_5d} |
| 近10日 | {rotation_10d} | {rotation_10d_rank} | {flow_10d} |
| 近20日 | {rotation_20d} | {rotation_20d_rank} | {flow_20d} |

### 板块强度判断

- **动量等级**: {momentum_level}（强势/偏强/中性/偏弱/弱势）
- **资金关注度**: {fund_attention}（高/中/低）
- **板块趋势**: {sector_trend}

---

## 六、投资建议

### 板块评级: {sector_rating}

**看多因素:**
{bullish_factors}

**看空因素:**
{bearish_factors}

### 推荐关注个股

| 排名 | 代码 | 名称 | 推荐理由 |
|------|------|------|----------|
{recommend_table}

---

> 风险提示: 本报告基于量化模型自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。

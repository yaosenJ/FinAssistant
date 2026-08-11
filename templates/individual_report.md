# {stock_name}({stock_code}) 投资研究报告

## 一、投资要点

**综合评级: {overall_rating}**

**核心优势:** {core_advantages}

**主要风险:** {main_risks}

---

## 二、公司概况

| 项目 | 内容 |
|------|------|
| 股票代码 | {stock_code} |
| 股票名称 | {stock_name} |
| 所属板块 | {sector} |
| 综合评级 | {overall_rating} |
| 全局排名 | 第{rank}名（{total_stocks}只内） |
| 板块内排名 | 第{sector_rank}名（{sector}内） |

### 各维度排名对比

| 维度 | 全局排名 | 板块排名 |
|------|----------|----------|
| 基本面 | {dim_rank_fundamental} | {dim_sector_rank_fundamental} |
| 估值 | {dim_rank_valuation} | {dim_sector_rank_valuation} |
| 技术面 | {dim_rank_technical} | {dim_sector_rank_technical} |
| 动量 | {dim_rank_momentum} | {dim_sector_rank_momentum} |
| 风险 | {dim_rank_anomaly} | {dim_sector_rank_anomaly} |

---

## 三、盈利能力分析

| 指标 | 数值 | 评级 | 说明 |
|------|------|------|------|
| 毛利率/营业利润率 | {gross_margin} | {gross_margin_rating} | 越高越好，反映产品竞争力 |
| 净利率 | {net_margin} | {net_margin_rating} | 综合盈利能力 |
| ROE | {roe} | {roe_rating} | 股东回报率 |

**杜邦拆解:**

| 指标 | 数值 | 说明 |
|------|------|------|
| 净利率 | {dupont_net_margin} | ROE = 净利率 x 周转率 x 权益乘数 |
| 总资产周转率 | {dupont_turnover} | 反映资产运营效率 |
| 权益乘数 | {dupont_leverage} | 反映杠杆水平 |

---

## 四、盈利真实性与营运风险

| 指标 | 数值 | 评级 | 说明 |
|------|------|------|------|
| 经营现金流/净利润 | {cf_ratio} | {cf_ratio_rating} | >1 说明利润有现金支撑 |
| 应收账款/营收 | {ar_ratio} | {ar_ratio_rating} | 越低越好，回款风险小 |
| 资产负债率 | {debt_ratio} | {debt_ratio_rating} | 越低越安全 |

---

## 五、成长性分析

| 指标 | 数值 | 评级 |
|------|------|------|
| 营收同比增长率 | {revenue_yoy} | {revenue_yoy_rating} |
| 净利润同比增长率 | {np_yoy} | {np_yoy_rating} |
| 营收环比增长率 | {revenue_qoq} | -- |
| 净利润环比增长率 | {np_qoq} | -- |

---

## 六、估值分析

| 指标 | 当前值 | 历史分位 | 估值评级 |
|------|--------|----------|----------|
| PE_TTM | {pe_ttm} | {pe_ttm_percentile} | {pe_ttm_level} |
| PB | {pb} | {pb_percentile} | {pb_level} |

---

## 七、技术面分析

| 指标 | 数值 | 评级 |
|------|------|------|
| 最新收盘价 | {close} | -- |
| MA趋势 | {ma_trend} | {ma_rating} |
| MACD信号 | {macd_signal} | {macd_rating} |
| RSI6信号 | {rsi6_signal} | -- |
| KDJ信号 | {kdj_signal} | -- |

---

## 八、动量与趋势分析

| 指标 | 数值 | 评级 |
|------|------|------|
| 近5日收益率 | {pct_5d} | {pct_5d_rating} |
| 近10日收益率 | {pct_10d} | -- |
| 近20日收益率 | {pct_20d} | -- |
| 量比(5/20) | {vol_ratio} | {vol_rating} |
| 20日波动率(年化) | {volatility_20d} | -- |

---

## 九、风险检测

{anomaly_text}

---

## 十、综合评估

综合评级: **{overall_rating}**

| 维度 | 得分 | 权重 |
|------|------|------|
| 基本面 | {score_fundamental} | 20% |
| 估值 | {score_valuation} | 15% |
| 技术面 | {score_technical} | 30% |
| 动量 | {score_momentum} | 25% |
| 风险 | {score_anomaly} | 10% |

---

## 十一、行业对比（{sector}）

### 财务指标对比

| 指标 | 本公司 | 行业均值 | 对比 |
|------|--------|----------|------|
| 毛利率 | {company_gross_margin} | {sector_gross_margin} | {gross_margin_vs} |
| ROE | {company_roe} | {sector_roe} | {roe_vs} |
| 营收增长率 | {company_revenue_growth} | {sector_revenue_growth} | {revenue_growth_vs} |

### 估值对比

| 指标 | 本公司 | 行业均值 | 对比 |
|------|--------|----------|------|
| PE_TTM | {company_pe} | {sector_pe} | {pe_vs} |
| PB | {company_pb} | {sector_pb} | {pb_vs} |

---

## 十二、盈利预测

| 预测项 | 预测值 | 预测依据 |
|--------|--------|----------|
| 营收增速 | {forecast_revenue} | 基于本期增速70%衰减 |
| 净利润增速 | {forecast_np} | 基于本期增速70%衰减 |
| 远期PE | {forecast_pe} | 按预测增速折算 |

---

> 风险提示: 本报告基于量化模型自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。

---

## 附录：评级标准

| 维度 | 优 | 良 | 中 | 差 |
|------|------|------|------|------|
| 毛利率 | >40% | 25-40% | 15-25% | <15% |
| 净利率 | >20% | 12-20% | 6-12% | <6% |
| ROE | >18% | 12-18% | 6-12% | <6% |
| 经营现金流/净利润 | >1.2 | 0.8-1.2 | 0.5-0.8 | <0.5 |
| 应收账款/营收 | <10% | 10-20% | 20-30% | >30% |
| 资产负债率 | <30% | 30-50% | 50-70% | >70% |

| 维度 | 低估/偏多/强势 | 合理/中性/偏强 | 偏高/偏弱 | 高估/弱势 |
|------|----------------|----------------|-----------|-----------|
| PE/PB历史分位 | <20% | 20-50% | 50-80% | >80% |
| MA趋势 | 多头排列 | 交叉盘整 | -- | 空头排列 |
| 近5日收益率 | >5% | 1-5% | -5~1% | <-5% |
| 量比 | >1.5 | 1.0-1.5 | 0.7-1.0 | <0.7 |

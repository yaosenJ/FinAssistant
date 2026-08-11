# 多股票对比研究报告

## 一、对比概况

| 项目 | 内容 |
|------|------|
| 对比标的 | {stock_list} |
| 所属板块 | {sectors} |
| 数据日期 | {trade_date} |
| 对比数量 | {stock_count} |

---

## 二、公司概况对比

| 项目 | {stock_1_name} | {stock_2_name} | {stock_3_name} |
|------|---------------|---------------|---------------|
| 股票代码 | {stock_1_code} | {stock_2_code} | {stock_3_code} |
| 所属板块 | {stock_1_sector} | {stock_2_sector} | {stock_3_sector} |
| 综合排名 | {stock_1_rank} | {stock_2_rank} | {stock_3_rank} |
| 综合评分 | {stock_1_score} | {stock_2_score} | {stock_3_score} |
| 综合评级 | {stock_1_rating} | {stock_2_rating} | {stock_3_rating} |

---

## 三、盈利能力对比

| 指标 | {stock_1_name} | {stock_2_name} | {stock_3_name} | 最优 |
|------|---------------|---------------|---------------|------|
| 毛利率 | {s1_gross_margin} | {s2_gross_margin} | {s3_gross_margin} | {best_gross_margin} |
| 净利率 | {s1_net_margin} | {s2_net_margin} | {s3_net_margin} | {best_net_margin} |
| ROE | {s1_roe} | {s2_roe} | {s3_roe} | {best_roe} |
| 经营现金流/净利润 | {s1_cf_ratio} | {s2_cf_ratio} | {s3_cf_ratio} | {best_cf_ratio} |

### 盈利能力综合评价

- **{stock_1_name}**: {s1_profit_comment}
- **{stock_2_name}**: {s2_profit_comment}
- **{stock_3_name}**: {s3_profit_comment}

---

## 四、成长性对比

| 指标 | {stock_1_name} | {stock_2_name} | {stock_3_name} | 最优 |
|------|---------------|---------------|---------------|------|
| 营收同比增长率 | {s1_revenue_yoy} | {s2_revenue_yoy} | {s3_revenue_yoy} | {best_revenue_yoy} |
| 净利润同比增长率 | {s1_np_yoy} | {s2_np_yoy} | {s3_np_yoy} | {best_np_yoy} |
| 营收环比增长率 | {s1_revenue_qoq} | {s2_revenue_qoq} | {s3_revenue_qoq} | -- |

### 成长性综合评价

- **{stock_1_name}**: {s1_growth_comment}
- **{stock_2_name}**: {s2_growth_comment}
- **{stock_3_name}**: {s3_growth_comment}

---

## 五、估值对比

| 指标 | {stock_1_name} | {stock_2_name} | {stock_3_name} | 最优 |
|------|---------------|---------------|---------------|------|
| PE_TTM | {s1_pe} | {s2_pe} | {s3_pe} | {best_pe} |
| PE历史分位 | {s1_pe_pct} | {s2_pe_pct} | {s3_pe_pct} | {best_pe_pct} |
| PB | {s1_pb} | {s2_pb} | {s3_pb} | {best_pb} |
| PB历史分位 | {s1_pb_pct} | {s2_pb_pct} | {s3_pb_pct} | {best_pb_pct} |
| 估值评级 | {s1_val_level} | {s2_val_level} | {s3_val_level} | -- |

### 估值综合评价

- **{stock_1_name}**: {s1_val_comment}
- **{stock_2_name}**: {s2_val_comment}
- **{stock_3_name}**: {s3_val_comment}

---

## 六、技术面对比

| 指标 | {stock_1_name} | {stock_2_name} | {stock_3_name} |
|------|---------------|---------------|---------------|
| 最新收盘价 | {s1_close} | {s2_close} | {s3_close} |
| MA趋势 | {s1_ma_trend} | {s2_ma_trend} | {s3_ma_trend} |
| MACD信号 | {s1_macd} | {s2_macd} | {s3_macd} |
| RSI6 | {s1_rsi6} | {s2_rsi6} | {s3_rsi6} |
| 技术面评级 | {s1_tech_level} | {s2_tech_level} | {s3_tech_level} |

---

## 七、动量对比

| 指标 | {stock_1_name} | {stock_2_name} | {stock_3_name} | 最优 |
|------|---------------|---------------|---------------|------|
| 近5日收益率 | {s1_pct_5d} | {s2_pct_5d} | {s3_pct_5d} | {best_pct_5d} |
| 近10日收益率 | {s1_pct_10d} | {s2_pct_10d} | {s3_pct_10d} | -- |
| 近20日收益率 | {s1_pct_20d} | {s2_pct_20d} | {s3_pct_20d} | -- |
| 量比 | {s1_vol_ratio} | {s2_vol_ratio} | {s3_vol_ratio} | -- |
| 20日波动率 | {s1_volatility} | {s2_volatility} | {s3_volatility} | {best_volatility} |

---

## 八、风险对比

| 风险类型 | {stock_1_name} | {stock_2_name} | {stock_3_name} |
|----------|---------------|---------------|---------------|
| HIGH级异常 | {s1_high_count} | {s2_high_count} | {s3_high_count} |
| MEDIUM级异常 | {s1_medium_count} | {s2_medium_count} | {s3_medium_count} |
| 资产负债率 | {s1_debt_ratio} | {s2_debt_ratio} | {s3_debt_ratio} |
| 应收账款占比 | {s1_ar_ratio} | {s2_ar_ratio} | {s3_ar_ratio} |

---

## 九、多维度雷达对比

| 维度 | {stock_1_name} | {stock_2_name} | {stock_3_name} |
|------|---------------|---------------|---------------|
| 基本面 | {s1_fundamental} | {s2_fundamental} | {s3_fundamental} |
| 估值 | {s1_valuation} | {s2_valuation} | {s3_valuation} |
| 技术面 | {s1_technical} | {s2_technical} | {s3_technical} |
| 动量 | {s1_momentum} | {s2_momentum} | {s3_momentum} |
| 风险 | {s1_anomaly} | {s2_anomaly} | {s3_anomaly} |
| **综合** | **{s1_total}** | **{s2_total}** | **{s3_total}** |

---

## 十、综合结论

### 对比总结

{comparison_summary}

### 投资建议

| 排序 | 股票 | 建议 | 核心理由 |
|------|------|------|----------|
| 1 | {rank_1_stock} | {rank_1_suggestion} | {rank_1_reason} |
| 2 | {rank_2_stock} | {rank_2_suggestion} | {rank_2_reason} |
| 3 | {rank_3_stock} | {rank_3_suggestion} | {rank_3_reason} |

---

> 风险提示: 本报告基于量化模型自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。

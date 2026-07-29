---
name: investment-report-generation
version: 1.0.0
author: FinAssistant
description: |
  个股投资研报生成技能。综合基本面、估值、技术面、风险检测结果，
  为每只入选股票生成结构化的 Markdown 投资研报。
  当需要生成投资报告、个股分析报告时触发。
tags: [finance, report, research, a-share]
allowed_tools: [executeCommand, readFile, writeFile]
---

# 投资研报生成技能

## When to Use
- "生成XX的投资研报"
- "为投资组合生成研究报告"
- 需要输出个股研报 .md 文件时

## Execution Steps

### Step 1: 收集分析数据
汇总各维度分析结果：
- 基本面指标（ROE、毛利率、增长率）
- 估值数据（PE/PB分位、估值水平）
- 技术面信号（趋势、MACD、RSI）
- 异常检测结果

### Step 2: 生成研报
```bash
python scripts/report_generator.py --ts_code {ts_code} --output_dir output/个股投资研报/
```

### Step 3: 研报结构

## Output Schema

```markdown
# {公司名称}({代码}) 投资研究报告

## 一、公司概况
| 项目 | 内容 |
|------|------|
| 股票代码 | {代码} |
| 股票名称 | {名称} |
| 所属板块 | {板块} |
| 综合评分 | {分数} / 100 |

## 二、财务分析
### 2.1 核心指标
| 指标 | 数值 |
|------|------|
| ROE | XX% |
| 毛利率 | XX% |
| ... | ... |

### 2.2 成长性
| 指标 | 数值 |
|------|------|
| 营收同比增长 | XX% |
| 净利润同比增长 | XX% |

## 三、估值分析
| 指标 | 当前值 | 历史分位 | 估值水平 |
|------|--------|----------|----------|
| PE_TTM | XX | XX% | XX |
| PB | XX | XX% | XX |

## 四、技术面分析
| 指标 | 数值 |
|------|------|
| MA趋势 | XX |
| MACD信号 | XX |
| RSI信号 | XX |

## 五、风险检测
{异常检测结果}

## 六、投资建议
综合评分: XX/100
建议: ...

> 风险提示: 本报告基于量化模型自动生成，仅供参考，不构成投资建议。
```

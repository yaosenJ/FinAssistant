---
name: financial-analysis-team
version: 1.0.0
author: FinAssistant
description: |
  A股上市公司多维度金融分析团队技能。由协调者统筹基本面分析师、估值分析师、
  技术面分析师、风险管理者四个角色协作，完成从选股到研报的全流程分析。
  适用于需要综合多维度分析的投资决策场景。
kind: team-skill
tags: [finance, team, multi-agent, a-share, portfolio]
roles:
  - id: coordinator
    purpose: 统筹任务分解、调度各分析师、聚合结果、输出最终投资组合和研报
    skills: [portfolio-construction, investment-report-generation]
    tools: [executeCommand, readFile, writeFile]
  - id: fundamental-analyst
    purpose: 分析公司基本面指标（ROE、毛利率、现金流、成长性），输出基本面评分
    skills: [stock-fundamental-analysis]
    tools: [executeCommand, readFile]
  - id: valuation-analyst
    purpose: 分析公司估值水平（PE/PB历史分位），判断高估/低估，输出估值评分
    skills: [stock-valuation-analysis]
    tools: [executeCommand, readFile]
  - id: technical-analyst
    purpose: 分析技术面指标（MA、MACD、RSI、KDJ），识别趋势和买卖信号
    skills: [stock-technical-analysis]
    tools: [executeCommand, readFile]
  - id: risk-manager
    purpose: 检测财务异常（现金流骤降、应收账款激增、商誉减值等），评估风险等级
    skills: [financial-anomaly-detection]
    tools: [executeCommand, readFile]
---

# 金融分析团队

## 团队概述

本团队由5个专业角色组成，覆盖投资分析的完整链条：
基本面分析 → 估值分析 → 技术面分析 → 风险检测 → 组合构建 → 研报生成

## 工作流程

协调者接收用户需求后，将分析任务分配给各专业分析师并行执行，
汇总评分后由协调者完成组合构建和研报生成。

详见 `workflow.md`。

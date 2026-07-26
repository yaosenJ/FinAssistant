#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务数据查询工具
查询上市公司三大财务报表数据（利润表、资产负债表、现金流量表）

功能:
- 按股票代码查询财务报表（支持 ts_code 和 symbol）
- 按报表类型筛选（利润表/资产负债表/现金流量表）
- 按报告日期范围筛选
- 提取指定财务指标字段
- 默认返回最近3期报表数据

数据来源: market_data.stock_financial 表（JSON 存储）

用法:
    from tools.financial_query import query_financial_data
    print(query_financial_data(ts_code='600519.SH'))
    print(query_financial_data(ts_code='600519.SH', report_type='利润表'))
    print(query_financial_data(ts_code='600519.SH', account_name='净利润'))
"""

import json
import logging

try:
    from tools.db import get_connection
except ImportError:
    from db import get_connection

logger = logging.getLogger(__name__)

# 报表类型映射（中文 → 数据库存储值）
REPORT_TYPE_MAP = {
    '利润表': 'income',
    'income': 'income',
    '资产负债表': 'balance',
    'balance': 'balance',
    '现金流量表': 'cashflow',
    'cashflow': 'cashflow',
}

# 报表类型中文名（反向映射）
REPORT_TYPE_CN = {
    'income': '利润表',
    'balance': '资产负债表',
    'cashflow': '现金流量表',
}


def _safe_float(val):
    """安全转 float"""
    if val is None:
        return None
    try:
        s = str(val).replace(',', '').replace('%', '').strip()
        if not s or s == '--' or s == '-':
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _format_value(val):
    """格式化数值显示"""
    f = _safe_float(val)
    if f is None:
        return str(val) if val is not None else '--'
    # 大数字用亿为单位
    if abs(f) >= 1e8:
        return f"{f / 1e8:,.2f}亿"
    elif abs(f) >= 1e4:
        return f"{f / 1e4:,.2f}万"
    else:
        return f"{f:,.2f}"


def _get_reports_by_ts_code(ts_code, statement_type=None, start_date=None, end_date=None, limit=3):
    """按 ts_code 查询财务报表

    Args:
        ts_code: 带后缀的股票代码，如 600519.SH
        statement_type: 报表类型 (income/balance/cashflow)，None 表示全部
        start_date: 起始报告日期 (YYYYMMDD 或 YYYY-MM-DD)
        end_date: 截止报告日期 (YYYYMMDD 或 YYYY-MM-DD)
        limit: 返回条数，默认3

    Returns:
        list: [(statement_type, report_date, report_data_dict), ...]
    """
    # 日期格式标准化（去掉横杠）
    if start_date:
        start_date = start_date.replace('-', '')
    if end_date:
        end_date = end_date.replace('-', '')

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if statement_type:
                # 查询指定报表类型
                types_to_query = [statement_type]
            else:
                # 查询所有报表类型
                types_to_query = ['income', 'balance', 'cashflow']

            all_results = []
            for stype in types_to_query:
                conditions = ["ts_code = %s", "statement_type = %s"]
                params = [ts_code, stype]

                if start_date:
                    conditions.append("report_date >= %s")
                    params.append(start_date)
                if end_date:
                    conditions.append("report_date <= %s")
                    params.append(end_date)

                where_clause = " AND ".join(conditions)
                sql = f"""
                    SELECT statement_type, report_date, report_data
                    FROM stock_financial
                    WHERE {where_clause}
                    ORDER BY report_date DESC
                    LIMIT %s
                """
                params.append(limit)
                cursor.execute(sql, params)

                for row in cursor.fetchall():
                    st = row[0]
                    rd = row[1]
                    data = row[2]
                    if isinstance(data, str):
                        data = json.loads(data)
                    all_results.append((st, rd, data))

            # 按报告日期排序
            all_results.sort(key=lambda x: x[1], reverse=True)
            return all_results
    finally:
        conn.close()


def _get_reports_by_symbol(symbol, statement_type=None, start_date=None, end_date=None, limit=3):
    """按纯数字代码查询，先通过 company_info 转换为 ts_code"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ts_code FROM company_info WHERE symbol = %s LIMIT 1", (symbol,))
            row = cursor.fetchone()
            if not row:
                return None, f"未找到股票代码: {symbol}"
            ts_code = row[0]
    finally:
        conn.close()

    results = _get_reports_by_ts_code(ts_code, statement_type, start_date, end_date, limit)
    return ts_code, results


def _format_single_report(ts_code, statement_type, report_date, data, account_name=None):
    """格式化单份报表"""
    type_cn = REPORT_TYPE_CN.get(statement_type, statement_type)

    if account_name:
        # 只提取指定字段
        val = data.get(account_name)
        if val is None:
            return f"[{ts_code}] {type_cn} ({report_date}): 未找到字段 \"{account_name}\""
        return f"股票: {ts_code} | 报表: {type_cn} | 日期: {report_date} | {account_name}: {_format_value(val)}"

    # 提取关键字段展示
    result = f"【{type_cn}】报告日期: {report_date}\n"

    if statement_type == 'income':
        fields = [
            ('营业总收入', ['营业总收入', '营业收入']),
            ('营业成本', ['营业成本']),
            ('净利润', ['净利润', '归属于母公司所有者的净利润', '归属于母公司股东的净利润']),
        ]
    elif statement_type == 'balance':
        fields = [
            ('资产总计', ['资产总计']),
            ('负债合计', ['负债合计']),
            ('股东权益', ['归属于母公司股东权益合计', '归属于母公司所有者权益', '所有者权益（或股东权益）合计']),
        ]
    elif statement_type == 'cashflow':
        fields = [
            ('经营活动现金流净额', ['经营活动产生的现金流量净额']),
            ('投资活动现金流净额', ['投资活动产生的现金流量净额']),
            ('筹资活动现金流净额', ['筹资活动产生的现金流量净额']),
        ]
    else:
        # 未知类型，展示所有字段
        for k, v in data.items():
            if k != '报告日':
                result += f"  {k}: {_format_value(v)}\n"
        return result

    for label, candidates in fields:
        for name in candidates:
            val = data.get(name)
            if val is not None:
                result += f"  {label}: {_format_value(val)}\n"
                break
        else:
            result += f"  {label}: --\n"

    return result


def query_financial_data(
    ts_code=None,
    symbol=None,
    report_type='所有报表',
    account_name=None,
    start_date=None,
    end_date=None,
    limit=3,
):
    """
    查询上市公司财务数据

    支持按股票代码、报表类型、报告日期、财务指标名称进行灵活查询。

    Args:
        ts_code: 带交易所后缀的股票代码（如 600519.SH）
        symbol: 纯数字股票代码（如 600519），与 ts_code 二选一
        report_type: 报表类型，默认"所有报表"
                     可选：利润表/income、资产负债表/balance、现金流量表/cashflow、所有报表
        account_name: 指定财务指标名称（如"净利润"、"营业收入"），不指定则返回关键指标汇总
        start_date: 起始报告日期（格式：YYYYMMDD 或 YYYY-MM-DD）
        end_date: 截止报告日期（格式：YYYYMMDD 或 YYYY-MM-DD）
        limit: 每种报表返回的期数，默认3（最近3期）

    Returns:
        str: 格式化的财务数据
    """
    # 参数校验
    if not ts_code and not symbol:
        return "请提供 ts_code（如 600519.SH）或 symbol（如 600519）"

    # 解析报表类型
    statement_type = None
    if report_type and report_type != '所有报表':
        statement_type = REPORT_TYPE_MAP.get(report_type)
        if not statement_type:
            valid = ', '.join(REPORT_TYPE_MAP.keys())
            return f"无效报表类型: {report_type}，可选值: {valid}"

    # 查询数据
    if ts_code:
        actual_ts_code = ts_code
        results = _get_reports_by_ts_code(ts_code, statement_type, start_date, end_date, limit)
    else:
        actual_ts_code, results = _get_reports_by_symbol(symbol, statement_type, start_date, end_date, limit)
        if isinstance(results, str):
            return results  # 错误信息

    if not results:
        return f"未找到 {actual_ts_code} 的财务数据"

    # 格式化输出
    output = f"=== {actual_ts_code} 财务数据查询 ===\n"
    output += f"查询到 {len(results)} 条记录\n"

    for st, rd, data in results:
        output += f"\n{'─' * 40}\n"
        output += _format_single_report(actual_ts_code, st, rd, data, account_name)

    return output


if __name__ == '__main__':
    # 测试查询
    print("\n1. 查询贵州茅台最近3期利润表:")
    print(query_financial_data(ts_code='600519.SH', report_type='利润表'))

    print("\n2. 查询贵州茅台净利润:")
    print(query_financial_data(ts_code='600519.SH', account_name='净利润'))

    print("\n3. 查询贵州茅台所有报表:")
    print(query_financial_data(ts_code='600519.SH', limit=1))

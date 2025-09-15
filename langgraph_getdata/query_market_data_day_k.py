#!/usr/bin/python3
# -*- coding: utf-8 -*-

from typing import Optional, List
from datetime import datetime, timedelta
import mysql.connector
from langchain_core.tools import tool

# MySQL 连接配置
MYSQL_CONFIG = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'market_data',
    'charset': 'utf8mb4',  # 添加字符集配置
    'collation': 'utf8mb4_general_ci'  # 添加排序规则
}
@tool
def query_stock_market_data(
        symbol: Optional[str] = None,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        limit: int = 500
) -> str:
    """
    查询股票市场日线数据，包含以下字段：
    - trade_date: 交易日期 (YYYY-MM-DD)
    - symbol: 股票代码
    - ts_code: 带市场后缀的股票代码
    - open: 开盘价
    - close: 收盘价
    - high: 最高价
    - low: 最低价
    - pre_close: 前收盘价
    - change_data: 涨跌额
    - pct_chg: 涨跌幅(%)
    - volume: 成交量(手)
    - amount: 成交额(万元)
    - pe: 市盈率
    - pb: 市净率
    - total_mv: 总市值(万元)
    - circ_mv: 流通市值(万元)
    - ln_pctchg: 对数收益率

    参数说明：
    - symbol: 股票代码(不带后缀)
    - ts_code: 股票代码(带后缀，如000001.SZ)
    - start_date: 开始日期(YYYY-MM-DD)
    - end_date: 结束日期(YYYY-MM-DD)
    - fields: 需要返回的字段列表
    - limit: 返回结果数量限制

    示例调用：
    - 查询贵州茅台最近10个交易日数据: ts_code="600519.SH"
    - 查询平安银行2023年数据: ts_code="000001.SZ", start_date="2023-01-01", end_date="2023-12-31"
    - 查询最近一个月创业板指成分股: symbol="399006", start_date="2023-03-01"
    """

    # 参数校验
    if not any([symbol, ts_code]):
        return "必须提供symbol或ts_code参数"

    # 默认字段
    default_fields = [
        'trade_date', 'symbol', 'ts_code', 'open', 'close', 'high', 'low',
        'pct_chg', 'volume', 'amount', 'pe', 'pb', 'total_mv'
    ]

    # 处理字段选择
    if fields:
        # 验证请求的字段是否有效
        valid_fields = [
            'trade_date', 'symbol', 'ts_code', 'open', 'close', 'high', 'low',
            'pre_close', 'change_data', 'pct_chg', 'volume', 'amount', 'pe',
            'pb', 'total_mv', 'total_share', 'float_share', 'circ_mv', 'ln_pctchg'
        ]
        invalid_fields = [f for f in fields if f not in valid_fields]
        if invalid_fields:
            return f"无效字段: {', '.join(invalid_fields)}. 有效字段包括: {', '.join(valid_fields)}"
    else:
        fields = default_fields

    # 处理日期默认值
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    conn = None
    try:
        # 连接数据库
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建查询
        query = f"SELECT {', '.join(fields)} FROM market_data_day_k WHERE "
        conditions = []
        params = []

        # 添加股票代码条件
        if ts_code:
            conditions.append("ts_code = %s COLLATE utf8mb4_general_ci")
            params.append(ts_code)
        elif symbol:
            conditions.append("symbol = %s COLLATE utf8mb4_general_ci")
            params.append(symbol)

        # 添加日期条件
        conditions.append("trade_date BETWEEN %s AND %s")
        params.extend([start_date, end_date])

        query += " AND ".join(conditions) + f" ORDER BY trade_date DESC LIMIT {limit}"

        # 执行查询
        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return "未找到符合条件的股票市场数据"

        # 格式化结果
        output = []
        for row in results:
            formatted_row = []
            for field in fields:
                value = row.get(field)
                # 特殊格式化处理
                if field == 'trade_date':
                    formatted_row.append(f"日期: {value}")
                elif field == 'pct_chg':
                    formatted_value = f"{value}%" if value is not None else "N/A"
                    formatted_row.append(f"涨跌幅: {formatted_value}")
                elif field in ['volume', 'amount', 'total_mv', 'circ_mv']:
                    formatted_value = f"{float(value):,.2f}" if value is not None else "N/A"
                    formatted_row.append(f"{field}: {formatted_value}")
                elif field in ['pe', 'pb']:
                    formatted_value = f"{float(value):.2f}" if value is not None else "N/A"
                    formatted_row.append(f"{field}: {formatted_value}")
                else:
                    formatted_value = value if value is not None else "N/A"
                    formatted_row.append(f"{field}: {formatted_value}")
            output.append(" | ".join(formatted_row))

        return "\n\n".join(output)

    except mysql.connector.Error as err:
        return f"数据库错误: {err}"
    except Exception as e:
        return f"查询失败: {str(e)}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# 示例使用

if __name__ == "__main__":
    from langchain.tools import tool
    from langchain_community.chat_models.tongyi import ChatTongyi
    from langchain.agents import initialize_agent, AgentType
    import mysql.connector

    chatLLM = ChatTongyi(
        model="qwen-max",
        temperature=0,
        api_key="sk-48d14c20891")
    tools = [query_stock_market_data]
    agent = initialize_agent(tools, chatLLM, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                             verbose=True)
    # agent.run("贵州茅台最近5个交易日数据")
    # agent.run("贵州茅台最近5个交易日数据中的收盘价")
    agent.run("贵州茅台股票最近能不能买")
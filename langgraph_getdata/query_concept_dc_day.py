# !/usr/bin/python3
# -*- coding: utf-8 -*-
from typing import Optional, List
from datetime import datetime, timedelta
from langchain_core.tools import tool
import mysql.connector

# MySQL 连接配置
MYSQL_CONFIG = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'market_data',
    'charset': 'utf8mb4'
}

@tool
def get_concept_market_data(
        concept_name: Optional[str] = None,
        concept_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        limit: int = 10
) -> str:
    """
    查询概念板块市场数据，包含以下字段：
    - concept_ts_code: 概念代码
    - concept_name: 概念名称(如"军工")
    - trade_date: 交易日期
    - open: 开盘点位
    - close: 收盘点位
    - high: 最高点位
    - low: 最低点位
    - pct_chg: 涨跌幅(%)
    - change_data: 涨跌额
    - vol: 成交量
    - amount: 成交额(万元)
    - pct_change: 振幅(%)
    - turnover_rate: 换手率(%)

    参数说明：
    - concept_name: 概念名称(支持模糊查询)
    - concept_code: 概念代码
    - start_date: 开始日期(YYYY-MM-DD)
    - end_date: 结束日期(YYYY-MM-DD)
    - fields: 需要返回的字段列表
    - limit: 返回结果数量限制

    示例：
    - 查询"军工"概念最近数据: get_concept_market_data(concept_name="军工")
    - 查询特定概念代码30天数据: get_concept_market_data(concept_code="TS1001", limit=30)
    """
    # 参数校验
    if not any([concept_name, concept_code]):
        return "必须提供concept_name或concept_code参数"

    # 默认字段
    default_fields = [
        'trade_date', 'concept_ts_code', 'concept_name',
        'close', 'pct_chg', 'amount', 'turnover_rate'
    ]

    # 处理字段选择
    if fields:
        valid_fields = [
            'concept_ts_code', 'concept_name', 'trade_date',
            'open', 'close', 'high', 'low', 'pct_chg',
            'change_data', 'vol', 'amount', 'pct_change', 'turnover_rate'
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
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建查询
        query = f"SELECT {', '.join(fields)} FROM concept_dc_day WHERE "
        conditions = []
        params = []

        if concept_code:
            conditions.append("concept_ts_code = %s")
            params.append(concept_code)
        elif concept_name:
            conditions.append("concept_name LIKE %s")
            params.append(f"%{concept_name}%")

        conditions.append("trade_date BETWEEN %s AND %s")
        params.extend([start_date, end_date])

        query += " AND ".join(conditions) + f" ORDER BY trade_date DESC LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return "未找到符合条件的概念板块数据"

        # 格式化结果
        output = []
        for row in results:
            formatted_row = []
            for field in fields:
                value = row.get(field)

                # 特殊格式化处理
                if field == 'trade_date':
                    formatted_row.append(f"日期: {value}")
                elif field == 'concept_name':
                    formatted_row.append(f"概念: {value}")
                elif field == 'concept_ts_code':
                    formatted_row.append(f"代码: {value}")
                elif field in ['pct_chg', 'pct_change', 'turnover_rate']:
                    formatted_value = f"{value}%" if value is not None else "N/A"
                    formatted_row.append(f"{field}: {formatted_value}")
                elif field in ['amount', 'vol']:
                    formatted_value = f"{float(value):,.2f}" if value is not None else "N/A"
                    formatted_row.append(f"{field}: {formatted_value}")
                else:
                    formatted_value = value if value is not None else "N/A"
                    formatted_row.append(f"{field}: {formatted_value}")

            output.append("\n".join(formatted_row))

        return "\n\n".join(output)

    except mysql.connector.Error as err:
        return f"数据库错误: {err}"
    except Exception as e:
        return f"查询失败: {str(e)}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@tool
def get_top_concepts(
        sort_field: str = 'pct_chg',
        top_n: int = 5,
        trade_date: Optional[str] = None
) -> str:
    """
    查询表现最好的概念板块排行

    参数：
    - sort_field: 排序字段(默认pct_chg，可选amount/vol/turnover_rate)
    - top_n: 返回数量(默认5)
    - trade_date: 指定日期(默认最新交易日)

    返回：
    - 概念名称
    - 概念代码
    - 排序字段值
    - 其他关键指标

    示例：
    - 查询涨幅前5概念: get_top_concepts()
    - 查询成交额前3概念: get_top_concepts(sort_field='amount', top_n=3)
    """
    # 验证排序字段
    valid_sort_fields = ['pct_chg', 'amount', 'vol', 'turnover_rate']
    if sort_field not in valid_sort_fields:
        return f"无效排序字段，可选: {', '.join(valid_sort_fields)}"

    if not trade_date:
        trade_date = datetime.now().strftime('%Y-%m-%d')

    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT concept_ts_code, concept_name, trade_date, 
               pct_chg, amount, vol, turnover_rate
        FROM concept_dc_day
        WHERE trade_date = %s
        ORDER BY %s DESC
        LIMIT %s
        """ % ('%s', sort_field, '%s')

        cursor.execute(query, (trade_date, top_n))
        results = cursor.fetchall()

        if not results:
            return f"未找到{trade_date}的概念板块数据"

        output = [f"{trade_date} 概念板块排行(按{sort_field}):"]
        for i, row in enumerate(results, 1):
            concept_info = [
                f"{i}. {row['concept_name']}({row['concept_ts_code']})",
                f"  涨跌幅: {row['pct_chg']}%",
                f"  成交额: {float(row['amount']):,.2f}万元",
                f"  成交量: {float(row['vol']):,.2f}",
                f"  换手率: {row['turnover_rate']}%"
            ]
            output.append("\n".join(concept_info))

        return "\n\n".join(output)

    except mysql.connector.Error as err:
        return f"数据库错误: {err}"
    except Exception as e:
        return f"查询失败: {str(e)}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    from langchain.tools import tool
    from langchain_community.chat_models.tongyi import ChatTongyi
    from langchain.agents import initialize_agent, AgentType
    import mysql.connector

    chatLLM = ChatTongyi(
        model="qwen-max",
        temperature=0,
        api_key="sk-48d14c208910")
    tools = [get_concept_market_data, get_top_concepts]
    agent = initialize_agent(tools, chatLLM, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                             verbose=True)

    # agent.run("军工概念最近涨跌情况是怎么样的")
    agent.run("""{"company": [], "content": [], "sectors": ["军工"]},{"market": {"start_date": "2025-01-06", "end_date": "2025-04-06"}, "fin_account": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]}""")


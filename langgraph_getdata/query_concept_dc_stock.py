# !/usr/bin/python3
# -*- coding: utf-8 -*-

from typing import Optional, List
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
def get_concept_stocks(
        concept_name: Optional[str] = None,
        concept_code: Optional[str] = None,
        limit: int = 200
) -> str:
    """
    查询概念板块的成分股列表

    参数:
    - concept_name: 概念名称(支持模糊查询，如"腾讯云")
    - concept_code: 概念代码(如"TS1001")
    - limit: 返回结果数量限制

    返回字段:
    - 概念信息: 代码,名称
    - 成分股列表: 股票代码,公司名称

    示例:
    - 查询"腾讯云"概念成分股: get_concept_stocks(concept_name="腾讯云")
    - 查询特定概念代码成分股: get_concept_stocks(concept_code="TS1001")
    """
    # 参数校验
    if not any([concept_name, concept_code]):
        return "必须提供concept_name或concept_code参数"

    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建查询
        query = """
        SELECT 
            c.concept_ts_code, 
            c.concept_name,
            c.ts_code,
            c.symbol,
            c.company_name
        FROM concept_dc_stock c
        """

        conditions = []
        params = []

        if concept_code:
            conditions.append("c.concept_ts_code = %s")
            params.append(concept_code)
        elif concept_name:
            conditions.append("c.concept_name LIKE %s")
            params.append(f"%{concept_name}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return "未找到符合条件的成分股数据"

        # 按概念分组
        concept_map = {}
        for row in results:
            concept_key = (row['concept_ts_code'], row['concept_name'])
            if concept_key not in concept_map:
                concept_map[concept_key] = []
            concept_map[concept_key].append(row)

        # 格式化输出
        output = []
        for (concept_code, concept_name), stocks in concept_map.items():
            concept_info = [
                f"概念代码: {concept_code}",
                f"概念名称: {concept_name}",
                f"成分股数量: {len(stocks)}",
                "成分股列表:"
            ]

            stock_list = []
            for stock in stocks:
                stock_list.append(
                    f"  {stock['company_name']}({stock['symbol']}, {stock['ts_code']})"
                )

            output.append("\n".join(concept_info + stock_list))

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
def get_stock_concepts(
        symbol: Optional[str] = None,
        ts_code: Optional[str] = None,
        company_name: Optional[str] = None,
        limit: int = 100
) -> str:
    """
    查询股票所属的概念板块

    参数:
    - symbol: 股票代码(不带后缀)
    - ts_code: 股票代码(带后缀，如000001.SZ)
    - company_name: 公司名称(支持模糊查询)
    - limit: 返回结果数量限制

    返回字段:
    - 股票基本信息: 代码,名称
    - 所属概念列表: 概念代码,概念名称

    示例:
    - 查询股票所属概念: get_stock_concepts(ts_code="000001.SZ")
    - 按公司名称查询: get_stock_concepts(company_name="浪潮信息")
    """
    # 参数校验
    if not any([symbol, ts_code, company_name]):
        return "必须提供symbol/ts_code/company_name参数"

    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建查询
        query = """
        SELECT 
            c.ts_code,
            c.symbol,
            c.company_name,
            c.concept_ts_code,
            c.concept_name
        FROM concept_dc_stock c
        """

        conditions = []
        params = []

        if ts_code:
            conditions.append("c.ts_code = %s")
            params.append(ts_code)
        elif symbol:
            conditions.append("c.symbol = %s")
            params.append(symbol)
        elif company_name:
            conditions.append("c.company_name LIKE %s")
            params.append(f"%{company_name}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return "未找到该股票的概念板块信息"

        # 按股票分组
        stock_map = {}
        for row in results:
            stock_key = (row['ts_code'], row['symbol'], row['company_name'])
            if stock_key not in stock_map:
                stock_map[stock_key] = []
            stock_map[stock_key].append((row['concept_ts_code'], row['concept_name']))

        # 格式化输出
        output = []
        for (ts_code, symbol, company_name), concepts in stock_map.items():
            stock_info = [
                f"股票代码: {symbol}({ts_code})",
                f"公司名称: {company_name}",
                f"所属概念数量: {len(concepts)}",
                "概念板块列表:"
            ]

            concept_list = []
            for concept_code, concept_name in concepts:
                concept_list.append(f"  {concept_name}({concept_code})")

            output.append("\n".join(stock_info + concept_list))

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
    # # 示例1: 查询概念成分股
    # print("=== 腾讯云概念成分股 ===")
    # print(get_concept_stocks(concept_name="腾讯云"))
    # print("\n" + "=" * 50 + "\n")
    #
    # # 示例2: 查询股票所属概念
    # print("=== 浪潮信息所属概念 ===")
    # print(get_stock_concepts(company_name="浪潮信息"))
    # print("\n" + "=" * 50 + "\n")
    #
    # # 示例3: 按股票代码查询
    # print("=== 股票代码查询所属概念 ===")
    # print(get_stock_concepts(ts_code="000001.SZ"))
    from langchain.tools import tool
    from langchain_community.chat_models.tongyi import ChatTongyi
    from langchain.agents import initialize_agent, AgentType
    import mysql.connector

    chatLLM = ChatTongyi(
        model="qwen-max",
        temperature=0,
        api_key="sk-48d14c208910")
    tools = [get_concept_stocks, get_stock_concepts]
    agent = initialize_agent(tools, chatLLM, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                             verbose=True)

    # agent.run("腾讯云有哪些成分股")
    agent.run("浪潮信息所属概念有哪些")

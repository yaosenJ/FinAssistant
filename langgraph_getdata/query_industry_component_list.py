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
def get_industry_stocks(
        industry_name: Optional[str] = None,
        industry_code: Optional[str] = None,
        industry_grade: Optional[str] = None,
        limit: int = 2000
) -> str:
    """
    查询行业成分股列表

    参数:
    - industry_name: 行业名称(支持模糊查询，如"计算机")
    - industry_code: 行业代码
    - industry_grade: 行业分类等级(如"L1")
    - limit: 返回结果数量限制

    返回字段:
    - 行业信息: 代码,名称,分类等级
    - 成分股列表: 股票代码,公司名称

    示例:
    - 查询"计算机"行业成分股: get_industry_stocks(industry_name="计算机")
    - 查询L1级特定行业: get_industry_stocks(industry_code="IND1001", industry_grade="L1")
    """
    # 参数校验
    if not any([industry_name, industry_code]):
        return "必须提供industry_name或industry_code参数"

    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建查询
        query = """
        SELECT 
            i.industry_code, 
            i.industry_name,
            i.industry_grade,
            i.ts_code,
            i.symbol,
            i.company_name
        FROM industry_component_list i
        """

        conditions = []
        params = []

        if industry_code:
            conditions.append("i.industry_code = %s")
            params.append(industry_code)
        elif industry_name:
            conditions.append("i.industry_name LIKE %s")
            params.append(f"%{industry_name}%")

        if industry_grade:
            conditions.append("i.industry_grade = %s")
            params.append(industry_grade)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return "未找到符合条件的行业成分股数据"

        # 按行业分组
        industry_map = {}
        for row in results:
            industry_key = (row['industry_code'], row['industry_name'], row['industry_grade'])
            if industry_key not in industry_map:
                industry_map[industry_key] = []
            industry_map[industry_key].append(row)

        # 格式化输出
        output = []
        for (industry_code, industry_name, industry_grade), stocks in industry_map.items():
            industry_info = [
                f"行业代码: {industry_code}",
                f"行业名称: {industry_name}",
                f"行业等级: {industry_grade}",
                f"成分股数量: {len(stocks)}",
                "成分股列表:"
            ]

            stock_list = []
            for stock in stocks:
                stock_list.append(
                    f"  {stock['company_name']}({stock['symbol']}, {stock['ts_code']})"
                )

            output.append("\n".join(industry_info + stock_list))

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
def get_stock_industries(
        symbol: Optional[str] = None,
        ts_code: Optional[str] = None,
        company_name: Optional[str] = None,
        limit: int = 100
) -> str:
    """
    查询股票所属的行业信息

    参数:
    - symbol: 股票代码(不带后缀)
    - ts_code: 股票代码(带后缀，如000001.SZ)
    - company_name: 公司名称(支持模糊查询)
    - limit: 返回结果数量限制

    返回字段:
    - 股票基本信息: 代码,名称
    - 所属行业列表: 行业代码,行业名称,行业等级

    示例:
    - 查询股票所属行业: get_stock_industries(ts_code="000001.SZ")
    - 按公司名称查询: get_stock_industries(company_name="招商银行")
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
            i.ts_code,
            i.symbol,
            i.company_name,
            i.industry_code,
            i.industry_name,
            i.industry_grade
        FROM industry_component_list i
        """

        conditions = []
        params = []

        if ts_code:
            conditions.append("i.ts_code = %s")
            params.append(ts_code)
        elif symbol:
            conditions.append("i.symbol = %s")
            params.append(symbol)
        elif company_name:
            conditions.append("i.company_name LIKE %s")
            params.append(f"%{company_name}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return "未找到该股票的行业信息"

        # 按股票分组
        stock_map = {}
        for row in results:
            stock_key = (row['ts_code'], row['symbol'], row['company_name'])
            if stock_key not in stock_map:
                stock_map[stock_key] = []
            stock_map[stock_key].append((row['industry_code'], row['industry_name'], row['industry_grade']))

        # 格式化输出
        output = []
        for (ts_code, symbol, company_name), industries in stock_map.items():
            stock_info = [
                f"股票代码: {symbol}({ts_code})",
                f"公司名称: {company_name}",
                f"所属行业数量: {len(industries)}",
                "行业分类列表:"
            ]

            industry_list = []
            for industry_code, industry_name, industry_grade in industries:
                industry_list.append(f"  {industry_name}({industry_code}, {industry_grade})")

            output.append("\n".join(stock_info + industry_list))

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
        api_key="sk-48d14c2089104d")
    tools = [get_industry_stocks, get_stock_industries]
    agent = initialize_agent(tools, chatLLM, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                             verbose=True)

    # agent.run("计算机行业成分股有哪些？")
    agent.run("招商银行所属行业是什么？")
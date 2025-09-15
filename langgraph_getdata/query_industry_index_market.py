# !/usr/bin/python3
# -*- coding: utf-8 -*-
from typing import Optional, List
from langchain_core.tools import tool
import mysql.connector

# MySQL 连接配置(添加字符集参数)
MYSQL_CONFIG = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'market_data',
    'charset': 'utf8mb4',  # 添加字符集配置
    'collation': 'utf8mb4_general_ci'
}
@tool
def get_industry_by_stock(
        symbol: Optional[str] = None,
        ts_code: Optional[str] = None,
        limit: int = 1
) -> str:
    """
    根据股票代码查询所属行业信息，返回行业名称和行业市场分类

    参数:
    - symbol: 股票代码(不带后缀)
    - ts_code: 股票代码(带后缀，如000001.SZ)
    - limit: 返回结果数量限制

    返回字段:
    - symbol: 股票代码
    - ts_code: 带市场后缀的股票代码
    - name: 行业名称
    - market: 行业市场分类，如L1
    - trade_date: 数据日期

    示例:
    - 查询贵州茅台所属行业: get_industry_by_stock(ts_code="600519.SH")
    - 查询平安银行所属行业: get_industry_by_stock(symbol="000001")
    """
    # 参数校验
    if not any([symbol, ts_code]):
        return "必须提供symbol或ts_code参数"

    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 修改查询逻辑，先找股票对应的行业代码，再查行业信息
        query = """
        SELECT i.symbol, i.ts_code, i.name, i.market, i.trade_date 
        FROM industry_index_market i
        JOIN (
            SELECT DISTINCT name, market 
            FROM industry_index_market 
            WHERE """

        conditions = []
        params = []

        if ts_code:
            conditions.append("ts_code = %s")
            params.append(ts_code)
        else:
            conditions.append("symbol = %s")
            params.append(symbol)

        query += " AND ".join(conditions) + " LIMIT 1) t ON i.name = t.name AND i.market = t.market"
        query += f" ORDER BY i.trade_date DESC LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            # 尝试直接查询
            direct_query = """
            SELECT symbol, ts_code, name, market, trade_date 
            FROM industry_index_market 
            WHERE """
            direct_query += " AND ".join(conditions) + f" ORDER BY trade_date DESC LIMIT {limit}"
            cursor.execute(direct_query, params)
            results = cursor.fetchall()
            if not results:
                return "未找到该股票对应的行业信息"

        output = []
        for row in results:
            formatted_row = [
                f"股票代码: {row['symbol']}",
                f"完整代码: {row['ts_code']}",
                f"行业名称: {row['name']}",
                f"行业分类: {row['market']}"
            ]
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


# @tool
# def get_stocks_by_industry(
#         industry_name: str,
#         market: Optional[str] = None,
#         limit: int = 1000
# ) -> str:
#     """
#     查询指定行业包含的股票列表
#
#     参数:
#     - industry_name: 行业名称(支持模糊查询)
#     - market: 行业市场分类(可选)
#     - limit: 返回结果数量限制
#
#     返回字段:
#     - symbol: 股票代码
#     - ts_code: 带市场后缀的股票代码
#     - name: 行业名称
#     - market: 行业市场分类
#     - trade_date: 数据日期
#     - close: 收盘价
#     - pct_chg: 涨跌幅
#
#     示例:
#     - 查询"白酒"行业股票: get_stocks_by_industry("白酒")
#     - 查询"银行"行业股票: get_stocks_by_industry("银行", market="L1)
#     """
#     conn = None
#     try:
#         conn = mysql.connector.connect(**MYSQL_CONFIG)
#         cursor = conn.cursor(dictionary=True)
#
#         query = """
#         SELECT symbol, ts_code, name, market, trade_date, close, pct_chg
#         FROM industry_index_market
#         WHERE name LIKE %s
#         """
#
#         # 处理字符集问题
#         industry_name = industry_name.encode('utf-8').decode('utf-8')
#         params = [f"%{industry_name}%"]
#
#         if market:
#             market = market.encode('utf-8').decode('utf-8')
#             query += " AND market = %s"
#             params.append(market)
#
#         query += f" ORDER BY trade_date DESC, pct_chg DESC LIMIT {limit}"
#
#         cursor.execute(query, params)
#         results = cursor.fetchall()
#
#         if not results:
#             return f"未找到行业'{industry_name}'的股票信息"
#
#         output = [f"行业查询: {industry_name} | 共找到 {len(results)} 条结果\n"]
#
#         for row in results:
#             # 修复涨跌幅字符串拼接问题
#             pct_chg = row['pct_chg']
#             if pct_chg is not None:
#                 pct_chg = f"{pct_chg}%"
#             else:
#                 pct_chg = "N/A"
#
#             formatted_row = [
#                 f"股票: {row['symbol']}({row['ts_code']})",
#                 f"行业: {row['name']}({row['market']})",
#                 f"日期: {row['trade_date']}",
#                 f"收盘价: {row['close'] if row['close'] is not None else 'N/A'}",
#                 f"涨跌幅: {pct_chg}"
#             ]
#             output.append("\n".join(formatted_row))
#
#         return "\n\n".join(output)
#
#     except mysql.connector.Error as err:
#         return f"数据库错误: {err}"
#     except Exception as e:
#         return f"查询失败: {str(e)}"
#     finally:
#         if conn and conn.is_connected():
#             cursor.close()
#             conn.close()

@tool
def get_stocks_by_industry(
        industry_name: str,
        market: Optional[str] = None,
        stock_limit: int = 30,  # 限制返回的股票数量
        days_limit: int = 30  # 每只股票返回的交易天数
) -> str:
    """
    查询指定行业包含的股票列表及每只股票最近3个交易日的交易信息

    参数:
    - industry_name: 行业名称(支持模糊查询)
    - market: 行业市场分类(可选)
    - stock_limit: 返回股票数量限制(默认10)
    - days_limit: 每只股票返回的交易天数(默认3)

    返回字段(每只股票):
    - 股票基本信息: 代码,名称
    - 最近3个交易日数据(日期,收盘价,涨跌幅)

    示例:
    - 查询"白酒"行业股票: get_stocks_by_industry("白酒")
    - 查询"银行"行业股票: get_stocks_by_industry("银行", market="L1")
    """
    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 第一步: 获取该行业下的股票列表
        stock_query = """
        SELECT DISTINCT symbol, ts_code, name, market
        FROM industry_index_market
        WHERE name LIKE %s
        """

        params = [f"%{industry_name}%"]

        if market:
            stock_query += " AND market = %s"
            params.append(market)

        stock_query += f" LIMIT {stock_limit}"

        cursor.execute(stock_query, params)
        stocks = cursor.fetchall()

        if not stocks:
            return f"未找到行业'{industry_name}'的股票信息"

        output = [f"行业查询: {industry_name} | 共找到 {len(stocks)} 只股票\n"]

        # 第二步: 对每只股票查询最近3个交易日数据
        for stock in stocks:
            # 查询该股票最近3个交易日数据
            data_query = """
            SELECT trade_date, close, pct_chg
            FROM industry_index_market
            WHERE ts_code = %s
            ORDER BY trade_date DESC
            LIMIT %s
            """
            cursor.execute(data_query, (stock['ts_code'], days_limit))
            daily_data = cursor.fetchall()

            # 格式化股票基本信息
            stock_info = [
                f"\n股票代码: {stock['symbol']}({stock['ts_code']})",
                f"行业名称: {stock['name']}",
                f"市场分类: {stock['market']}",
                "最近交易日数据:"
            ]

            # 格式化每日交易数据
            daily_info = []
            for data in daily_data:
                pct_chg = f"{data['pct_chg']}%" if data['pct_chg'] is not None else "N/A"
                daily_info.append(
                    f"  日期: {data['trade_date']} | "
                    f"收盘价: {data['close'] if data['close'] is not None else 'N/A'} | "
                    f"涨跌幅: {pct_chg}"
                )

            # 合并信息
            output.append("\n".join(stock_info + daily_info))

        return "\n".join(output)

    except mysql.connector.Error as err:
        return f"数据库错误: {err}"
    except Exception as e:
        return f"查询失败: {str(e)}"


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
    tools = [get_industry_by_stock, get_stocks_by_industry]
    agent = initialize_agent(tools, chatLLM, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                             verbose=True)

    agent.run("白酒行业包含哪些股票")
    # agent.run("801010.SI所属什么行业")



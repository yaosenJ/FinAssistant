# !/usr/bin/python3
# -*- coding: utf-8 -*-

from langchain_core.tools import tool
import mysql.connector  # 需要安装 mysql-connector-python

# MySQL 连接配置（建议通过环境变量管理敏感信息）
MYSQL_CONFIG = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'market_data'
}
@tool
def query_financial_data(
        symbol: str = None,
        ts_code: str = None,
        report_type: str = "所有报表",  # 默认值改为"所有报表"
        account_name: str = None,
        start_date: str = None,
        end_date: str = None
) -> str:
    """
    查询上市公司财务数据，支持以下查询条件：
    - symbol:     股票代码（无后缀，如：002622）
    - ts_code:    带交易所后缀的股票代码（如：002622.SZ）
    - report_type:报表类型（默认返回所有类型，可选：资产负债表/现金流量表/利润表/财务指标）
    - account_name: 财务指标名称（如不指定则返回所有指标）
    - start_date: 起始报告日期（格式：YYYY-MM-DD）
    - end_date:   截止报告日期（格式：YYYY-MM-DD）
     如果没有同时给报告起始和截止日期，请你用一个日期填充到start_date、end_date。如：查询2024-03-31的财报，把2024-03-31同时赋值到start_date和end_date
    当不指定报表类型时，默认返回所有类型的财务数据。
    """

    # 参数校验
    if not any([symbol, ts_code]):
        return "至少需要提供 symbol 或 ts_code 中的一个查询条件"

    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建基础条件
        conditions = []
        parameters = []

        # 股票代码条件
        if symbol:
            conditions.append("symbol = %s")
            parameters.append(symbol)
        if ts_code:
            conditions.append("ts_code = %s")
            parameters.append(ts_code)

        # 日期条件处理（新增核心逻辑）
        date_condition = []
        if start_date:
            date_condition.append("reportdate >= %s")
            parameters.append(start_date)
        if end_date:
            date_condition.append("reportdate <= %s")
            parameters.append(end_date)

        # 如果没有日期条件，获取最近3个报告日
        if not date_condition:
            date_subquery = "SELECT DISTINCT reportdate FROM fin_account"
            if conditions:
                date_subquery += " WHERE " + " AND ".join(conditions)
            date_subquery += " ORDER BY reportdate DESC LIMIT 3"
            cursor.execute(date_subquery, parameters.copy())  # 使用参数副本
            recent_dates = [row["reportdate"] for row in cursor.fetchall()]
            if recent_dates:
                date_condition.append(f"reportdate IN ({','.join(['%s'] * len(recent_dates))})")
                parameters.extend(recent_dates)

        # 报表类型处理（修改逻辑）
        valid_report_types = ["资产负债表", "现金流量表", "利润表", "财务指标"]
        if report_type and report_type != "所有报表":
            if report_type not in valid_report_types:
                return f"无效报表类型，可选值：{', '.join(valid_report_types)}"
            conditions.append("type = %s")
            parameters.append(report_type)

        # 财务指标条件
        if account_name:
            conditions.append("account = %s")
            parameters.append(account_name)

        # 修复后正确代码
        where_clause = " AND ".join(conditions + date_condition)
        base_query = f"""
            SELECT ts_code, reportdate, account, value, type 
            FROM fin_account
            WHERE {where_clause}
            ORDER BY reportdate DESC
        """

        cursor.execute(base_query, parameters)
        results = cursor.fetchall()
        # 处理查询结果
        if not results:
            return "未找到符合条件的财务数据"

        # 格式化输出
        output = []
        for row in results:
            formatted_row = (
                f"股票：{row['ts_code']} | 报表日：{row['reportdate']} | "
                f"报表类型：{row['type']} | {row['account']} => {float(row['value']):,}"
            )
            output.append(formatted_row)

        return "\n\n".join(output)

    except mysql.connector.Error as err:
        return f"数据库连接错误: {err}"
    except Exception as e:
        return f"查询执行失败：{str(e)}"
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
    tools = [query_financial_data]
    agent = initialize_agent(tools, chatLLM, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
    agent.run("请查询股票002622.SZ的2023-12-31的报表数据")

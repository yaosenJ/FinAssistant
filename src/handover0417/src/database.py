# !/usr/bin/python3
# -*- coding: utf-8 -*-
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime, timedelta
import bisect


def get_company_news_from_stock(stock, db_config, table_name='new_processed_daily_news', days_ago=None):
    """
    从MySQL数据库获取指定公司的新闻数据，基于交易日历计算日期范围

    参数:
        stock (str): 公司股票代码或名称
        db_config (dict): 数据库连接配置
        table_name (str): 数据库表名，默认为'new_processed_daily_news'
        days_ago (int): 查询前n个交易日的数据，None表示查询所有数据

    返回:
        DataFrame: 包含该公司新闻的DataFrame，包含trade_date, title, content列
    """
    try:
        # 对密码进行编码处理（特殊字符）
        encoded_password = quote_plus(db_config['password'])

        # 创建数据库连接字符串
        connection_str = (
            f"mysql+pymysql://{db_config['user']}:{encoded_password}@"
            f"{db_config['host']}:{db_config['port']}/"
            f"{db_config['database']}?charset=utf8mb4"
        )

        # 创建引擎（添加连接池和超时设置）
        engine = create_engine(
            connection_str,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            echo=False  # 设为True可查看SQL日志
        )

        # 构建基础SQL查询
        sql = f"""
        SELECT trade_date, title, content
        FROM {table_name}
        WHERE stock_name = :stock_name
        """

        params = {'stock_name': stock}

        # 如果指定了days_ago，添加日期条件
        if days_ago is not None:
            # 加载交易日历
            try:
                df_trade = pd.read_csv('../data/time.csv', dtype={'cal_date': str})
                df_trade['cal_date'] = pd.to_datetime(df_trade['cal_date'], format='%Y%m%d').dt.date
                trade_dates = sorted(df_trade['cal_date'].tolist())
            except Exception as e:
                print(f"加载交易日文件失败: {e}")
                return pd.DataFrame()

            today = datetime.now().date()

            # 查找最近的交易日
            index = bisect.bisect_right(trade_dates, today) - 1
            if index < 0:
                print("错误：当前日期早于所有交易日")
                return pd.DataFrame()

            end_date = trade_dates[index]

            # 计算起始日期
            start_index = index - (days_ago - 1)
            if start_index < 0:
                start_index = 0
                print(f"注意：请求的{days_ago}个交易日超出范围，将返回从{trade_dates[start_index]}到{end_date}的数据。")

            start_date = trade_dates[start_index]

            sql += " AND trade_date >= :start_date AND trade_date <= :end_date"
            params.update({'start_date': start_date, 'end_date': end_date})

        # 添加排序条件
        sql += " ORDER BY trade_date DESC"

        # 使用text()构造查询，参数化查询防止SQL注入
        sql = text(sql)

        # 执行查询
        with engine.connect() as connection:
            df = pd.read_sql(sql, connection, params=params)

        return df

    except Exception as e:
        print(f"数据库查询出错: {str(e)}")
        return pd.DataFrame()  # 返回空DataFrame


def get_company_news_from_industry(industry, db_config, table_name='new_processed_daily_news', days_ago=None):
    """
    从MySQL数据库获取指定行业的新闻数据

    参数:
        industry (str): 行业名称
        db_config (dict): 数据库连接配置
        table_name (str): 数据库表名，默认为'new_processed_daily_news'
        days_ago (int): 查询距当前日期前几天的数据，None表示查询所有数据

    返回:
        DataFrame: 包含该公司新闻的DataFrame，包含trade_date, title, content列
    """
    try:
        # 对密码进行编码处理（特殊字符）
        encoded_password = quote_plus(db_config['password'])

        # 创建数据库连接字符串
        connection_str = (
            f"mysql+pymysql://{db_config['user']}:{encoded_password}@"
            f"{db_config['host']}:{db_config['port']}/"
            f"{db_config['database']}?charset=utf8mb4"
        )

        # 创建引擎（添加连接池和超时设置）
        engine = create_engine(
            connection_str,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            echo=False  # 设为True可查看SQL日志
        )

        # 构建基础SQL查询
        sql = f"""
        SELECT trade_date, title, content
        FROM {table_name}
        WHERE industry_name = :industry_name
        """

        params = {'industry_name': industry}
        # 如果指定了days_ago，添加日期条件

        if days_ago is not None:
            # 加载交易日历
            try:
                df_trade = pd.read_csv('../data/time.csv', dtype={'cal_date': str})
                df_trade['cal_date'] = pd.to_datetime(df_trade['cal_date'], format='%Y%m%d').dt.date
                trade_dates = sorted(df_trade['cal_date'].tolist())
            except Exception as e:
                print(f"加载交易日文件失败: {e}")
                return pd.DataFrame()

            today = datetime.now().date()

            # 查找最近的交易日
            index = bisect.bisect_right(trade_dates, today) - 1
            if index < 0:
                print("错误：当前日期早于所有交易日")
                return pd.DataFrame()

            end_date = trade_dates[index]

            # 计算起始日期
            start_index = index - (days_ago - 1)
            if start_index < 0:
                start_index = 0
                print(f"注意：请求的{days_ago}个交易日超出范围，将返回从{trade_dates[start_index]}到{end_date}的数据。")

            start_date = trade_dates[start_index]

            sql += " AND trade_date >= :start_date AND trade_date <= :end_date"
            params.update({'start_date': start_date, 'end_date': end_date})

        # 添加排序条件
        sql += " ORDER BY trade_date DESC"

        # 使用text()构造查询，参数化查询防止SQL注入
        sql = text(sql)

        # 执行查询
        with engine.connect() as connection:
            df = pd.read_sql(sql, connection, params=params)

        return df

    except Exception as e:
        print(f"数据库查询出错: {str(e)}")
        return pd.DataFrame()  # 返回空DataFrame


def get_company_news_from_concept(concept, db_config, table_name='new_processed_daily_news', days_ago=None):
    """
    从MySQL数据库获取指定概念的新闻数据

    参数:
        concept (str): 概念名称
        db_config (dict): 数据库连接配置
        table_name (str): 数据库表名，默认为'new_processed_daily_news'
        days_ago (int): 查询距当前日期前几天的数据，None表示查询所有数据

    返回:
        DataFrame: 包含该公司新闻的DataFrame，包含trade_date, title, content列
    """
    try:
        # 对密码进行编码处理（特殊字符）
        encoded_password = quote_plus(db_config['password'])

        # 创建数据库连接字符串
        connection_str = (
            f"mysql+pymysql://{db_config['user']}:{encoded_password}@"
            f"{db_config['host']}:{db_config['port']}/"
            f"{db_config['database']}?charset=utf8mb4"
        )

        # 创建引擎（添加连接池和超时设置）
        engine = create_engine(
            connection_str,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            echo=False  # 设为True可查看SQL日志
        )

        # 构建基础SQL查询
        sql = f"""
        SELECT trade_date, title, content
        FROM {table_name}
        WHERE concept_name = :concept_name
        """

        params = {'concept_name': concept}
        # 如果指定了days_ago，添加日期条件

        if days_ago is not None:
            # 加载交易日历
            try:
                df_trade = pd.read_csv('../data/time.csv', dtype={'cal_date': str})
                df_trade['cal_date'] = pd.to_datetime(df_trade['cal_date'], format='%Y%m%d').dt.date
                trade_dates = sorted(df_trade['cal_date'].tolist())
            except Exception as e:
                print(f"加载交易日文件失败: {e}")
                return pd.DataFrame()

            today = datetime.now().date()

            # 查找最近的交易日
            index = bisect.bisect_right(trade_dates, today) - 1
            if index < 0:
                print("错误：当前日期早于所有交易日")
                return pd.DataFrame()

            end_date = trade_dates[index]

            # 计算起始日期
            start_index = index - (days_ago - 1)
            if start_index < 0:
                start_index = 0
                print(f"注意：请求的{days_ago}个交易日超出范围，将返回从{trade_dates[start_index]}到{end_date}的数据。")

            start_date = trade_dates[start_index]

            sql += " AND trade_date >= :start_date AND trade_date <= :end_date"
            params.update({'start_date': start_date, 'end_date': end_date})

        # 添加排序条件
        sql += " ORDER BY trade_date DESC"

        # 使用text()构造查询，参数化查询防止SQL注入
        sql = text(sql)

        # 执行查询
        with engine.connect() as connection:
            df = pd.read_sql(sql, connection, params=params)

        return df

    except Exception as e:
        print(f"数据库查询出错: {str(e)}")
        return pd.DataFrame()  # 返回空DataFrame


if __name__ == "__main__":
    # 数据库配置
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',  # 包含特殊字符也无需担心
        'database': 'stock_news'
    }

    # 测试查询
    target_stock = '机器人'
    company_news = get_company_news_from_stock(target_stock, db_config, days_ago=10)

    target_concept = '光伏'
    concept_news = get_company_news_from_concept(target_concept, db_config, days_ago=10)

    # if not company_news.empty:
    #     print(f"找到 {len(company_news)} 条关于 {target_stock} 的新闻:")
    #     print(company_news.head())  # 只打印前几条
    # else:
    #     print(f"没有找到关于 {target_stock} 的新闻，请检查：")
    #     print("1. 数据库连接配置是否正确")
    #     print("2. 该股票代码在数据库中是否存在")
    #     print("3. 表名是否正确（当前使用表名: stock_news）")

    if not concept_news.empty:
        print(f"找到 {len(concept_news)} 条关于 {target_concept} 的新闻:")
        print(company_news.head())  # 只打印前几条
    else:
        print(f"没有找到关于 {target_concept} 的新闻，请检查：")
        print("1. 数据库连接配置是否正确")
        print("2. 该股票代码在数据库中是否存在")
        print("3. 表名是否正确（当前使用表名: stock_news）")

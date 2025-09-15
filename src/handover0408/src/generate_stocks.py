# !/usr/bin/python3
# -*- coding: utf-8 -*-
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import json
import os


def get_unique_stocks(db_config, table_name='industry_component_list'):
    """
    获取数据库中所有唯一的股票代码/名称

    参数:
        db_config (dict): 数据库连接配置
        table_name (str): 数据库表名

    返回:
        list: 包含所有唯一company_name值的列表
    """
    try:
        # 对密码进行编码处理
        encoded_password = quote_plus(db_config['password'])

        # 创建数据库连接字符串
        connection_str = (
            f"mysql+pymysql://{db_config['user']}:{encoded_password}@"
            f"{db_config['host']}:{db_config['port']}/"
            f"{db_config['database']}?charset=utf8mb4"
        )

        # 创建引擎
        engine = create_engine(connection_str)

        # 查询所有唯一的company_name值
        query = text(f"SELECT DISTINCT company_name FROM {table_name} ORDER BY company_name")

        with engine.connect() as connection:
            df = pd.read_sql(query, connection)

        return df['company_name'].tolist()

    except Exception as e:
        print(f"数据库查询出错: {str(e)}")
        return []


def save_to_json(data, filename='stocks.json'):
    """
    将数据保存为JSON文件

    参数:
        data: 要保存的数据
        filename (str): 保存的文件名
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print(f"数据已成功保存到 {os.path.abspath(filename)}")
        return True
    except Exception as e:
        print(f"保存文件出错: {str(e)}")
        return False


if __name__ == "__main__":
    # 数据库配置
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'market_data'
    }

    # 1. 获取所有股票代码/名称
    unique_stocks = get_unique_stocks(db_config)

    if not unique_stocks:
        print("没有找到任何股票数据，或查询出错")
        exit()

    print(f"数据库中共有 {len(unique_stocks)} 个不同的股票代码/名称")

    # 2. 保存为JSON文件
    output_data = {
        "update_time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(unique_stocks),
        "stocks": unique_stocks
    }

    # 保存到当前目录下的data文件夹中
    save_to_json(output_data, '../data/stocks.json')

    # 3. 可选：打印前20个结果预览
    print("\n前20个股票代码/名称预览:")
    for i, stock in enumerate(unique_stocks[:20], 1):
        print(f"{i}. {stock}")
    if len(unique_stocks) > 20:
        print(f"...(共 {len(unique_stocks)} 条，其余省略)")

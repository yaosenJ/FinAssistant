# !/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
from urllib.parse import quote_plus
import aiomysql
import pandas as pd
from datetime import datetime
import bisect
from typing import Dict, Optional, Tuple


async def create_async_pool(db_config: Dict) -> aiomysql.Pool:
    """创建异步MySQL连接池"""
    return await aiomysql.create_pool(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        db=db_config['database'],
        charset='utf8mb4'
    )


async def load_trade_dates() -> list:
    """异步加载交易日历"""
    try:
        df_trade = pd.read_csv('../data/time.csv', dtype={'cal_date': str})
        df_trade['cal_date'] = pd.to_datetime(df_trade['cal_date'], format='%Y%m%d').dt.date
        return sorted(df_trade['cal_date'].tolist())
    except Exception as e:
        print(f"加载交易日文件失败: {e}")
        return []


async def get_date_range(days_ago: Optional[int], trade_dates: list) -> Tuple[Optional[str], Optional[str]]:
    """计算日期范围"""
    if days_ago is None:
        return None, None

    today = datetime.now().date()
    index = bisect.bisect_right(trade_dates, today) - 1
    if index < 0:
        raise ValueError("当前日期早于所有交易日")

    end_date = trade_dates[index]
    start_index = max(0, index - (days_ago - 1))
    start_date = trade_dates[start_index]

    if start_index == 0:
        print(f"注意：请求的{days_ago}个交易日超出范围，将返回从{start_date}到{end_date}的数据。")

    return start_date, end_date


async def fetch_news_data(
        pool: aiomysql.Pool,
        table_name: str,
        field_name: str,
        field_value: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
) -> pd.DataFrame:
    """异步执行SQL查询并返回DataFrame"""
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 构建SQL查询
                sql = f"""
                SELECT trade_date, title, content
                FROM {table_name}
                WHERE {field_name} = %s
                """
                params = [field_value]

                if start_date and end_date:
                    sql += " AND trade_date >= %s AND trade_date <= %s"
                    params.extend([start_date, end_date])

                sql += " ORDER BY trade_date DESC"

                await cursor.execute(sql, params)
                result = await cursor.fetchall()
                return pd.DataFrame(result)
    except Exception as e:
        print(f"数据库查询出错: {str(e)}")
        return pd.DataFrame()


async def get_company_news(
        db_config: Dict,
        search_type: str,
        search_value: str,
        table_name: str = 'new_processed_daily_news',
        days_ago: Optional[int] = None
) -> pd.DataFrame:
    """通用异步获取新闻数据"""
    field_mapping = {
        'stock': 'stock_name',
        'industry': 'industry_name',
        'concept': 'concept_name'
    }

    if search_type not in field_mapping:
        raise ValueError(f"不支持的搜索类型: {search_type}")

    try:
        trade_dates = await load_trade_dates()
        start_date, end_date = await get_date_range(days_ago, trade_dates)

        pool = await create_async_pool(db_config)
        return await fetch_news_data(
            pool, table_name, field_mapping[search_type], search_value, start_date, end_date
        )
    except Exception as e:
        print(f"获取{search_type}新闻出错: {str(e)}")
        return pd.DataFrame()


async def main():
    # 数据库配置
    db_config = {
        'host': '192.168.1.101',
        'port': 13306,
        'user': 'news_user',
        'password': 'km101',
        'database': 'stock_news'
    }

    # 并行查询示例
    concept_task = get_company_news(db_config, 'concept', '光伏', days_ago=10)
    stock_task = get_company_news(db_config, 'stock', '机器人', days_ago=10)

    # 使用asyncio.gather并行执行多个查询
    concept_news, stock_news = await asyncio.gather(concept_task, stock_task)

    # 检查并打印结果
    if not concept_news.empty:
        print(f"找到 {len(concept_news)} 条关于光伏的新闻:")
        print(concept_news.head())
    else:
        print("没有找到关于光伏的新闻")

    if not stock_news.empty:
        print(f"\n找到 {len(stock_news)} 条关于机器人的新闻:")
        print(stock_news.head())
    else:
        print("\n没有找到关于机器人的新闻")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
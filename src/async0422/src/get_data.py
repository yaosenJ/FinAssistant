#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Dict
from database import get_company_news  # 假设我们已经实现了异步版本的数据库查询

# 数据库配置（全局常量，避免重复定义）
DB_CONFIG = {
    'host': '192.168.1.101',
    'port': 13306,
    'user': 'news_user',
    'password': 'km101',
    'database': 'stock_news'
}


async def get_company_report_info_from_stock(stock: str) -> Dict:
    """异步查询股票新闻信息"""
    try:
        result = await get_company_news(
            db_config=DB_CONFIG,
            search_type='stock',
            search_value=stock,
            days_ago=10
        )
        # return {"status": "success", "data": result}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_company_report_info_from_industry(industry: str) -> Dict:
    """异步查询行业新闻信息"""
    try:
        result = await get_company_news(
            db_config=DB_CONFIG,
            search_type='industry',
            search_value=industry,
            days_ago=30
        )
        # return {"status": "success", "data": result}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_company_report_info_from_concept(concept: str) -> Dict:
    """异步查询概念新闻信息"""
    try:
        result = await get_company_news(
            db_config=DB_CONFIG,
            search_type='concept',
            search_value=concept,
            days_ago=30
        )
        # return {"status": "success", "data": result}
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def main():
    """测试示例"""
    # 并行查询示例
    stock_task = get_company_report_info_from_stock("机器人")
    concept_task = get_company_report_info_from_concept("光伏")

    stock_result, concept_result = await asyncio.gather(stock_task, concept_task)

    print("股票查询结果:", stock_result)
    print("概念查询结果:", concept_result)


if __name__ == "__main__":
    asyncio.run(main())

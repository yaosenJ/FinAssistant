# !/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio

import aiofiles

from rag_consine_date import AsyncNewsSearchSystem
from get_data import (
    get_company_report_info_from_stock,
    get_company_report_info_from_industry,
    get_company_report_info_from_concept,
)
from summary_generation import AsyncQwenClient


async def get_news_content_from_milvus(query: str, days: int = 10) -> str:
    """带错误处理的Milvus查询"""
    system = AsyncNewsSearchSystem()
    try:
        await system.initialize()  # 显式初始化
        raw_results = await system.search_news(query, days)
        if not raw_results:
            return "未找到相关新闻"

        # 对结果进行重排
        ranked_results = await system.rerank_contexts(
            query=query,
            contexts=raw_results,  # 确保这是文档列表
            top_n=10
        )
        return "\n".join(ranked_results[:10])  # 取前10条并拼接
    except Exception as e:
        print(f"查询异常: {str(e)}")
        return f"查询失败: {str(e)}"


async def get_news_content_from_mysql(content: str, type: str) -> str:
    """从mysql中异步获取新闻内容"""
    try:
        if type == "stock":
            result = await get_company_report_info_from_stock(content)  # 直接 await 异步函数
        elif type == "industry":
            result = await get_company_report_info_from_industry(content)
        elif type == "concept":
            result = await get_company_report_info_from_concept(content)
        else:
            result = ""
        return str(result)
    except Exception as e:
        print(f"MySQL查询失败: {str(e)}")
        return ""


async def get_content(query: str, content: str, type: str) -> str:
    """并行获取新闻和报告内容"""
    news_result_milvus = await get_news_content_from_milvus(query)

    news_result_mysql = await get_news_content_from_mysql(content, type)
    # news_result_milvus, news_result_mysql =  asyncio.gather(news_task_milvus, news_task_mysql)
    return news_result_milvus + news_result_mysql

import asyncio
import yaml

def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


config = load_config('./config.yaml')

async def main(query: str, content: str, type: str) -> str:
    """异步主函数"""
    text = await get_content(query, content, type)
    print(text)
    # summary_content = await asyncio.to_thread(AsyncQwenClient().generate_summary, query, text)
    summary_content = await AsyncQwenClient(config).generate_summary(query,text)
    return summary_content


if __name__ == "__main__":
    # query = '新能源汽车的发展前景如何？'
    # content = "新能源汽车"
    # type = "concept"
    query = '房地产行业目前面临哪些风险？'
    content = "房地产"
    type = "industry"


    # 运行异步主函数
    result = asyncio.run(main(query, content, type))
    print(result)
#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import aiofiles
import httpx
from typing import List, Dict, Optional
import numpy as np
from pymilvus import connections, Collection
import yaml
from contextlib import asynccontextmanager


# ================= 异步配置加载 =================
async def load_config(config_path: str) -> dict:
    async with aiofiles.open(config_path, mode='r') as f:
        content = await f.read()
        return yaml.safe_load(content)


# ================= 异步服务初始化 =================
class AsyncQwenClient:
    def __init__(self, config: dict):
        self.api_key = config['qwen']['api_key']
        self.base_url = config['qwen']['base_url']
        self.embedding_model = config['qwen']['embedding_model']
        self.chat_model = config['qwen']['chat_model']
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30)

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """异步获取文本向量（带指数退避重试）"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.embedding_model,
            "input": text,
            "text_type": "document"
        }

        for attempt in range(3):
            try:
                response = await self.client.post(
                    "/embeddings",
                    json=payload,
                    headers=headers
                )
                if response.status_code == 200:
                    return response.json()['data'][0]['embedding']
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(2 ** attempt)
        return None

    async def generate_summary(self, query: str, contexts: str) -> str:
        """异步生成智能摘要"""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        system_prompt = """ Role: 
        - 证券领域信息整合专家

        ## objective: 
        - 根据{{query}}，在{{contexts}}中寻找相关信息，并分析总结，形成简报

        ## Workflows 
        - 1: 判断{{contexts}}中，是否存在与{{query}}相关的信息
        - 2: 如果没有相关信息，输出“无相关信息”
        - 3: 如果包含相关信息，对相关信息进行提取、整理，并根据{{query}}进行分析和总结
        - 4: 将上一步的内容整理成简报

        ## Rules
        1. 基本原则：
           - 准确性: 分析所使用的信息必须包含在{{contexts}}中
           - 时效性: 优先处理最新市场动态信息
           - 完整性: 确保关键信息不遗漏（例如：数值、时间等）

        2. 限制条件：
           - 直接回答问题核心，不要复述问题
           - 简报中避免"根据资料"等前缀
           - 分析时不考虑trade_date的信息

        ## Initialization
        作为证券信息整合专家，你必须遵守上述Rules，按照Workflows执行任务。"""
        print(contexts)
        try:
            response = await self.client.post(
                "/chat/completions",
                json={
                    "model": self.chat_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"问题：{query}\n相关文本：{' '.join(contexts)}"}
                    ],
                    "temperature": 0.5,
                    "top_p": 0.9
                },
                headers=headers
            )
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"摘要生成失败: {str(e)}")
            return "摘要生成失败"


# ================= 异步Milvus连接管理 =================
@asynccontextmanager
async def async_milvus_connection(config: dict):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: connections.connect(
            alias='default',
            host=config['milvus']['host'],
            port=config['milvus']['port']
        )
    )
    try:
        yield
    finally:
        await loop.run_in_executor(None, connections.disconnect, 'default')


class AsyncMilvusSearcher:
    def __init__(self, config: dict):
        self.collection_name = config['milvus']['collection_name']
        self.search_params = config['milvus']['search_params']
        self.collection = None

    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        self.collection = Collection(self.collection_name)
        await loop.run_in_executor(None, self.collection.load)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass  # 连接由上下文管理器统一管理

    async def search(self, embedding: List[float]) -> List[Dict]:
        """异步向量搜索"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.collection.search(
                data=[embedding],
                anns_field="embedding",
                param={
                    "metric_type": self.search_params['metric_type'],
                    "params": {"nprobe": self.search_params['nprobe']}
                },
                limit=self.search_params['limit'],
                output_fields=["content", "title"]
            )
        )


# ================= 异步主流程 =================
async def process_single_query(query: str, qwen_client: AsyncQwenClient, searcher: AsyncMilvusSearcher):
    """处理单个查询的完整流程"""
    print(f"\n处理问题: {query}")

    # 获取向量
    start_time = asyncio.get_event_loop().time()
    embedding = await qwen_client.get_embedding(query)
    if not embedding:
        return

    # Milvus搜索
    results = await searcher.search(embedding)
    hits = results[0]

    if not hits:
        print("未找到相关结果")
        return

    # 处理结果
    contexts = [{
        "title": hit.entity.get("title"),
        "content": hit.entity.get("content")
    } for hit in hits]

    # 生成摘要
    summary = await qwen_client.generate_summary(query, [ctx["content"] for ctx in contexts])

    # 显示结果
    process_time = asyncio.get_event_loop().time() - start_time
    print(f"\n摘要: {summary}")
    print(f"处理耗时: {process_time:.2f}s")
    return summary


async def main_async():
    config = await load_config('config.yaml')
    qwen_client = AsyncQwenClient(config)

    async with async_milvus_connection(config):
        async with AsyncMilvusSearcher(config) as searcher:
            # 异步读取测试问题
            async with aiofiles.open(config['data']['test_path'], 'r', encoding='gbk') as f:
                queries = [line.strip() async for line in f if line.strip()]

            # 并行处理查询（限制最大并发数）
            semaphore = asyncio.Semaphore(3)  # 控制并发请求数

            async def limited_task(query):
                async with semaphore:
                    return await process_single_query(query, qwen_client, searcher)

            tasks = [limited_task(query) for query in queries]
            await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main_async())
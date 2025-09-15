#!/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Set, Optional
import hashlib
import numpy as np
import pandas as pd
import aiomysql
import yaml
from fuzzywuzzy import fuzz
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility


# ================= 异步配置加载 =================
async def load_config(config_path: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: yaml.safe_load(open(config_path)))


config = asyncio.run(load_config('config.yaml'))

# ================= 从YAML读取配置 =================
# Milvus配置
MILVUS_HOST = config['milvus']['host']
MILVUS_PORT = config['milvus']['port']  # 注意这里会自动转为int类型
COLLECTION_NAME = config['milvus']['collection_name']


# ================= 异步交易日历处理 =================
class AsyncTradeCalendar:
    def __init__(self, csv_path: str = '../data/time.csv') -> None:
        self.trade_dates = []
        self.csv_path = csv_path
        self._loaded = False  # 添加加载状态标志

    async def load_trade_dates(self) -> None:
        """异步加载交易日数据（带重试机制）"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                df = await loop.run_in_executor(
                    None,
                    lambda: pd.read_csv(
                        self.csv_path,
                        dtype={'cal_date': str},
                        usecols=['cal_date'],
                        encoding='utf-8-sig'  # 处理BOM头
                    )
                )

                # 增强数据校验
                if df.empty or 'cal_date' not in df.columns:
                    raise ValueError("无效的交易日历文件格式")

                # 使用列表推导式优化日期解析
                self.trade_dates = sorted([
                    datetime.strptime(d, "%Y%m%d").date()
                    for d in df['cal_date']
                    if str(d).strip()  # 过滤空值
                ])

                if not self.trade_dates:
                    raise ValueError("未解析出有效交易日")

                self._loaded = True
                print(f"成功加载 {len(self.trade_dates)} 个交易日（第{attempt + 1}次尝试）")
                return

            except Exception as e:
                print(f"交易日历加载失败（尝试 {attempt + 1}/{max_retries}）: {str(e)}")
                if attempt == max_retries - 1:
                    # 最后一次尝试仍失败，设置默认日期
                    self.trade_dates = [date.today()]
                    self._loaded = False
                    print("警告：使用当天作为默认交易日")
                await asyncio.sleep(1)  # 重试间隔

    async def get_last_trade_date(self, target_date: date = None) -> date:
        """获取最近交易日（带安全校验）"""
        if not self._loaded:
            await self.load_trade_dates()

        target = target_date or date.today()
        return next(
            (td for td in reversed(self.trade_dates) if td <= target),
            self.trade_dates[-1] if self.trade_dates else date.today()
        )

    async def get_n_days_back(self, end_date: date, n_days: int) -> date:
        """计算起始日期（带边界检查）"""
        if not self._loaded:
            await self.load_trade_dates()

        try:
            idx = self.trade_dates.index(end_date)
            return self.trade_dates[max(0, idx - n_days + 1)]
        except ValueError:
            print(f"警告：{end_date} 不在交易日历中，返回最早可用日期")
            return self.trade_dates[0] if self.trade_dates else end_date - timedelta(days=n_days)

# ================= 异步全局工具 =================
async def get_dynamic_dates(n_days: int, calendar: AsyncTradeCalendar) -> tuple[str, str]:
    """异步动态计算日期范围"""
    try:
        end_date = await calendar.get_last_trade_date()
        start_date = await calendar.get_n_days_back(end_date, n_days)
    except ValueError as e:
        print(f"日期计算失败: {str(e)}, 使用默认日期范围")
        default_end = datetime.now().date()
        default_start = default_end - timedelta(days=30)
        return (
            default_start.strftime("%Y-%m-%d 00:00:00"),
            default_end.strftime("%Y-%m-%d 23:59:59")
        )

    return (
        start_date.strftime("%Y-%m-%d 00:00:00"),
        end_date.strftime("%Y-%m-%d 23:59:59")
    )


# ================= 异步Milvus操作 =================
class AsyncMilvusVectorDB:
    def __init__(self):
        self.collection = None

    async def connect(self):
        """异步连接Milvus"""
        loop = asyncio.get_event_loop()
        # 正确传递参数的方式
        await loop.run_in_executor(
            None,
            lambda: connections.connect(
                alias='default',
                host=MILVUS_HOST,
                port=MILVUS_PORT
            )
        )
        self.collection = Collection(COLLECTION_NAME)
        await loop.run_in_executor(None, self.collection.load)

    async def retrieval(self,
                        query_embedding: List[float],
                        time_filter: str,
                        top_k: int = 100) -> List[Dict]:
        """异步向量搜索"""
        loop = asyncio.get_event_loop()

        query_array = np.array(query_embedding)
        normalized_query = (query_array / np.linalg.norm(query_array)).tolist()

        results = await loop.run_in_executor(
            None,
            lambda: self.collection.search(
                data=[normalized_query],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 64}},
                expr=time_filter,
                limit=top_k,
                output_fields=["title", "content", "trade_date"]
            )
        )

        return [{
            "title": hit.entity.get("title"),
            "content": hit.entity.get("content"),
            "trade_date": hit.entity.get("trade_date"),
            "score": hit.distance
        } for hits in results for hit in hits]


# ================= 异步文本向量生成 =================
class AsyncEmbeddingGenerator:
    def __init__(self) -> None:
        import dashscope
        dashscope.api_key = config['qwen']['api_key']
        self.client = dashscope.TextEmbedding

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """异步获取文本向量"""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.client.call(
                    model=config['qwen']['embedding_model'],
                    input=text,
                    text_type="document"
                )
            )
            return response.output['embeddings'][0]['embedding'] if response.status_code == 200 else None
        except Exception as e:
            print(f"生成向量失败: {str(e)}")
            return None


# ================= 异步新闻搜索系统 =================
class AsyncNewsSearchSystem:
    def __init__(self, search_days: int = 10) -> None:
        self.embedding = AsyncEmbeddingGenerator()
        self.vector_db = AsyncMilvusVectorDB()
        self.search_days = search_days
        self.calendar = AsyncTradeCalendar()

    async def initialize(self):
        """异步初始化"""
        await self.calendar.load_trade_dates()
        await self.vector_db.connect()

    async def search_news(self, query: str, days: int = None) -> List[Dict]:
        """异步新闻搜索"""
        _, target_end = await get_dynamic_dates(self.search_days, self.calendar)
        end_dt = datetime.strptime(target_end, "%Y-%m-%d %H:%M:%S")

        if days is not None:
            start_date = await self.calendar.get_n_days_back(end_dt.date(), days)
            start_dt = datetime.combine(start_date, datetime.min.time())
            start_ts = int(start_dt.timestamp() * 1000)
        else:
            start_ts = int(end_dt.timestamp() * 1000 - 365 * 24 * 3600 * 1000)

        end_ts = int(end_dt.timestamp() * 1000)
        time_filter = f"trade_date >= {start_ts} && trade_date <= {end_ts}"

        query_embedding = await self.embedding.get_embedding(query)
        if not query_embedding:
            return []

        semantic_results = await self.vector_db.retrieval(query_embedding, time_filter)
        filtered_results = [res for res in semantic_results if res['score'] >= 0.4]
        return sorted(filtered_results, key=lambda x: x['score'], reverse=True)[:20]


# ================= 使用示例 =================
async def main():
    # 初始化系统
    search_system = AsyncNewsSearchSystem()
    await search_system.initialize()

    # 执行搜索
    results = await search_system.search_news("新能源汽车行业未来5年的发展前景如何？", days=10)
    print(f"找到 {len(results)} 条相关新闻：")
    for idx, res in enumerate(results[:5], 1):
        print(f"{idx}. {res['title']} (得分: {res['score']:.2f})")


if __name__ == "__main__":
    asyncio.run(main())

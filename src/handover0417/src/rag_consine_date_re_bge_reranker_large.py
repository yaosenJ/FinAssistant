#!/usr/bin/python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from typing import List, Dict, Set
import numpy as np
import pandas as pd
import yaml
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
import requests
# ================= 配置加载 =================
def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


config = load_config('../config/config.yaml')

# ================= 从YAML读取配置 =================
# Milvus配置
MILVUS_HOST = config['milvus']['host']
MILVUS_PORT = config['milvus']['port']  # 注意这里会自动转为int类型
COLLECTION_NAME = config['milvus']['collection_name']

# ================= 交易日历处理模块 =================
class TradeCalendar:
    def __init__(self, csv_path: str = '../data/time.csv') -> None:
        self.trade_dates = self._load_trade_dates(csv_path)
        self.trade_dates.sort()

    def _load_trade_dates(self, path: str) -> List[date]:
        """加载并解析交易日数据"""
        df = pd.read_csv(path, dtype={'cal_date': str})
        dates = []
        for d in df['cal_date']:
            try:
                dt = datetime.strptime(d, "%Y%m%d").date()
                dates.append(dt)
            except ValueError:
                continue
        return dates

    def get_last_trade_date(self, target_date: date = None) -> date:
        """获取指定日期前最近的交易日"""
        target = target_date or date.today()
        for td in reversed(self.trade_dates):
            if td <= target:
                return td
        return self.trade_dates[-1]  # 保底返回最后一个

    def get_n_days_back(self, end_date: date, n_days: int) -> date:
        """从end_date往前找n个交易日"""
        try:
            idx = self.trade_dates.index(end_date)
            start_idx = max(0, idx - n_days + 1)
            return self.trade_dates[start_idx]
        except ValueError:
            return self.trade_dates[0]


# ================= 全局工具函数 =================
TRADE_CALENDAR = TradeCalendar()


def get_dynamic_dates(n_days: int) -> tuple[str, str]:
    """动态计算日期范围"""
    end_date = TRADE_CALENDAR.get_last_trade_date()
    start_date = TRADE_CALENDAR.get_n_days_back(end_date, n_days)
    return (
        start_date.strftime("%Y-%m-%d 00:00:00"),
        end_date.strftime("%Y-%m-%d 23:59:59")
    )


# ================= Milvus向量数据库操作类 =================
class MilvusVectorDB:
    def __init__(self) -> None:
        self.collection = None
        self._connect_to_milvus()
        self._setup_collection()

    def _connect_to_milvus(self) -> None:
        """连接Milvus数据库"""
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, alias='default')

    def _setup_collection(self) -> None:
        """创建或连接集合"""
        self.collection = Collection(COLLECTION_NAME)
        self.collection.load()

    def retrieval(self,
                  query_embedding: List[float],
                  time_filter: str,
                  top_k: int = 100) -> List[Dict]:
        """带时间过滤的向量搜索"""
        query_array = np.array(query_embedding)
        normalized_query = (query_array / np.linalg.norm(query_array)).tolist()

        results = self.collection.search(
            data=[normalized_query],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 64}},
            expr=time_filter,
            limit=top_k,
            output_fields=["title", "content", "trade_date"]
        )

        return [{
            "title": hit.entity.get("title"),
            "content": hit.entity.get("content"),
            "trade_date": hit.entity.get("trade_date"),
            "score": hit.distance
        } for hits in results for hit in hits]


# ================= 文本向量生成器 =================
class EmbeddingGenerator:
    def __init__(self) -> None:
        import dashscope
        dashscope.api_key = config['qwen']['api_key']
        self.client = dashscope.TextEmbedding

    def get_embedding(self, text: str) -> List[float]:
        try:
            response = self.client.call(
                model=config['qwen']['embedding_model'],
                input=text,
                text_type="document"
            )
            return response.output['embeddings'][0]['embedding'] if response.status_code == 200 else None
        except Exception as e:
            print(f"生成向量失败: {str(e)}")
            return None


# ================= 新闻搜索系统主类 =================
class NewsSearchSystem:
    def __init__(self, search_days: int = 10) -> None:
        self.embedding = EmbeddingGenerator()
        self.vector_db = MilvusVectorDB()
        self.search_days = search_days

    def search_news(self, query: str, days: int = None) -> List[Dict]:
        _, target_end = get_dynamic_dates(self.search_days)
        end_dt = datetime.strptime(target_end, "%Y-%m-%d %H:%M:%S")

        if days is not None:
            start_date = TRADE_CALENDAR.get_n_days_back(end_dt.date(), days)
            # 修复：将date转换为datetime
            start_dt = datetime.combine(start_date, datetime.min.time())
            start_ts = int(start_dt.timestamp() * 1000)
        else:
            start_ts = int(end_dt.timestamp() * 1000 - 365 * 24 * 3600 * 1000)

        end_ts = int(end_dt.timestamp() * 1000)
        time_filter = f"trade_date >= {start_ts} && trade_date <= {end_ts}"

        query_embedding = self.embedding.get_embedding(query)
        if not query_embedding:
            return []

        semantic_results = self.vector_db.retrieval(query_embedding, time_filter)
        # Filter results with score >= 0.4
        filtered_results = [res for res in semantic_results if res['score'] >= 0.4]
        # Sort by score in descending order and take top 30
        text = sorted(filtered_results, key=lambda x: x['score'], reverse=True)[:20]
        text_contexts = [f"标题：{c['title']}\n内容：{c['content']}" for c in text]
        return text_contexts

    def rerank_contexts(self, query: str, contexts: List[str], top_n: int = 10) -> List[str]:

        """使用本地部署的BGE reranker进行重排"""

        api_url = "http://192.168.1.119:8011/rerank"
        headers = {'Content-Type': 'application/json'}

        try:
            payload = {
                "query": query,
                "documents": contexts
            }

            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=10  # 设置超时时间
            )

            if response.status_code == 200:
                results = response.json().get('results', [])
                # 提取前top_n个文档内容
                return [item['document'] for item in results[:top_n]]
            return contexts[:top_n]

        except requests.exceptions.RequestException as e:
            print(f"重排请求失败: {str(e)}")
            return contexts[:top_n]
        except Exception as e:
            print(f"重排处理异常: {str(e)}")
            return contexts[:top_n]

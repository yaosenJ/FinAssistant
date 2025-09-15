#!/usr/bin/python3
# -*- coding: utf-8 -*-

# ================= 标准库导入 =================
from datetime import datetime, timedelta, date
from typing import List, Dict, Set
import hashlib

# ================= 第三方库导入 =================
import numpy as np
import pandas as pd
import pymysql
import yaml
from fuzzywuzzy import fuzz
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

# ================= 配置加载 =================
def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


config = load_config('config.yaml')

# ================= 从YAML读取配置 =================
# Milvus配置
MILVUS_HOST = config['milvus']['host']
MILVUS_PORT = config['milvus']['port']  # 注意这里会自动转为int类型
COLLECTION_NAME = config['milvus']['collection_name']
EMBEDDING_DIM = config['milvus']['embedding_dim']

# MySQL配置
MYSQL_HOST = config['mysql']['host']
MYSQL_PORT = config['mysql']['port']
MYSQL_USER = config['mysql']['user']
MYSQL_PASSWORD = config['mysql']['password']
MYSQL_DB = config['mysql']['database']

# 数据处理配置
BATCH_SIZE = config['data']['batch_size']


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
        print("成功连接到Milvus数据库")

    def _setup_collection(self) -> None:
        """创建或连接集合"""
        if utility.has_collection(COLLECTION_NAME):
            self.collection = Collection(COLLECTION_NAME)
            print(f"连接到现有集合: {COLLECTION_NAME}")
        else:
            fields = [
                FieldSchema(name="hash_id", dtype=DataType.VARCHAR, is_primary=True, max_length=32),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=400),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=3000),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
                FieldSchema(name="trade_date", dtype=DataType.INT64)
            ]
            schema = CollectionSchema(fields, description="最终版新闻数据库")
            self.collection = Collection(COLLECTION_NAME, schema)

            self.collection.create_index("embedding", {
                "index_type": "IVF_SQ8",
                "metric_type": "COSINE",
                "params": {"nlist": 2048}
            })
            print(f"创建新集合: {COLLECTION_NAME}")
        self.collection.load()

    def check_existing_hashes(self, hash_list: List[str]) -> Set[str]:
        """批量检查哈希是否存在"""
        existing = set()
        for i in range(0, len(hash_list), BATCH_SIZE):
            batch = hash_list[i:i + BATCH_SIZE]
            expr = f"hash_id in {str(batch)}"
            res = self.collection.query(expr, output_fields=["hash_id"])
            existing.update(item["hash_id"] for item in res)
        return existing

    def insert_batch(self,
                     hashes: List[str],
                     titles: List[str],
                     contents: List[str],
                     embeddings: List[List[float]],
                     timestamps: List[int]) -> None:
        """批量插入数据"""
        embeddings_array = np.array(embeddings)
        norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        normalized = embeddings_array / norms

        data = [hashes, titles, contents, normalized.tolist(), timestamps]
        try:
            self.collection.insert(data)
            print(f"成功插入{len(hashes)}条数据")
        except Exception as e:
            print(f"插入失败: {str(e)}")

    def search_news(self,
                    query_embedding: List[float],
                    time_filter: str,
                    top_k: int = 1000) -> List[Dict]:
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

    def close(self) -> None:
        connections.disconnect('default')
        print("Milvus连接已关闭")


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
        self.mysql_conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            charset='utf8mb4'
        )
        self.processed_hashes = set()
        self.search_days = search_days

    def _generate_hash(self, title: str, dt: datetime) -> str:
        """生成数据唯一标识"""
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return hashlib.md5(f"{title}||{time_str}".encode()).hexdigest()

    def load_data(self, n_days: int = None) -> None:
        """动态加载数据"""
        n_days = n_days or self.search_days
        target_start, target_end = get_dynamic_dates(n_days)

        cursor = self.mysql_conn.cursor()
        try:
            cursor.execute("""
                SELECT title, content, trade_date 
                FROM daily_news 
                WHERE trade_date BETWEEN %s AND %s
            """, (target_start, target_end))

            candidate_data = []
            hash_list = []
            for title, content, dt in cursor:
                try:
                    dt_obj = dt if isinstance(dt, datetime) else datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S")
                    data_hash = self._generate_hash(title, dt_obj)
                    hash_list.append(data_hash)
                    candidate_data.append((title, content, dt_obj, data_hash))
                except Exception as e:
                    print(f"数据预处理失败: {str(e)}")

            existing_hashes = self.vector_db.check_existing_hashes(hash_list)
            new_data = [item for item in candidate_data if item[3] not in existing_hashes]
            print(f"发现{len(new_data)}条新数据需要处理")

            for i in range(0, len(new_data), BATCH_SIZE):
                batch = new_data[i:i + BATCH_SIZE]
                self._process_batch(batch)

        finally:
            cursor.close()
            self.mysql_conn.close()

    def _process_batch(self, batch: list) -> None:
        """处理单批次数据"""
        hashes, titles, contents, embeddings, timestamps = [], [], [], [], []

        for title, content, dt, data_hash in batch:
            embedding = self.embedding.get_embedding(f"{title}: {content[:200]}")
            if embedding:
                hashes.append(data_hash)
                titles.append(title)
                contents.append(content)
                embeddings.append(embedding)
                timestamps.append(int(dt.timestamp() * 1000))

        if embeddings:
            self.vector_db.insert_batch(hashes, titles, contents, embeddings, timestamps)
            self.processed_hashes.update(hashes)

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

        semantic_results = self.vector_db.search_news(query_embedding, time_filter)
        # Filter results with score >= 0.4
        filtered_results = [res for res in semantic_results if res['score'] >= 0.4]
        # Sort by score in descending order and take top 10
        return sorted(filtered_results, key=lambda x: x['score'], reverse=True)[:20]

    def print_results(self, results: List[Dict]) -> None:
        """可视化打印结果"""
        print(f"\n{'=' * 50}")
        print(f"找到{len(results)}条结果：")
        for i, item in enumerate(results, 1):
            dt = datetime.fromtimestamp(item['trade_date'] / 1000)
            print(f"\n#{i} [{dt.strftime('%Y-%m-%d %H:%M')}] 相似度: {item['score']:.4f}")
            print(f"标题: {item['title']}")
            print(f"内容摘要: {item['content'][:150]}...")

    def get_results(self, results: List[Dict]) -> List[str]:
        """获取结果文本"""
        return [item['title'] + item['content'] for item in results]

    def close(self) -> None:
        self.vector_db.close()


# ================= 主程序入口 =================
if __name__ == "__main__":
    system = NewsSearchSystem()
    try:
        print("正在初始化数据...")
        system.load_data()

        while True:
            query = input("\n请输入问题(输入 q 退出): ").strip()
            if query.lower() == 'q':
                break

            try:
                days = int(input("请输入时间范围天数(留空则搜索全部): ") or 0)
                days = None if days <= 0 else days
            except ValueError:
                days = None
                print("将搜索全部时间范围")

            results = system.search_news(query, days)
            system.print_results(results)

    finally:
        system.close()
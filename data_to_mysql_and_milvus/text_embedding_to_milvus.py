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

# ================= 配置信息 =================
MILVUS_HOST = '192.168.1.102'
MILVUS_PORT = '19530'
MYSQL_HOST = '192.168.1.101'
MYSQL_PORT = 13306
MYSQL_USER = 'news_user'
MYSQL_PASSWORD = 'km101'
MYSQL_DB = 'stock_news'
COLLECTION_NAME = "company_news_final"
EMBEDDING_DIM = 1536
BATCH_SIZE = 100

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

    def close(self) -> None:
        connections.disconnect('default')
        print("Milvus连接已关闭")


# ================= 文本向量生成器 =================
class EmbeddingGenerator:
    def __init__(self) -> None:
        import dashscope
        dashscope.api_key = "sk-48d14c208910"
        self.client = dashscope.TextEmbedding

    def get_embedding(self, text: str) -> List[float]:
        try:
            response = self.client.call(
                model='text-embedding-v1',
                input=text,
                text_type="document"
            )
            return response.output['embeddings'][0]['embedding'] if response.status_code == 200 else None
        except Exception as e:
            print(f"生成向量失败: {str(e)}")
            return None


# ================= 新闻系统主类 =================
class NewsSystem:
    def __init__(self) -> None:
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
    def _generate_hash(self, title: str, dt: datetime) -> str:
        """生成数据唯一标识"""
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return hashlib.md5(f"{title}||{time_str}".encode()).hexdigest()

    def load_data(self,  start_date: str = None,
                 end_date: str = None) -> None:

        target_start = start_date
        target_end = end_date
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

    def close(self) -> None:
        self.vector_db.close()


# ================= 主程序入口 =================
if __name__ == "__main__":
    system = NewsSystem()
    print("正在初始化数据...")
    system.load_data(
        start_date="2025-04-1 00:00:00",
        end_date="2028-04-11 23:59:59"
    )
    system.close()
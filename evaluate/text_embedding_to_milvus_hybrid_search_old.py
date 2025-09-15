#!/usr/bin/python3
# -*- coding: utf-8 -*-

from datetime import datetime
import hashlib
from typing import List, Set, Dict, Optional
import dashscope
import pymysql
from pymilvus import MilvusClient, DataType, Function, FunctionType
import time

# ================= 配置信息 =================
MILVUS_URL = '192.168.1.227:19530'
MYSQL_HOST = '192.168.1.101'
MYSQL_PORT = 13306
MYSQL_USER = 'news_user'
MYSQL_PASSWORD = 'km101'
MYSQL_DB = 'stock_news'
COLLECTION_NAME = "company_news_hybrid"
DENSE_DIM = 1024  # text-embedding-v3维度
MAX_TITLE_LEN = 400
MAX_CONTENT_LEN = 3000
DASHSCOPE_API_KEY = "sk-48d14c2089"
EMBED_BATCH_SIZE = 500
MAX_RETRIES = 3  # API调用重试次数
RETRY_DELAY = 5  # 重试延迟秒数
INSERT_BATCH_SIZE = 200  # 根据数据特征调整该值

# ================= 文本向量生成器 =================
class EmbeddingGenerator:
    def __init__(self):
        dashscope.api_key = DASHSCOPE_API_KEY
        self.client = dashscope.TextEmbedding

    def embed_documents(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量生成文档嵌入（带重试机制）"""
        embeddings = []
        for text in texts:
            for attempt in range(MAX_RETRIES):
                try:
                    response = self.client.call(
                        model='text-embedding-v3',
                        input=text,
                        text_type="document"
                    )
                    if response.status_code == 200:
                        embedding = response.output['embeddings'][0]['embedding']
                        if len(embedding) == DENSE_DIM:
                            embeddings.append(embedding)
                        else:
                            print(f"嵌入维度异常：{len(embedding)}维")
                            embeddings.append(None)
                        break
                    else:
                        print(f"API错误（尝试{attempt+1}/{MAX_RETRIES}）: {response.message}")
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY)
                except Exception as e:
                    print(f"请求异常（尝试{attempt+1}/{MAX_RETRIES}）: {str(e)}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
            else:
                embeddings.append(None)
                print(f"文本嵌入失败：{text[:50]}...")
        return embeddings

class NewsSystem:
    def __init__(self):
        # 初始化MySQL连接
        self.mysql_conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            charset='utf8mb4'
        )

        # 初始化Embedding模型
        self.embedding_generator = EmbeddingGenerator()

        # 初始化Milvus客户端
        self.client = MilvusClient(
            uri=f"http://{MILVUS_URL}",
            token="root:Milvus",  # 根据实际修改
            db_name="default"
        )

        # 创建集合
        self._create_collection()

    def _generate_hash(self, title: str, dt: datetime) -> str:
        """生成数据唯一标识"""
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return hashlib.md5(f"{title}||{time_str}".encode()).hexdigest()

    def _create_collection(self):

        if COLLECTION_NAME in self.client.list_collections():
            print(f"集合 {COLLECTION_NAME} 已存在")
            self.client.load_collection(COLLECTION_NAME)
            return

        # 创建Schema
        schema = self.client.create_schema(
            enable_dynamic_field=True
        )

        # 添加字段
        schema.add_field(field_name="hash_id", datatype=DataType.VARCHAR,
                         is_primary=True, max_length=32)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR,
                         max_length=MAX_TITLE_LEN)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR,
                         max_length=MAX_CONTENT_LEN,
                         enable_analyzer=True,
                         analyzer_params={"type": "chinese"}, enable_match=True)
        schema.add_field(field_name="dense", datatype=DataType.FLOAT_VECTOR,
                         dim=DENSE_DIM)
        schema.add_field(field_name="sparse_bm25", datatype=DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field(field_name="trade_date", datatype=DataType.INT64)

        bm25_function = Function(
            name="bm25",
            function_type=FunctionType.BM25,
            input_field_names=["content"],
            output_field_names="sparse_bm25",
        )
        schema.add_function(bm25_function)

        # 索引配置
        index_params = self.client.prepare_index_params()

        index_params.add_index(
            field_name="dense",
            index_name="dense_index",
            index_type="IVF_SQ8",
            metric_type="COSINE",
            params={"nlist": 2048}
        )

        index_params.add_index(
            field_name="sparse_bm25",
            index_name="sparse_bm25_index",
            index_type="SPARSE_WAND",
            metric_type="BM25"
        )

        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            index_params=index_params
        )
        self.client.load_collection(COLLECTION_NAME)

    def _check_existing_hashes(self, hash_list: List[str]) -> Set[str]:
        """批量检查哈希是否存在"""
        if not hash_list:
            return set()

        # 构造正确的IN表达式（使用单引号包裹每个哈希值）
        in_clause = ', '.join([f"'{h}'" for h in hash_list])
        expr = f"hash_id in [{in_clause}]"

        # 使用query方法进行标量查询
        res = self.client.query(
            collection_name=COLLECTION_NAME,
            filter=expr,
            output_fields=["hash_id"]
        )
        return {item["hash_id"] for item in res}

    def load_data(self, start_date: str, end_date: str):
        """主数据加载流程"""
        cursor = self.mysql_conn.cursor()
        try:
            cursor.execute("""
                SELECT title, content, trade_date 
                FROM new_processed_daily_news 
                WHERE trade_date BETWEEN %s AND %s
            """, (start_date, end_date))

            raw_data = []
            hash_list = []
            for title, content, dt in cursor:
                dt_obj = dt if isinstance(dt, datetime) else datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S")
                data_hash = self._generate_hash(title, dt_obj)
                hash_list.append(data_hash)
                raw_data.append({
                    "hash_id": data_hash,
                    "title": title[:MAX_TITLE_LEN],  # 确保长度限制
                    "content": content[:MAX_CONTENT_LEN],
                    "trade_date": int(dt_obj.timestamp() * 1000)
                })

            existing = self._check_existing_hashes(hash_list)
            new_data = [d for d in raw_data if d["hash_id"] not in existing]
            print(f"发现 {len(new_data)} 条新数据需要处理")

            # 批量处理（移除分块逻辑）
            self._process_fulltext_data(new_data)

        finally:
            cursor.close()
            self.mysql_conn.close()

    def _process_fulltext_data(self, data: List[Dict]):
        """处理完整文本数据（优化批处理）"""
        if not data:
            return

        # 合并标题和内容并截断
        combined_texts = [
            f"{item['title']}: {item['content']}"[:MAX_CONTENT_LEN]
            for item in data
        ]

        # 分批生成嵌入
        embeddings = []
        for i in range(0, len(combined_texts), EMBED_BATCH_SIZE):
            batch_texts = combined_texts[i:i+EMBED_BATCH_SIZE]
            print(f"正在处理第 {i//EMBED_BATCH_SIZE+1} 批，共 {len(batch_texts)} 条文本")
            batch_embeddings = self.embedding_generator.embed_documents(batch_texts)
            embeddings.extend(batch_embeddings)

        # 构建有效数据
        valid_count = 0
        insert_data = []
        for idx, item in enumerate(data):
            if embeddings[idx] and len(embeddings[idx]) == DENSE_DIM:
                insert_data.append({
                    **item,
                    "dense": embeddings[idx],
                })
                valid_count += 1
            else:
                print(f"丢弃无效数据：{item['title'][:50]}...")

            # 分批插入
            if insert_data:
                try:
                    # 拆分大数据为小批次
                    total = len(insert_data)
                    for i in range(0, total, INSERT_BATCH_SIZE):
                        batch = insert_data[i:i + INSERT_BATCH_SIZE]
                        print(f"正在插入批次 {i // INSERT_BATCH_SIZE + 1}/{(total - 1) // INSERT_BATCH_SIZE + 1}")
                        res = self.client.insert(
                            collection_name=COLLECTION_NAME,
                            data=batch
                        )
                    print(f"成功插入 {valid_count}/{len(data)} 条数据（分{total // INSERT_BATCH_SIZE + 1}批）")
                except Exception as e:
                    print(f"插入失败: {str(e)}")
            else:
                print("无有效数据需要插入")


if __name__ == "__main__":
    system = NewsSystem()
    try:
        system.load_data(
            # start_date="2025-03-28 00:00:00",
            # end_date="2025-04-11 12:00:00"
            # start_date="2025-04-09 11:00:00",
            # end_date="2025-04-11 11:00:00"
            start_date="2025-03-28 00:00:00",
            end_date="2025-04-11 12:00:00"
        )
    finally:
        system.client.close()

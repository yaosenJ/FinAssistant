# !/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@Author         :  Brisky 
@Version        :  WIN10, Python3.7.9
------------------------------------
@IDE            ： PyCharm
@Description    :  
@CreateTime     :  2025/4/16 21:10
@UpdateTime     :  2025/4/16 21:10
------------------------------------
"""
# !/usr/bin/python3
# -*- coding: utf-8 -*-

from datetime import datetime
import hashlib
import logging
from typing import List, Set, Dict, Optional
import dashscope
import pymysql
from pymilvus import (
    MilvusClient,
    DataType,
    Function,
    FunctionType,
    connections,
    MilvusException
)
import time


# ================= 配置信息 =================
class Config:
    # Milvus配置
    MILVUS_URL = '192.168.1.227:19530'
    MILVUS_TOKEN = "root:Milvus"
    COLLECTION_NAME = "company_news_hybrid"
    CONN_TIMEOUT = 30  # 秒
    CONN_POOL_SIZE = 5

    # MySQL配置
    MYSQL_HOST = '192.168.1.101'
    MYSQL_PORT = 13306
    MYSQL_USER = 'news_user'
    MYSQL_PASSWORD = 'km101'
    MYSQL_DB = 'stock_news'

    # 文本处理参数
    DENSE_DIM = 1024
    MAX_TITLE_LEN = 400
    MAX_CONTENT_LEN = 3000
    EMBED_BATCH_SIZE = 500
    INSERT_BATCH_SIZE = 200

    # API配置
    DASHSCOPE_API_KEY = "sk-48d14c"
    MAX_RETRIES = 3
    RETRY_DELAY = 5


# ================= 日志配置 =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("news_system.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ================= 文本向量生成器 =================
class EmbeddingGenerator:
    def __init__(self):
        dashscope.api_key = Config.DASHSCOPE_API_KEY
        self.client = dashscope.TextEmbedding

    def _handle_retry(self, attempt: int, text: str, error: str):
        if attempt < Config.MAX_RETRIES - 1:
            delay = Config.RETRY_DELAY * (attempt + 1)
            logger.warning(
                f"Retry {attempt + 1}/{Config.MAX_RETRIES} for text: {text[:50]}... "
                f"Error: {error}. Retrying in {delay}s"
            )
            time.sleep(delay)
        else:
            logger.error(f"Failed after {Config.MAX_RETRIES} attempts: {text[:50]}...")

    def embed_documents(self, texts: List[str]) -> List[Optional[List[float]]]:
        embeddings = []
        for idx, text in enumerate(texts):
            clean_text = text.strip()
            if not clean_text:
                embeddings.append(None)
                continue

            for attempt in range(Config.MAX_RETRIES):
                try:
                    response = self.client.call(
                        model='text-embedding-v3',
                        input=clean_text,
                        text_type="document"
                    )

                    if response.status_code == 200:
                        embedding = response.output['embeddings'][0]['embedding']
                        if len(embedding) == Config.DENSE_DIM:
                            embeddings.append(embedding)
                            break
                        else:
                            logger.error(f"Invalid embedding dim: {len(embedding)}")
                            embeddings.append(None)
                            break
                    else:
                        self._handle_retry(attempt, clean_text, response.message)

                except Exception as e:
                    self._handle_retry(attempt, clean_text, str(e))
            else:
                embeddings.append(None)

        return embeddings


# ================= 新闻系统核心类 =================
class NewsSystem:
    def __init__(self):
        # 初始化连接池
        self._init_milvus_connection()
        self._init_mysql_connection()
        self.embedding_generator = EmbeddingGenerator()
        self._create_collection()

    def _init_milvus_connection(self):
        """初始化Milvus连接池"""
        try:
            connections.connect(
                "default",
                uri=f"http://{Config.MILVUS_URL}",
                token=Config.MILVUS_TOKEN,
                timeout=Config.CONN_TIMEOUT,
                pool_size=Config.CONN_POOL_SIZE
            )
            self.client = MilvusClient(using="default")
            logger.info("Milvus连接池初始化成功")
        except MilvusException as e:
            logger.error(f"Milvus连接失败: {str(e)}")
            raise

    def _init_mysql_connection(self):
        """初始化MySQL连接"""
        try:
            self.mysql_conn = pymysql.connect(
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                db=Config.MYSQL_DB,
                charset='utf8mb4',
                connect_timeout=Config.CONN_TIMEOUT
            )
            logger.info("MySQL连接成功")
        except pymysql.Error as e:
            logger.error(f"MySQL连接失败: {str(e)}")
            raise

    def _create_collection(self):
        """创建或验证集合"""
        try:
            if Config.COLLECTION_NAME in self.client.list_collections():
                logger.info(f"集合 {Config.COLLECTION_NAME} 已存在，正在验证...")
                self.client.load_collection(Config.COLLECTION_NAME)
                return

            logger.info(f"正在创建新集合: {Config.COLLECTION_NAME}")

            # 创建Schema
            schema = self.client.create_schema(enable_dynamic_field=True)
            schema.add_field("hash_id", DataType.VARCHAR, is_primary=True, max_length=32)
            schema.add_field("title", DataType.VARCHAR, max_length=Config.MAX_TITLE_LEN)
            schema.add_field(
                "content", DataType.VARCHAR,
                max_length=Config.MAX_CONTENT_LEN,
                enable_analyzer=True,
                analyzer_params={"type": "chinese"},
                enable_match=True
            )
            schema.add_field("dense", DataType.FLOAT_VECTOR, dim=Config.DENSE_DIM)
            schema.add_field("sparse_bm25", DataType.SPARSE_FLOAT_VECTOR)
            schema.add_field("trade_date", DataType.INT64)

            # BM25函数
            schema.add_function(Function(
                name="bm25",
                function_type=FunctionType.BM25,
                input_field_names=["content"],
                output_field_names="sparse_bm25",
            ))

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
                collection_name=Config.COLLECTION_NAME,
                schema=schema,
                index_params=index_params
            )
            self.client.load_collection(Config.COLLECTION_NAME)
            logger.info("集合创建完成")

        except MilvusException as e:
            logger.error(f"集合操作失败: {str(e)}")
            raise

    def _safe_query(self, expr: str) -> Set[str]:
        """带重试的查询操作"""
        for attempt in range(3):
            try:
                res = self.client.query(
                    collection_name=Config.COLLECTION_NAME,
                    filter=expr,
                    output_fields=["hash_id"]
                )
                return {item["hash_id"] for item in res}
            except MilvusException as e:
                logger.warning(f"查询重试 {attempt + 1}/3: {str(e)}")
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
                self._reconnect_milvus()

    def _reconnect_milvus(self):
        """重新建立Milvus连接"""
        try:
            connections.disconnect("default")
            connections.connect("default", uri=f"http://{Config.MILVUS_URL}",
                                token=Config.MILVUS_TOKEN)
            self.client = MilvusClient(using="default")
            logger.info("Milvus重连成功")
        except Exception as e:
            logger.error(f"Milvus重连失败: {str(e)}")
            raise

    def _check_existing_hashes(self, hash_list: List[str]) -> Set[str]:
        """批量检查哈希存在性"""
        if not hash_list:
            return set()

        in_clause = ", ".join([f"'{h}'" for h in hash_list])
        expr = f"hash_id in [{in_clause}]"

        try:
            return self._safe_query(expr)
        except Exception as e:
            logger.error(f"哈希检查失败: {str(e)}")
            return set()

    def _generate_hash(self, title: str, dt: datetime) -> str:
        """生成唯一哈希标识"""
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return hashlib.md5(f"{title}||{time_str}".encode()).hexdigest()

    def load_data(self, start_date: str, end_date: str):
        """主数据加载流程"""
        cursor = None
        try:
            cursor = self.mysql_conn.cursor()
            logger.info(f"开始加载数据 {start_date} 至 {end_date}")

            # 执行查询
            cursor.execute("""
                SELECT title, content, trade_date 
                FROM new_processed_daily_news 
                WHERE trade_date BETWEEN %s AND %s
            """, (start_date, end_date))

            # 数据预处理
            raw_data, hash_list = [], []
            for title, content, dt in cursor:
                dt_obj = dt if isinstance(dt, datetime) else datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S")
                data_hash = self._generate_hash(title, dt_obj)
                hash_list.append(data_hash)
                raw_data.append({
                    "hash_id": data_hash,
                    "title": title[:Config.MAX_TITLE_LEN],
                    "content": content[:Config.MAX_CONTENT_LEN],
                    "trade_date": int(dt_obj.timestamp() * 1000)
                })

            # 过滤已存在数据
            existing = self._check_existing_hashes(hash_list)
            new_data = [d for d in raw_data if d["hash_id"] not in existing]
            logger.info(f"发现新数据: 总计 {len(new_data)} 条")

            # 处理并插入数据
            if new_data:
                self._process_and_insert(new_data)

        except Exception as e:
            logger.error(f"数据加载失败: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
            self.mysql_conn.close()

    def _process_and_insert(self, data: List[Dict]):
        """处理并插入数据"""
        logger.info("开始处理文本嵌入...")
        combined_texts = [
            f"{item['title']}: {item['content']}"[:Config.MAX_CONTENT_LEN]
            for item in data
        ]

        # 分批生成嵌入
        embeddings = []
        for i in range(0, len(combined_texts), Config.EMBED_BATCH_SIZE):
            batch = combined_texts[i:i + Config.EMBED_BATCH_SIZE]
            logger.info(f"处理嵌入批次 {i // Config.EMBED_BATCH_SIZE + 1}")
            embeddings.extend(self.embedding_generator.embed_documents(batch))

        # 构建插入数据
        insert_data = []
        for idx, item in enumerate(data):
            if embeddings[idx] and len(embeddings[idx]) == Config.DENSE_DIM:
                insert_data.append({**item, "dense": embeddings[idx]})
            else:
                logger.warning(f"丢弃无效数据: {item['title'][:50]}...")

        # 分批插入
        if insert_data:
            logger.info(f"准备插入 {len(insert_data)} 条有效数据")
            self._batch_insert(insert_data)
        else:
            logger.warning("无有效数据需要插入")

    def _batch_insert(self, data: List[Dict]):
        """带重试的批量插入"""
        total = len(data)
        success_count = 0

        for i in range(0, total, Config.INSERT_BATCH_SIZE):
            batch = data[i:i + Config.INSERT_BATCH_SIZE]
            batch_num = (i // Config.INSERT_BATCH_SIZE) + 1
            logger.info(f"插入批次 {batch_num}/{(total - 1) // Config.INSERT_BATCH_SIZE + 1}")

            for retry in range(3):
                try:
                    res = self.client.insert(
                        collection_name=Config.COLLECTION_NAME,
                        data=batch,
                        params={"timeout": 60}
                    )
                    success_count += len(batch)
                    logger.debug(f"批次 {batch_num} 插入成功: {res}")
                    break
                except MilvusException as e:
                    logger.warning(f"插入重试 {retry + 1}/3: {str(e)}")
                    if retry == 2:
                        logger.error(f"最终插入失败: {str(e)}")
                    else:
                        time.sleep(2 ** retry)
                        self._reconnect_milvus()

        logger.info(f"数据插入完成，成功 {success_count}/{total} 条")

    def __del__(self):
        """资源清理"""
        try:
            connections.disconnect("default")
            logger.info("Milvus连接已关闭")
        except Exception as e:
            logger.error(f"连接关闭异常: {str(e)}")


if __name__ == "__main__":
    try:
        system = NewsSystem()
        system.load_data(
            # start_date="2025-04-09 11:00:00",
            # end_date="2025-04-11 11:00:00"
            # start_date="2025-03-28 00:00:00",
            # end_date="2025-04-01 00:00:00"
            start_date="2025-03-28 00:00:00",
            end_date="2025-04-11 12:00:00"
        )
    except Exception as e:
        logger.error(f"系统运行失败: {str(e)}", exc_info=True)
    finally:
        del system
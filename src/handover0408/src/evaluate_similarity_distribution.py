# !/usr/bin/python3
# -*- coding: utf-8 -*-
# ================ 新增导入 ================
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date
from typing import List, Dict, Set
import hashlib

# ================= 第三方库导入 =================
import numpy as np
import pandas as pd
import pymysql
from fuzzywuzzy import fuzz
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
# plt.switch_backend('Agg')  # 用于无GUI环境的服务器
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

# 设置matplotlib正常显示中文和负号
plt.rcParams['font.sans-serif'] = ['SimHei']  # 指定默认字体为黑体
plt.rcParams['axes.unicode_minus'] = False

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
BATCH_SIZE = 500


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
                    top_k: int = 10000) -> List[Dict]:
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
        return sorted(semantic_results, key=lambda x: x['score'], reverse=True)[:10000]

    def plot_similarity_distribution(self, scores: List[float], query: str) -> None:
        """绘制学术风格相似度分布直方图（0.1区间）"""
        if not scores:
            print("无有效数据可绘制分布图")
            return

        try:
            # ========== 样式设置 ==========
            try:
                import seaborn as sns
                sns.set_style("whitegrid")
                sns.set_palette("deep")  # 使用更专业的调色板
            except ImportError:
                plt.style.use('ggplot')  # 使用Matplotlib内置样式

            # ========== 参数配置 ==========
            plt.rcParams.update({
                'font.family': 'SimHei',  # 更兼容的字体
                'font.size': 12,
                'axes.titlesize': 14,
                'axes.labelsize': 12,
                'xtick.labelsize': 10,
                'ytick.labelsize': 10,
                'figure.dpi': 300,
                'savefig.bbox': 'tight',
                'grid.color': '#e0e0e0',
                'grid.linestyle': '--',
                'grid.linewidth': 0.8
            })

            # ========== 数据准备 ==========
            bins = np.arange(0, 1.01, 0.1)
            clean_query = "".join(x for x in query[:50] if x.isalnum() or x in (" ", "_"))  # 清理特殊字符
            clean_query = clean_query or "query"  # 防止空查询

            # ========== 绘图核心 ==========
            fig, ax = plt.subplots(figsize=(8, 5))
            n, bins, patches = ax.hist(
                scores,
                bins=bins,
                edgecolor='#37474f',
                facecolor='#1565c0',
                alpha=0.9,
                linewidth=0.8
            )

            # ========== 标注优化 ==========
            max_count = max(n) if n.size > 0 else 1
            for i, patch in enumerate(patches):
                if n[i] > 0:
                    ax.text(
                        x=patch.get_x() + patch.get_width() / 2,
                        y=n[i] + max_count * 0.03,
                        s=f'{int(n[i])}',
                        ha='center',
                        va='bottom',
                        fontsize=9,
                        color='#263238'
                    )

            # ========== 坐标轴设置 ==========
            ax.set_title(
                f"Similarity Distribution: '{clean_query[:30]}...'" if len(clean_query) > 30
                else f"Similarity Distribution: '{clean_query}'",
                pad=20
            )
            ax.set_xlabel('Cosine Similarity', labelpad=10)
            ax.set_ylabel('Count', labelpad=10)

            # X轴标签设置
            ax.set_xticks(np.arange(0, 1.1, 0.1))
            ax.set_xticklabels([f'{x:.1f}' for x in np.arange(0, 1.1, 0.1)], rotation=45)
            ax.xaxis.set_major_locator(plt.MultipleLocator(0.1))

            # Y轴动态刻度
            y_step = max(1, int(max_count / 5))
            ax.yaxis.set_major_locator(plt.MultipleLocator(y_step))
            ax.set_ylim(0, max_count * 1.15)

            # ========== 统计信息 ==========
            stats_text = (
                f'n = {len(scores)}\n'
                f'μ = {np.mean(scores):.3f} ± {np.std(scores):.3f}\n'
                f'min = {np.min(scores):.3f}\n'
                f'max = {np.max(scores):.3f}'
            )
            ax.text(
                0.97, 0.97,
                stats_text,
                transform=ax.transAxes,
                ha='right',
                va='top',
                fontsize=9,
                bbox=dict(facecolor='white', alpha=0.8, pad=5, edgecolor='none')
            )

            # ========== 保存输出 ==========
            filename = f"sim_dist_{clean_query[:20]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            filename = filename.replace(" ", "_")  # 确保文件名合法
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"分布图已保存至: {filename}")

        except Exception as e:
            print(f"生成分布图失败: {str(e)}")
        finally:
            plt.close(fig) if 'fig' in locals() else plt.close()

    def print_results(self, results: List[Dict], query: str) -> None:  # 修改方法签名
        """可视化打印结果并添加分布图"""
        print(f"\n{'=' * 50}")
        print(f"找到{len(results)}条结果：")

        # 收集相似度分数
        scores = [item['score'] for item in results]

        # 打印结果（保持原有逻辑）
        for i, item in enumerate(results, 1):
            dt = datetime.fromtimestamp(item['trade_date'] / 1000)
            print(f"\n#{i} [{dt.strftime('%Y-%m-%d %H:%M')}] 相似度: {item['score']:.4f}")
            print(f"标题: {item['title']}")
            print(f"内容摘要: {item['content'][:150]}...")

        # 新增分布图绘制
        if scores:
            self.plot_similarity_distribution(scores, query)

    def get_results(self, results: List[Dict]) -> List[str]:
        """获取结果文本"""
        return [item['title'] + item['content'] for item in results]

    def close(self) -> None:
        self.vector_db.close()


# ================ 修改主程序部分 ================
if __name__ == "__main__":
    system = NewsSearchSystem()
    try:
        # print("正在初始化数据...")
        # system.load_data()

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
            system.print_results(results, query)  # 传入query参数

    finally:
        system.close()

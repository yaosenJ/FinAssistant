# !/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@Author         :  Brisky 
@Version        :  WIN10, Python3.7.9
------------------------------------
@IDE            ： PyCharm
@Description    :  
@CreateTime     :  2025/4/16 23:01
@UpdateTime     :  2025/4/16 23:01
------------------------------------
"""
from datetime import datetime
import logging
from typing import List
from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker, connections
from langchain_community.embeddings import DashScopeEmbeddings
from dashscope import Generation


# ================= 配置信息 (与插入代码统一) =================
class Config:
    # Milvus配置
    MILVUS_URL = '192.168.1.227:19530'  # 与插入代码保持一致
    MILVUS_TOKEN = "root:Milvus"  # 生产环境建议使用环境变量
    COLLECTION_NAME = "company_news_hybrid"  # 使用相同集合名
    CONN_TIMEOUT = 30

    # 检索参数
    TOP_K = 5  # 检索结果数量
    DENSE_SEARCH_PARAMS = {  # 与插入代码索引配置一致
        "metric_type": "COSINE",
        "params": {"nprobe": 32}  # 根据实际数据量调整
    }
    RRF_WINDOW_SIZE = 100  # RRF融合窗口大小

    # 大模型配置
    DASHSCOPE_API_KEY = "sk-48d14c2089"
    LLM_MODEL = "qwen-max"  # 改用更强大的模型


# ================= 日志配置 =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# ================= 混合检索系统 =================
class HybridSearchSystem:
    def __init__(self):
        self._init_milvus()
        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v3",  # 与插入代码版本一致
            dashscope_api_key=Config.DASHSCOPE_API_KEY
        )

    def _init_milvus(self):
        """初始化Milvus连接"""
        try:
            self.client = MilvusClient(
                uri=f"http://{Config.MILVUS_URL}",
                token=Config.MILVUS_TOKEN,
                db_name="default",
                timeout=Config.CONN_TIMEOUT
            )
            logger.info("Milvus客户端初始化成功")
        except Exception as e:
            logger.error(f"Milvus连接失败: {str(e)}")
            raise

    def _hybrid_search(self, query: str) -> List[dict]:
        """执行混合检索（修复版）"""
        try:
            # 生成向量
            query_emb = self.embeddings.embed_documents([query])[0]

            # 构建双路请求
            dense_req = AnnSearchRequest(
                data=[query_emb],
                anns_field="dense",
                param=Config.DENSE_SEARCH_PARAMS,
                limit=Config.TOP_K * 2
            )

            sparse_req = AnnSearchRequest(
                data=[query],
                anns_field="sparse_bm25",
                param={"metric_type": "BM25"},
                limit=Config.TOP_K * 2
            )

            # 执行检索
            results = self.client.hybrid_search(
                collection_name=Config.COLLECTION_NAME,
                reqs=[dense_req, sparse_req],
                ranker=RRFRanker(k=Config.RRF_WINDOW_SIZE),
                limit=Config.TOP_K,
                output_fields=["title", "content"]
            )

            # 正确解析双重列表结构
            processed_results = []
            for result_group in results:  # 遍历每个检索路径的结果组
                for hit in result_group:  # 遍历组内每个命中结果
                    entity = hit.get("entity", {})
                    processed_results.append({
                        "title": entity.get("title", "无标题"),
                        "content": entity.get("content", "")
                    })

            return processed_results[:Config.TOP_K]  # 截取前 TOP_K 个结果

        except Exception as e:
            logger.error(f"检索失败: {str(e)}")
            return []

    def _generate_answer(self, query: str, context: List[str]) -> str:
        """生成回答"""
        try:
            # 构建提示词模板
            context_str = "\n".join(
                [f"[{i + 1}] {doc['content'][:300]}..." for i, doc in enumerate(context)]
            )

            prompt = f"""基于以下新闻数据回答问题：

            {context_str}

            请用中文简洁明了地回答：{query}
            """

            response = Generation.call(
                model=Config.LLM_MODEL,
                prompt=prompt,
                seed=42,  # 固定随机种子保证可复现
                top_p=0.8,
                temperature=0.3
            )
            return response.output.text
        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            return "暂时无法生成回答"

    def query(self, question: str) -> dict:
        """完整检索流程"""
        try:
            # 执行混合检索
            results = self._hybrid_search(question)

            # 生成回答
            answer = self._generate_answer(question, results)

            return {
                "answer": answer,
                "references": [{
                    "title": doc["title"],
                    "content": doc["content"]
                } for doc in results]
            }
        except Exception as e:
            logger.error(f"查询流程异常: {str(e)}")
            return {"error": "服务暂时不可用"}


# ================= 使用示例 =================
if __name__ == "__main__":
    try:
        system = HybridSearchSystem()

        # 测试查询
        question = "特斯拉第一季度的交付量是多少？"
        response = system.query(question)

        print("\n===== 生成回答 =====")
        print(response["answer"])

        print("\n===== 参考来源 =====")
        for ref in response["references"]:
            print(f"{ref['title']}")
            print(ref["content"][:200] + "...\n")

    except Exception as e:
        logger.error(f"系统运行失败: {str(e)}")
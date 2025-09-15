# !/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from typing import List, Tuple
import pandas as pd
from tqdm import tqdm
from datasets import Dataset
from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker
from langchain_community.llms import Tongyi
from langchain_community.embeddings import DashScopeEmbeddings
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from dashscope import Generation
import dashscope
import requests

# ================= 系统配置 =================
class Config:
    # Milvus配置
    MILVUS_URL = '192.168.1.227:19530'
    MILVUS_TOKEN = "root:Milvus"
    COLLECTION_NAME = "company_news_hybrid"
    CONN_TIMEOUT = 30
    RERANK_TOP_N = 2
    # 检索参数
    TOP_K = 4

    DENSE_SEARCH_PARAMS = {
        "metric_type": "COSINE",
        "params": {"nprobe": 32}
    }
    RRF_WINDOW_SIZE = 100

    # 大模型配置
    DASHSCOPE_API_KEY = "sk-48d14c2089104df1"
    LLM_MODEL = "qwen-max"

    # 评估配置
    QA_DATA_PATH = "../data/qa_pairs_update.csv"
    OUTPUT_PATH = "../data/qa_pairs_update/rag_results_hybrid_re.csv"

    # QA_DATA_PATH = "../data/qa_pairs.csv"
    # OUTPUT_PATH = "../data/qa_pairs/rag_results_hybrid.csv"


# ================= 日志配置 =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# ================= 混合检索系统核心类 =================
class HybridSearchSystem:
    def __init__(self):
        self._init_milvus()
        self._init_embeddings()
        dashscope.api_key = Config.DASHSCOPE_API_KEY

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

    def _init_embeddings(self):
        """初始化文本嵌入模型"""
        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=Config.DASHSCOPE_API_KEY
        )

        # 新增重排方法
    def _rerank_contexts(self, query: str, contexts: List[dict]) -> List[dict]:
        """使用本地部署的BGE reranker进行重排"""
        api_url = "http://192.168.1.119:8011/rerank"

        try:
            # 提取纯文本内容用于重排
            context_texts = [f"标题：{ctx['title']}\n内容：{ctx['content']}" for ctx in contexts]

            payload = {
                "query": query,
                "documents": context_texts
            }

            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                results = response.json().get('results', [])

                # 将重排结果映射回原始数据结构
                return [item['document'] for item in results[:Config.RERANK_TOP_N]]

            return contexts[:Config.RERANK_TOP_N]
        except Exception as e:
            logger.error(f"重排失败: {str(e)[:200]}")
            return contexts[:Config.RERANK_TOP_N]

    def _hybrid_search(self, query: str) -> List[dict]:
        """执行混合检索"""
        try:
            # 生成向量
            query_emb = self.embeddings.embed_query(query)

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

            # 解析结果
            processed_results = []
            for result_group in results:
                for hit in result_group:
                    entity = hit.get("entity", {})
                    processed_results.append({
                        "title": entity.get("title", "无标题"),
                        "content": entity.get("content", "")
                    })
            return processed_results[:Config.TOP_K]

        except Exception as e:
            logger.error(f"检索失败: {str(e)}")
            return []

    def _generate_answer(self, query: str, context: List[dict]) -> str:
        """生成回答"""
        try:
            context_str = str(context)

            prompt = f"""基于以下新闻数据回答问题：

            {context_str}

            请用中文简洁明了地回答：{query}
            """

            response = Generation.call(
                model=Config.LLM_MODEL,
                prompt=prompt,
                seed=42,
                top_p=0.8,
                temperature=0.3
            )
            return response.output.text
        except Exception as e:
            logger.error(f"生成回答失败: {str(e)}")
            return "暂时无法生成回答"

    def query(self, question: str) -> dict:
        """完整查询接口"""
        try:
            # 1. 混合检索
            results = self._hybrid_search(question)

            # 2. 重排
            if results:
                results = self._rerank_contexts(question, results)

            # 3. 生成答案
            answer = self._generate_answer(question, results)

            return {
                "answer": answer,
                "references": results
            }
        except Exception as e:
            logger.error(f"查询流程异常: {str(e)}")
            return {"error": "服务暂时不可用"}

    def query_with_context(self, question: str) -> Tuple[str, List[dict]]:
        """获取答案和上下文（用于评估）"""
        try:
            results = self._hybrid_search(question)

            # 新增重排步骤
            if results:
                results = self._rerank_contexts(question, results)

            answer = self._generate_answer(question, results)
            return answer, results
        except Exception as e:
            logger.error(f"获取上下文失败: {str(e)}")
            return "", []


# ================= RAG评估功能 =================
class RagEvaluator:
    def __init__(self):
        self.system = HybridSearchSystem()
        self._init_metrics()

    def _init_metrics(self):
        """初始化评估指标"""
        # 大语言模型
        llm = Tongyi(
            model=Config.LLM_MODEL,
            api_key=Config.DASHSCOPE_API_KEY
        )
        self.generator_llm = LangchainLLMWrapper(llm)

        # 嵌入模型
        qwen_embedding = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=Config.DASHSCOPE_API_KEY
        )
        self.qwen_embeddings = LangchainEmbeddingsWrapper(qwen_embedding)

        # 配置评估指标
        faithfulness.llm = self.generator_llm
        answer_relevancy.llm = self.generator_llm
        answer_relevancy.embeddings = self.qwen_embeddings
        context_recall.llm = self.generator_llm
        context_precision.llm = self.generator_llm

    def process_qa_data(self, csv_path: str) -> Dataset:
        """处理QA数据并生成评估数据集"""
        df_input = pd.read_csv(csv_path, encoding='utf-8')
        question_list = df_input["question"].tolist()
        ground_truth_list = df_input["answer"].tolist()

        filtered_questions = []
        filtered_ground_truths = []
        contexts_list = []
        answer_list = []

        for q, gt in tqdm(zip(question_list, ground_truth_list),
                          total=len(question_list),
                          desc="处理QA数据"):
            try:
                answer, contexts = self.system.query_with_context(q)
                if not answer or not contexts:
                    continue
                contexts_list.append(contexts)
                answer_list.append(answer)
                filtered_questions.append(q)
                filtered_ground_truths.append(gt)
            except Exception as e:
                logger.error(f"处理问题失败: {q}, 错误: {str(e)[:200]}...")
                continue

        df = pd.DataFrame({
            "question": filtered_questions,
            "contexts": contexts_list,
            "answer": answer_list,
            "ground_truth": filtered_ground_truths,
        })
        return Dataset.from_pandas(df)

    def evaluate(self, dataset: Dataset) -> dict:
        """执行评估并返回结果"""
        if len(dataset) == 0:
            logger.warning("没有有效数据可供评估")
            return {}

        result = evaluate(
            dataset,
            metrics=[
                answer_relevancy,
                faithfulness,
                context_recall,
                context_precision,
            ]
        )
        return result


def main():
    logger.info("启动RAG评估流程...")
    evaluator = RagEvaluator()

    # 处理数据
    dataset = evaluator.process_qa_data(Config.QA_DATA_PATH)

    # 保存处理结果
    dataset.to_pandas().to_csv(Config.OUTPUT_PATH, index=False)
    logger.info(f"中间结果已保存至 {Config.OUTPUT_PATH}")

    # 执行评估
    if len(dataset) > 0:
        result = evaluator.evaluate(dataset)
        logger.info("\n评估结果:")
        print(result)
    else:
        logger.warning("没有有效数据可供评估")


if __name__ == "__main__":
    main()
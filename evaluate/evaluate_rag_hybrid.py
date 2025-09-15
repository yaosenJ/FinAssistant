# # # #!/usr/bin/python3
# # # # -*- coding: utf-8 -*-
# # # from datetime import datetime, timedelta, date
# # # from typing import List, Dict, Set
# # # import numpy as np
# # # from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
# # # from datasets import Dataset
# # # import pandas as pd
# # # from tqdm import tqdm
# # # from ragas import evaluate
# # # from ragas.llms import LangchainLLMWrapper
# # # from ragas.metrics import (
# # #     answer_relevancy,
# # #     faithfulness,
# # #     context_recall,
# # #     context_precision,
# # # )
# # # from langchain_community.llms import Tongyi
# # # from langchain_community.embeddings import DashScopeEmbeddings
# # # from ragas.embeddings import LangchainEmbeddingsWrapper
# # # from openai import OpenAI, BadRequestError
# # # import dashscope
# # # from http import HTTPStatus
# # #
# # # # Milvus配置
# # # MILVUS_HOST = '192.168.1.227'
# # # MILVUS_PORT = '19530'
# # # COLLECTION_NAME = "company_news_hybrid"
# # # EMBEDDING_DIM = 1024
# # #
# # #
# # # # ================= 交易日历处理模块 =================
# # # class TradeCalendar:
# # #     def __init__(self, csv_path: str = '../data/time.csv') -> None:
# # #         self.trade_dates = self._load_trade_dates(csv_path)
# # #         self.trade_dates.sort()
# # #
# # #     def _load_trade_dates(self, path: str) -> List[date]:
# # #         """加载并解析交易日数据"""
# # #         df = pd.read_csv(path, dtype={'cal_date': str})
# # #         dates = []
# # #         for d in df['cal_date']:
# # #             try:
# # #                 dt = datetime.strptime(d, "%Y%m%d").date()
# # #                 dates.append(dt)
# # #             except ValueError:
# # #                 continue
# # #         return dates
# # #
# # #     def get_last_trade_date(self, target_date: date = None) -> date:
# # #         """获取指定日期前最近的交易日"""
# # #         target = target_date or date.today()
# # #         for td in reversed(self.trade_dates):
# # #             if td <= target:
# # #                 return td
# # #         return self.trade_dates[-1]  # 保底返回最后一个
# # #
# # #     def get_n_days_back(self, end_date: date, n_days: int) -> date:
# # #         """从end_date往前找n个交易日"""
# # #         try:
# # #             idx = self.trade_dates.index(end_date)
# # #             start_idx = max(0, idx - n_days + 1)
# # #             return self.trade_dates[start_idx]
# # #         except ValueError:
# # #             return self.trade_dates[0]
# # #
# # #
# # # TRADE_CALENDAR = TradeCalendar()
# # #
# # #
# # # def get_dynamic_dates(n_days: int) -> tuple[str, str]:
# # #     """动态计算日期范围"""
# # #     end_date = TRADE_CALENDAR.get_last_trade_date()
# # #     start_date = TRADE_CALENDAR.get_n_days_back(end_date, n_days)
# # #     return (
# # #         start_date.strftime("%Y-%m-%d 00:00:00"),
# # #         end_date.strftime("%Y-%m-%d 23:59:59")
# # #     )
# # #
# # #
# # # # ================= Milvus向量数据库操作类 =================
# # # class MilvusVectorDB:
# # #     def __init__(self) -> None:
# # #         self.collection = None
# # #         self._connect_to_milvus()
# # #         self._setup_collection()
# # #
# # #     def _connect_to_milvus(self) -> None:
# # #         """连接Milvus数据库"""
# # #         connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, alias='default')
# # #         # print("成功连接到Milvus数据库")
# # #
# # #     def _setup_collection(self) -> None:
# # #         """连接集合"""
# # #         self.collection = Collection(COLLECTION_NAME)
# # #         # print(f"连接到现有集合: {COLLECTION_NAME}")
# # #         self.collection.load()
# # #
# # #     def retrieve(self,
# # #                  query_embedding: List[float],
# # #                  time_filter: str,
# # #                  top_k: int = 100) -> List[Dict]:
# # #         """带时间过滤的向量搜索"""
# # #         query_array = np.array(query_embedding)
# # #         normalized_query = (query_array / np.linalg.norm(query_array)).tolist()
# # #
# # #         results = self.collection.search(
# # #             data=[normalized_query],
# # #             anns_field="embedding",
# # #             param={"metric_type": "COSINE", "params": {"nprobe": 64}},
# # #             expr=time_filter,
# # #             limit=top_k,
# # #             output_fields=["title", "content", "trade_date"]
# # #         )
# # #
# # #         return [{
# # #             "title": hit.entity.get("title"),
# # #             "content": hit.entity.get("content"),
# # #             "trade_date": hit.entity.get("trade_date"),
# # #             "score": hit.distance
# # #         } for hits in results for hit in hits]
# # #
# # #     def close(self) -> None:
# # #         connections.disconnect('default')
# # #         print("Milvus连接已关闭")
# # #
# # #
# # # # ================= 文本向量生成器 =================
# # # class EmbeddingGenerator:
# # #     def __init__(self) -> None:
# # #         import dashscope
# # #         dashscope.api_key = "sk-48d14c2089104d"
# # #         self.client = dashscope.TextEmbedding
# # #
# # #     def get_embedding(self, text: str) -> List[float]:
# # #         try:
# # #             response = self.client.call(
# # #                 model='text-embedding-v3',
# # #                 input=text,
# # #                 text_type="document"
# # #             )
# # #             return response.output['embeddings'][0]['embedding'] if response.status_code == 200 else None
# # #         except Exception as e:
# # #             print(f"生成向量失败: {str(e)}")
# # #             return None
# # #
# # #
# # # # ================= 新闻搜索系统主类 =================
# # # class NewsSearchAnswerSystem:
# # #     def __init__(self, search_days: int = 20) -> None:
# # #         self.embedding = EmbeddingGenerator()
# # #         self.vector_db = MilvusVectorDB()
# # #         self.processed_hashes = set()
# # #         self.search_days = search_days
# # #         self.SYSTEM_PROMPT = """
# # #         你是一个AI助手。你需要根据提供的上下文片段来回答问题,生成答案中不要出现“根据提供的信息”等文字。
# # #         """
# # #
# # #         self.USER_PROMPT = """
# # #         请使用以下包含在<context>标签中的信息，回答<question>标签中的问题：
# # #         <context>
# # #         {context}
# # #         </context>
# # #         <question>
# # #         {question}
# # #         </question>
# # #         """
# # #
# # #     def search_news(self, query: str, days: int = None) -> List[Dict]:
# # #         _, target_end = get_dynamic_dates(self.search_days)
# # #         end_dt = datetime.strptime(target_end, "%Y-%m-%d %H:%M:%S")
# # #
# # #         if days is not None:
# # #             start_date = TRADE_CALENDAR.get_n_days_back(end_dt.date(), days)
# # #             # 修复：将date转换为datetime
# # #             start_dt = datetime.combine(start_date, datetime.min.time())
# # #             start_ts = int(start_dt.timestamp() * 1000)
# # #         else:
# # #             start_ts = int(end_dt.timestamp() * 1000 - 365 * 24 * 3600 * 1000)
# # #
# # #         end_ts = int(end_dt.timestamp() * 1000)
# # #         time_filter = f"trade_date >= {start_ts} && trade_date <= {end_ts}"
# # #
# # #         query_embedding = self.embedding.get_embedding(query)
# # #         if not query_embedding:
# # #             return []
# # #
# # #         semantic_results = self.vector_db.retrieve(query_embedding, time_filter)
# # #         # Filter results with score >= 0.4
# # #         filtered_results = [res for res in semantic_results if res['score'] >= 0.4]
# # #         # Sort by score in descending order and take top 10
# # #         return sorted(filtered_results, key=lambda x: x['score'], reverse=True)[:5]
# # #
# # #     def rerank_contexts(self, query: str, contexts: List[str], top_n: int = 2) -> List[str]:
# # #         """使用API进行上下文重排"""
# # #         try:
# # #             import dashscope
# # #             dashscope.api_key = "sk-48d14c2089"
# # #             resp = dashscope.TextReRank.call(
# # #                 model="gte-rerank-v2",
# # #                 query=query,
# # #                 documents=contexts,
# # #                 top_n=top_n,
# # #                 return_documents=True
# # #             )
# # #             if resp.status_code == HTTPStatus.OK:
# # #                 return [doc['document']['text'] for doc in resp.output['results']]
# # #             return contexts[:top_n]
# # #         except Exception as e:
# # #             print(f"重排失败: {str(e)}")
# # #             return contexts[:top_n]
# # #
# # #     def print_results(self, results: List[Dict]) -> None:
# # #         """可视化打印结果"""
# # #         print(f"\n{'=' * 50}")
# # #         print(f"找到{len(results)}条结果：")
# # #         for i, item in enumerate(results, 1):
# # #             dt = datetime.fromtimestamp(item['trade_date'] / 1000)
# # #             print(f"\n#{i} [{dt.strftime('%Y-%m-%d %H:%M')}] 相似度: {item['score']:.4f}")
# # #             print(f"标题: {item['title']}")
# # #             print(f"内容摘要: {item['content'][:150]}...")
# # #
# # #     def get_results(self, results: List[Dict]) -> List[str]:
# # #         """获取结果文本"""
# # #         return [item['title'] + item['content'] for item in results]
# # #
# # #     def close(self) -> None:
# # #         self.vector_db.close()
# # #
# # #     def answer(
# # #             self,
# # #             question: str,
# # #             return_retrieved_text: bool = False,
# # #     ):
# # #         """
# # #         Answer the given question with the retrieved knowledge.
# # #         """
# # #         retrieved_texts = self.search_news(question, int(14))
# # #         text_contexts = [f"标题：{c['title']}\n内容：{c['content']}" for c in retrieved_texts]
# # #
# # #         # 新增重排步骤
# # #         reranked_texts = self.rerank_contexts(query=question, contexts=text_contexts)
# # #         user_prompt = self.USER_PROMPT.format(
# # #             context="\n".join(str(reranked_texts)), question=question
# # #         )
# # #         QWEN_API_KEY = "sk-48d14c2089104"
# # #         QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# # #
# # #         # ================= 服务初始化 =================
# # #         # 配置Dashscope向量模型
# # #         dashscope.api_key = QWEN_API_KEY
# # #
# # #         openai_client = OpenAI(
# # #             api_key=QWEN_API_KEY,
# # #             base_url=QWEN_BASE_URL
# # #         )
# # #
# # #         response = openai_client.chat.completions.create(
# # #             model="qwen-plus",
# # #             messages=[
# # #                 {"role": "system", "content": self.SYSTEM_PROMPT},
# # #                 {"role": "user", "content": user_prompt},
# # #             ],
# # #         )
# # #         if not return_retrieved_text:
# # #             return response.choices[0].message.content
# # #         else:
# # #             return response.choices[0].message.content, retrieved_texts
# # #
# # #
# # # csv_path = "../data/qa_pairs.csv"
# # # df_input = pd.read_csv(csv_path, encoding='gbk')
# # # question_list = df_input["question"].tolist()
# # # ground_truth_list = df_input["answer"].tolist()
# # # # print(question_list)
# # # # print(ground_truth_list)
# # # # 初始化过滤后的结果列表
# # # filtered_questions = []
# # # filtered_ground_truths = []
# # # contexts_list = []
# # # answer_list = []
# # #
# # # for question, ground_truth in tqdm(zip(question_list, ground_truth_list),
# # #                                    total=len(question_list),
# # #                                    desc="回答问题"):
# # #     try:
# # #         # 尝试获取答案和上下文
# # #         answer, contexts = NewsSearchAnswerSystem().answer(question, return_retrieved_text=True)
# # #
# # #         # 处理可能的内容审查错误（如果API返回空结果）
# # #         if not answer or not contexts:
# # #             print(f"问题 '{question}' 返回空结果，已跳过")
# # #             continue
# # #
# # #         # 格式化上下文信息
# # #         text_contexts = [
# # #             f"标题：{ctx['title']}\n内容：{ctx['content']}"
# # #             for ctx in contexts
# # #         ]
# # #
# # #         # 收集有效结果
# # #         contexts_list.append(text_contexts)
# # #         answer_list.append(answer)
# # #         filtered_questions.append(question)
# # #         filtered_ground_truths.append(ground_truth)
# # #
# # #     except BadRequestError as e:
# # #         # 处理内容审查错误
# # #         print(f"\n内容审查警告：问题 '{question}' 因内容不合规被跳过")
# # #         print(f"错误详情：{str(e)[:200]}...")  # 截断错误信息防止输出过长
# # #         continue
# # #
# # #     except Exception as e:
# # #         # 处理其他未知错误
# # #         print(f"\n未知错误：处理问题 '{question}' 时发生异常")
# # #         print(f"错误类型：{type(e).__name__}")
# # #         print(f"错误详情：{str(e)[:200]}...")
# # #         continue
# # #
# # # # 创建过滤后的DataFrame
# # # df = pd.DataFrame({
# # #     "question": filtered_questions,
# # #     "contexts": contexts_list,
# # #     "answer": answer_list,
# # #     "ground_truth": filtered_ground_truths,
# # # })
# # #
# # # # 保存处理结果（仅包含成功处理的数据）
# # # output_path = "rag_results_2776_v3_re.csv"
# # # df.to_csv(output_path, index=False)
# # # print(f"\n成功处理 {len(filtered_questions)}/{len(question_list)} 条数据，结果已保存至 {output_path}")
# # #
# # # # 后续的评估代码需要相应调整，使用过滤后的数据
# # # if not df.empty:
# # #     rag_results = Dataset.from_pandas(df)
# # #
# # #     # 初始化评估模型（保持原有配置）
# # #     llm = Tongyi(
# # #         model="qwen-max",
# # #         api_key="sk-48d14c2089104df1a05",
# # #     )
# # #     generator_llm = LangchainLLMWrapper(llm)
# # #
# # #     qwen_embedding = DashScopeEmbeddings(
# # #         model="text-embedding-v1",
# # #         dashscope_api_key="sk-48d14c2089104df1"
# # #     )
# # #     qwen_embeddings = LangchainEmbeddingsWrapper(qwen_embedding)
# # #
# # #     # 配置评估指标
# # #     faithfulness.llm = generator_llm
# # #     answer_relevancy.llm = generator_llm
# # #     answer_relevancy.embeddings = qwen_embeddings
# # #     context_recall.llm = generator_llm
# # #     context_precision.llm = generator_llm
# # #
# # #     # 执行评估
# # #     result = evaluate(
# # #         rag_results,
# # #         metrics=[
# # #             answer_relevancy,
# # #             faithfulness,
# # #             context_recall,
# # #             context_precision,
# # #         ]
# # #     )
# # #     print(result)
# # # else:
# # #     print("警告：所有数据均处理失败，评估步骤已跳过")
# # from pymilvus import MilvusClient
# # from pymilvus import AnnSearchRequest, RRFRanker
# # from langchain_community.embeddings import DashScopeEmbeddings
# # from dashscope import Generation
# # # 创建Milvus Client。
# # client = MilvusClient(
# #     uri="http://c-xxxx.milvus.aliyuncs.com:19530",  # Milvus实例的公网地址。
# #     token="<yourUsername>:<yourPassword>",  # 登录Milvus实例的用户名和密码。
# #     db_name="default"  # 待连接的数据库名称，本文示例为默认的default。
# # )
# # collection_name = "milvus_overview"
# # # 替换为您的 DashScope API-KEY
# # dashscope_api_key = "<YOUR_DASHSCOPE_API_KEY>"
# # # 初始化 Embedding 模型
# # embeddings = DashScopeEmbeddings(
# #     model="text-embedding-v2",  # 使用text-embedding-v2模型。
# #     dashscope_api_key=dashscope_api_key
# # )
# # # Define the query
# # query = "Why does Milvus run so scalable?"
# # # Embed the query and generate the corresponding vector representation
# # query_embeddings = embeddings.embed_documents([query])
# # # Set the top K result count
# # top_k = 5  # Get the top 5 docs related to the query
# # # Define the parameters for the dense vector search
# # search_params_dense = {
# #     "metric_type": "IP",
# #     "params": {"nprobe": 2}
# # }
# # # Create a dense vector search request
# # request_dense = AnnSearchRequest([query_embeddings[0]], "dense", search_params_dense, limit=top_k)
# # # Define the parameters for the BM25 text search
# # search_params_bm25 = {
# #     "metric_type": "BM25"
# # }
# # # Create a BM25 text search request
# # request_bm25 = AnnSearchRequest([query], "sparse_bm25", search_params_bm25, limit=top_k)
# # # Combine the two requests
# # reqs = [request_dense, request_bm25]
# # # Initialize the RRF ranking algorithm
# # ranker = RRFRanker(100)
# # # Perform the hybrid search
# # hybrid_search_res = client.hybrid_search(
# #     collection_name=collection_name,
# #     reqs=reqs,
# #     ranker=ranker,
# #     limit=top_k,
# #     output_fields=["text"]
# # )
# # # Extract the context from hybrid search results
# # context = []
# # print("Top K Results:")
# # for hits in hybrid_search_res:  # Use the correct variable here
# #     for hit in hits:
# #         context.append(hit['entity']['text'])  # Extract text content to the context list
# #         print(hit['entity']['text'])  # Output each retrieved document
# # # Define a function to get an answer based on the query and context
# # def getAnswer(query, context):
# #     prompt = f'''Please answer my question based on the content within:
# #     ```
# #     {context}
# #     ```
# #     My question is: {query}.
# #     '''
# #     # Call the generation module to get an answer
# #     rsp = Generation.call(model='qwen-turbo', prompt=prompt)
# #     return rsp.output.text
# # # Get the answer
# # answer = getAnswer(query, context)
# # print(answer)
# # # Expected output excerpt
# # """
# # Milvus is highly scalable due to its cloud-native and highly decoupled system architecture. This architecture allows the system to continuously expand as data grows. Additionally, Milvus supports three deployment modes that cover a wide...
# # """
#
# # !/usr/bin/python3
# # -*- coding: utf-8 -*-
# """
# @Author         :  yaosenJ
# @Version        :  WIN10, Python3.7.9
# ------------------------------------
# @IDE            ： PyCharm
# @Description    :  增强版混合检索系统集成RAG评估
# @CreateTime     :  2024/4/16 23:01
# @UpdateTime     :  2024/4/16 23:01
# ------------------------------------
# """
# import argparse
# import logging
# from datetime import datetime
# from typing import List, Tuple
# import pandas as pd
# from tqdm import tqdm
# from datasets import Dataset
# from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker
# from langchain_community.llms import Tongyi
# from langchain_community.embeddings import DashScopeEmbeddings
# from ragas import evaluate
# from ragas.metrics import (
#     answer_relevancy,
#     faithfulness,
#     context_recall,
#     context_precision,
# )
# from ragas.llms import LangchainLLMWrapper
# from ragas.embeddings import LangchainEmbeddingsWrapper
# from dashscope import Generation
# import dashscope
#
#
# # ================= 系统配置 =================
# class Config:
#     # Milvus配置
#     MILVUS_URL = '192.168.1.227:19530'
#     MILVUS_TOKEN = "root:Milvus"
#     COLLECTION_NAME = "company_news_hybrid"
#     CONN_TIMEOUT = 30
#
#     # 检索参数
#     TOP_K = 2
#     DENSE_SEARCH_PARAMS = {
#         "metric_type": "COSINE",
#         "params": {"nprobe": 32}
#     }
#     RRF_WINDOW_SIZE = 100
#
#     # 大模型配置
#     DASHSCOPE_API_KEY = "sk-48d14c2089104df"
#     LLM_MODEL = "qwen-max"
#
#     # 评估配置
#     QA_DATA_PATH = "../data/qa_pairs_update.csv"
#     OUTPUT_PATH = "./rag_results_hybrid.csv"
#
#
# # ================= 日志配置 =================
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[logging.StreamHandler()]
# )
# logger = logging.getLogger(__name__)
#
#
# # ================= 混合检索系统核心类 =================
# class HybridSearchSystem:
#     def __init__(self):
#         self._init_milvus()
#         self._init_embeddings()
#         dashscope.api_key = Config.DASHSCOPE_API_KEY
#
#     def _init_milvus(self):
#         """初始化Milvus连接"""
#         try:
#             self.client = MilvusClient(
#                 uri=f"http://{Config.MILVUS_URL}",
#                 token=Config.MILVUS_TOKEN,
#                 db_name="default",
#                 timeout=Config.CONN_TIMEOUT
#             )
#             logger.info("Milvus客户端初始化成功")
#         except Exception as e:
#             logger.error(f"Milvus连接失败: {str(e)}")
#             raise
#
#     def _init_embeddings(self):
#         """初始化文本嵌入模型"""
#         self.embeddings = DashScopeEmbeddings(
#             model="text-embedding-v3",
#             dashscope_api_key=Config.DASHSCOPE_API_KEY
#         )
#
#     def _hybrid_search(self, query: str) -> List[dict]:
#         """执行混合检索"""
#         try:
#             # 生成向量
#             query_emb = self.embeddings.embed_query(query)
#
#             # 构建双路请求
#             dense_req = AnnSearchRequest(
#                 data=[query_emb],
#                 anns_field="dense",
#                 param=Config.DENSE_SEARCH_PARAMS,
#                 limit=Config.TOP_K * 2
#             )
#
#             sparse_req = AnnSearchRequest(
#                 data=[query],
#                 anns_field="sparse_bm25",
#                 param={"metric_type": "BM25"},
#                 limit=Config.TOP_K * 2
#             )
#
#             # 执行检索
#             results = self.client.hybrid_search(
#                 collection_name=Config.COLLECTION_NAME,
#                 reqs=[dense_req, sparse_req],
#                 ranker=RRFRanker(k=Config.RRF_WINDOW_SIZE),
#                 limit=Config.TOP_K,
#                 output_fields=["title", "content"]
#             )
#
#             # 解析结果
#             processed_results = []
#             for result_group in results:
#                 for hit in result_group:
#                     entity = hit.get("entity", {})
#                     processed_results.append({
#                         "title": entity.get("title", "无标题"),
#                         "content": entity.get("content", "")
#                     })
#             return processed_results[:Config.TOP_K]
#
#         except Exception as e:
#             logger.error(f"检索失败: {str(e)}")
#             return []
#
#     def _generate_answer(self, query: str, context: List[dict]) -> str:
#         """生成回答"""
#         try:
#             context_str = "\n".join(
#                 [f"[{i + 1}] 标题：{doc['title']}\n内容：{doc['content'][:300]}..."
#                  for i, doc in enumerate(context)]
#             )
#
#             prompt = f"""基于以下新闻数据回答问题：
#
#             {context_str}
#
#             请用中文简洁明了地回答：{query}
#             """
#
#             response = Generation.call(
#                 model=Config.LLM_MODEL,
#                 prompt=prompt,
#                 seed=42,
#                 top_p=0.8,
#                 temperature=0.3
#             )
#             return response.output.text
#         except Exception as e:
#             logger.error(f"生成回答失败: {str(e)}")
#             return "暂时无法生成回答"
#
#     def query(self, question: str) -> dict:
#         """完整查询接口"""
#         try:
#             results = self._hybrid_search(question)
#             answer = self._generate_answer(question, results)
#             return {
#                 "answer": answer,
#                 "references": results
#             }
#         except Exception as e:
#             logger.error(f"查询流程异常: {str(e)}")
#             return {"error": "服务暂时不可用"}
#
#     def query_with_context(self, question: str) -> Tuple[str, List[dict]]:
#         """获取答案和上下文（用于评估）"""
#         try:
#             results = self._hybrid_search(question)
#             answer = self._generate_answer(question, results)
#             return answer, results
#         except Exception as e:
#             logger.error(f"获取上下文失败: {str(e)}")
#             return "", []
#
#
# # ================= RAG评估功能 =================
# class RagEvaluator:
#     def __init__(self):
#         self.system = HybridSearchSystem()
#         self._init_metrics()
#
#     def _init_metrics(self):
#         """初始化评估指标"""
#         # 大语言模型
#         llm = Tongyi(
#             model=Config.LLM_MODEL,
#             api_key=Config.DASHSCOPE_API_KEY
#         )
#         self.generator_llm = LangchainLLMWrapper(llm)
#
#         # 嵌入模型
#         qwen_embedding = DashScopeEmbeddings(
#             model="text-embedding-v3",
#             dashscope_api_key=Config.DASHSCOPE_API_KEY
#         )
#         self.qwen_embeddings = LangchainEmbeddingsWrapper(qwen_embedding)
#
#         # 配置评估指标
#         faithfulness.llm = self.generator_llm
#         answer_relevancy.llm = self.generator_llm
#         answer_relevancy.embeddings = self.qwen_embeddings
#         context_recall.llm = self.generator_llm
#         context_precision.llm = self.generator_llm
#
#     def process_qa_data(self, csv_path: str) -> Dataset:
#         """处理QA数据并生成评估数据集"""
#         df_input = pd.read_csv(csv_path, encoding='gbk')
#         question_list = df_input["question"].tolist()
#         ground_truth_list = df_input["answer"].tolist()
#
#         filtered_questions = []
#         filtered_ground_truths = []
#         contexts_list = []
#         answer_list = []
#
#         for q, gt in tqdm(zip(question_list, ground_truth_list),
#                           total=len(question_list),
#                           desc="处理QA数据"):
#             try:
#                 answer, contexts = self.system.query_with_context(q)
#                 if not answer or not contexts:
#                     continue
#
#                 # 格式化上下文
#                 text_contexts = [
#                     f"标题：{ctx['title']}\n内容：{ctx['content']}"
#                     for ctx in contexts
#                 ]
#
#                 contexts_list.append(text_contexts)
#                 answer_list.append(answer)
#                 filtered_questions.append(q)
#                 filtered_ground_truths.append(gt)
#             except Exception as e:
#                 logger.error(f"处理问题失败: {q}, 错误: {str(e)[:200]}...")
#                 continue
#
#         df = pd.DataFrame({
#             "question": filtered_questions,
#             "contexts": contexts_list,
#             "answer": answer_list,
#             "ground_truth": filtered_ground_truths,
#         })
#         return Dataset.from_pandas(df)
#
#     def evaluate(self, dataset: Dataset) -> dict:
#         """执行评估并返回结果"""
#         if len(dataset) == 0:
#             logger.warning("没有有效数据可供评估")
#             return {}
#
#         result = evaluate(
#             dataset,
#             metrics=[
#                 answer_relevancy,
#                 faithfulness,
#                 context_recall,
#                 context_precision,
#             ]
#         )
#         return result
#
#
# # ================= 命令行接口 =================
# def main():
#     parser = argparse.ArgumentParser(description="混合检索系统")
#     parser.add_argument('--evaluate', action='store_true', help='执行RAG评估')
#     parser.add_argument('--data', default=Config.QA_DATA_PATH, help='QA数据路径')
#     parser.add_argument('--output', default=Config.OUTPUT_PATH, help='评估结果路径')
#     args = parser.parse_args()
#
#     if args.evaluate:
#         logger.info("启动RAG评估流程...")
#         evaluator = RagEvaluator()
#
#         # 处理数据
#         dataset = evaluator.process_qa_data(args.data)
#
#         # 保存中间结果
#         dataset.to_pandas().to_csv(args.output, index=False)
#         logger.info(f"中间结果已保存至 {args.output}")
#
#         # 执行评估
#         if len(dataset) > 0:
#             result = evaluator.evaluate(dataset)
#             logger.info("\n评估结果:")
#             print(result)
#         else:
#             logger.warning("没有有效数据可供评估")
#     else:
#         # 示例查询
#         system = HybridSearchSystem()
#         question = "特斯拉第一季度的交付量是多少？"
#         response = system.query(question)
#
#         print("\n===== 生成回答 =====")
#         print(response["answer"])
#
#         print("\n===== 参考来源 =====")
#         for ref in response["references"]:
#             print(f"{ref['title']}")
#             print(ref["content"][:200] + "...\n")
#
#
# if __name__ == "__main__":
#     main()


# !/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@Author         :  yaosenJ
@Version        :  WIN10, Python3.7.9
------------------------------------
@IDE            ： PyCharm
@Description    :  增强版混合检索系统集成RAG评估
@CreateTime     :  2024/4/16 23:01
@UpdateTime     :  2024/4/16 23:01
------------------------------------
"""
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


# ================= 系统配置 =================
class Config:
    # Milvus配置
    MILVUS_URL = '192.168.1.227:19530'
    MILVUS_TOKEN = "root:Milvus"
    COLLECTION_NAME = "company_news_hybrid"
    CONN_TIMEOUT = 30

    # 检索参数
    TOP_K = 2
    DENSE_SEARCH_PARAMS = {
        "metric_type": "COSINE",
        "params": {"nprobe": 32}
    }
    RRF_WINDOW_SIZE = 100

    # 大模型配置
    DASHSCOPE_API_KEY = "sk-48d14c2089104df1"
    LLM_MODEL = "qwen-max"

    # 评估配置
    # QA_DATA_PATH = "../data/qa_pairs_update.csv"
    # OUTPUT_PATH = "../data/qa_pairs_update/rag_results_hybrid.csv"

    QA_DATA_PATH = "../data/qa_pairs.csv"
    OUTPUT_PATH = "../data/qa_pairs/rag_results_hybrid.csv"


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
            context_str = "\n".join(
                [f"[{i + 1}] 标题：{doc['title']}\n内容：{doc['content'][:300]}..."
                 for i, doc in enumerate(context)]
            )

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
            results = self._hybrid_search(question)
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
        df_input = pd.read_csv(csv_path, encoding='gbk')
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

                # 格式化上下文
                text_contexts = [
                    f"标题：{ctx['title']}\n内容：{ctx['content']}"
                    for ctx in contexts
                ]

                contexts_list.append(text_contexts)
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
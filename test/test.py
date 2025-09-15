# !/usr/bin/python3
# -*- coding: utf-8 -*-
import pandas as pd
from datasets import Dataset
import ast  # 添加这个库用于安全解析字符串列表
# 读取 CSV 时转换 contexts 列
df = pd.read_csv(
    "../data/qa_pairs_update/rag_results_hybrid.csv",
    converters={
        "contexts": lambda x: ast.literal_eval(x)  # 将字符串转换为列表
    }
)
rag_results = Dataset.from_pandas(df)
# print(rag_results)

from ragas import evaluate

from ragas.llms import LangchainLLMWrapper



from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
)


from langchain_community.llms import Tongyi

llm = Tongyi(
    model="qwen-max",
    # top_p="...",
    api_key="sk-48d14c208",
    # other params...
)
generator_llm = LangchainLLMWrapper(llm)


from langchain_community.embeddings import DashScopeEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper


qwen_embedding = DashScopeEmbeddings(
    model="text-embedding-v1", dashscope_api_key="sk-48d14c2089104"
)

qwen_embeddings= LangchainEmbeddingsWrapper(qwen_embedding)
faithfulness.llm = generator_llm
answer_relevancy.llm = generator_llm
answer_relevancy.embeddings = qwen_embeddings
context_recall.llm = generator_llm
context_precision.llm = generator_llm
result = evaluate(
    rag_results,
    metrics=[
        answer_relevancy,
        faithfulness,
        context_recall,
        context_precision,
    ]
)
print(result)
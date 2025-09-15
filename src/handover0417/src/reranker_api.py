# !/usr/bin/python3
# -*- coding: utf-8 -*-
# 安装依赖
# pip install fastapi uvicorn transformers

# 创建服务文件 rerank_api.py
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

app = FastAPI()

model = AutoModelForSequenceClassification.from_pretrained(
    "/home/km_gpu_2/code/model/BAAI/bge-reranker-large",
    torch_dtype=torch.float16,
    device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained(
    "/home/km_gpu_2/code/model/BAAI/bge-reranker-large"
)


class RequestData(BaseModel):
    query: str
    documents: list[str]
    top_n: int = 10


@app.post("/rerank")
async def rerank(data: RequestData):
    pairs = [[data.query, doc] for doc in data.documents]
    inputs = tokenizer(
        pairs,
        padding=True,
        truncation=True,
        return_tensors="pt",
        max_length=512
    ).to(model.device)

    with torch.no_grad():
        outputs = model(**inputs)
        scores = outputs.logits[:, 0].float()

    sorted_docs = sorted(
        zip(data.documents, scores.tolist()),
        key=lambda x: x[1],
        reverse=True
    )[:data.top_n]

    return {
        "results": [
            {"document": doc, "score": score}
            for doc, score in sorted_docs
        ]
    }



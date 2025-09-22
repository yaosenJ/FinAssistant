from fastapi import APIRouter, Depends, Query
from typing import List, Literal

from .deps import get_current_username

router = APIRouter(prefix="/features", tags=["features"]) 

@router.get("/research")
def research(query: str, mode: Literal['vector','hybrid','rerank']='hybrid', _u: str = Depends(get_current_username)):
    # TODO: integrate with real retrieval pipelines (Milvus/MySQL)
    import random
    return [{
        "title": f"{mode.upper()} · 结果 {i+1}",
        "snippet": f"{query} · 相关检索摘要片段（演示占位）",
        "date": "2025-09-22",
        "source": "FinNews",
        "score": random.random()
    } for i in range(5)]

@router.get("/stocks/diagnosis")
def stock_diagnosis(code: str = Query(..., description="股票代码，如 600519"), _u: str = Depends(get_current_username)):
    # TODO: join fundamentals, sentiment, technical factors
    return {
        "code": code,
        "rating": "A-",
        "summary": "盈利能力稳健，行业景气度较高，短期波动风险可控。",
        "factors": {
            "valuation": "合理偏高",
            "growth": "稳健",
            "profitability": "强",
            "risk": "中低"
        }
    }

@router.get("/indices/overview")
def indices_overview(kind: Literal['industry','concept']='industry', _u: str = Depends(get_current_username)):
    # TODO: aggregate index constituents and trends
    sample = [
        {"name": "半导体", "change": 1.23, "leaders": ["韦尔股份", "兆易创新"]},
        {"name": "新能源", "change": -0.45, "leaders": ["宁德时代", "阳光电源"]},
        {"name": "消费电子", "change": 0.78, "leaders": ["立讯精密", "歌尔股份"]}
    ]
    return {"kind": kind, "items": sample}

@router.get("/qa")
def fin_qa(question: str, _u: str = Depends(get_current_username)):
    # TODO: integrate with LLM and knowledge sources
    return {
        "question": question,
        "answer": "这是基于金融常识与示例知识库的解答（演示）。",
        "sources": [
            {"title": "证券投资学", "url": "https://example.com/book"},
            {"title": "行业研究报告", "url": "https://example.com/report"}
        ]
    }

@router.get("/news")
def news(query: str = "", limit: int = 10, _u: str = Depends(get_current_username)):
    # TODO: fetch from MySQL and rerank via embedding
    return [{
        "title": f"{query or '市场'} 动态 {i+1}",
        "date": "2025-09-22",
        "source": "FinWire",
        "summary": "新闻摘要占位，用于展示资讯查询解读能力。"
    } for i in range(limit)]

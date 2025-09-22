from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal

from .deps import get_current_username
from ..services.news_recall import NewsRecallService

router = APIRouter(prefix="/news", tags=["news"]) 
service = None

@router.on_event("startup")
def _init():
    global service
    try:
        service = NewsRecallService()
    except Exception as e:
        # 延迟失败，首次请求时再尝试
        service = None

@router.get("/recall")
async def news_recall(query: str, mode: Literal['vector','bm25','hybrid']='hybrid', limit: int = 20, _u: str = Depends(get_current_username)):
    global service
    if service is None:
        service = NewsRecallService()
    if mode == 'vector':
        return await service.vector_recall(query, limit)
    if mode == 'bm25':
        return await service.bm25_recall(query, limit)
    return await service.hybrid_recall(query, limit)

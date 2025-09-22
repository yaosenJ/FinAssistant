from typing import List, Dict, Any
from .config_loader import load_config
from .mysql_client import MySQLClient
from .milvus_client import MilvusClient
from .embedding import QwenEmbedding
from .bm25 import BM25Lite
import asyncio

class NewsRecallService:
    def __init__(self):
        cfg = load_config()
        self.mysql = MySQLClient(
            host=cfg.mysql.get('host','localhost'),
            port=int(cfg.mysql.get('port',3306)),
            user=cfg.mysql.get('user','root'),
            password=cfg.mysql.get('password',''),
            database=cfg.mysql.get('database','')
        )
        self.milvus = MilvusClient(
            host=cfg.milvus.get('host','localhost'),
            port=int(cfg.milvus.get('port',19530)),
            collection_name=cfg.milvus.get('collection_name','company_news_final')
        )
        self.embedder = QwenEmbedding(
            api_key=cfg.qwen.get('api_key',''),
            base_url=cfg.qwen.get('base_url','https://dashscope.aliyuncs.com/compatible-mode/v1'),
            model=cfg.qwen.get('embedding_model','text-embedding-v3')
        )

    async def vector_recall(self, query: str, limit: int = 20) -> List[Dict[str,Any]]:
        emb = await self.embedder.embed(query)
        return self.milvus.vector_search(emb, limit=limit)

    async def bm25_recall(self, query: str, limit: int = 20) -> List[Dict[str,Any]]:
        # 从 MySQL 拉最近新闻做关键词召回
        rows = self.mysql.fetch_news(query="", limit=500)
        docs = [f"{r['title']} {r['content'] or ''}" for r in rows]
        bm25 = BM25Lite(docs)
        scores = bm25.score(query)
        ranked = sorted(zip(rows, scores), key=lambda x: x[1], reverse=True)[:limit]
        out = []
        for r, s in ranked:
            out.append({
                "id": r["id"],
                "title": r["title"],
                "content": r["content"],
                "trade_date": r["trade_date"],
                "source": r.get("source",""),
                "score": float(s)
            })
        return out

    async def hybrid_recall(self, query: str, limit: int = 20) -> List[Dict[str,Any]]:
        vec_task = asyncio.create_task(self.vector_recall(query, limit))
        kw_task = asyncio.create_task(self.bm25_recall(query, limit))
        vec, kw = await asyncio.gather(vec_task, kw_task)
        # 归一化 + 融合（简单示例）
        def norm(scores):
            if not scores: return []
            vals = [x['score'] for x in scores]
            mn, mx = min(vals), max(vals)
            return [0.0 if mx==mn else (v-mn)/(mx-mn) for v in vals]
        v_norm = norm(vec)
        k_norm = norm(kw)
        for i, x in enumerate(vec): x['hybrid'] = 0.6*(1 - v_norm[i])  # COSINE 距离转相关度
        for i, x in enumerate(kw): x['hybrid'] = 0.4*k_norm[i]
        merged = { (x.get('id'), x.get('title')): x for x in vec }
        for y in kw:
            key = (y.get('id'), y.get('title'))
            if key in merged:
                merged[key]['hybrid'] = max(merged[key]['hybrid'], y['hybrid'])
            else:
                merged[key] = y
        out = sorted(merged.values(), key=lambda z: z['hybrid'], reverse=True)[:limit]
        return out

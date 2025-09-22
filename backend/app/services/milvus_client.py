from typing import List, Dict, Any
from pymilvus import connections, Collection, DataType

class MilvusClient:
    def __init__(self, host: str, port: int, collection_name: str):
        self.alias = "default"
        connections.connect(self.alias, host=host, port=str(port))
        self.collection = Collection(collection_name)
        # Auto-detect vector field and output fields
        self.vector_field_name = None
        self.output_fields = []
        for f in self.collection.schema.fields:
            if f.dtype == DataType.FLOAT_VECTOR or f.dtype == DataType.BFLOAT16_VECTOR:
                self.vector_field_name = f.name
            else:
                self.output_fields.append(f.name)
        if not self.vector_field_name:
            # Fallback to common name
            self.vector_field_name = "embedding"
        # Prefer common useful fields order if present
        preferred = ["id", "title", "content", "trade_date", "source"]
        ordered = [p for p in preferred if p in self.output_fields]
        rest = [f for f in self.output_fields if f not in ordered]
        self.output_fields = ordered + rest

    def vector_search(self, embedding: List[float], limit: int = 20, metric_type: str = "COSINE", nprobe: int = 128) -> List[Dict[str, Any]]:
        res = self.collection.search(
            data=[embedding],
            anns_field=self.vector_field_name,
            param={"metric_type": metric_type, "params": {"nprobe": nprobe}},
            limit=limit,
            output_fields=self.output_fields
        )
        hits = res[0]
        out = []
        for h in hits:
            ent = h.entity
            item: Dict[str, Any] = {"score": float(h.distance)}
            for f in self.output_fields:
                item[f] = ent.get(f)
            # Normalize common aliases
            if "trade_date" in item and item["trade_date"] is not None:
                item["trade_date"] = str(item["trade_date"])
            out.append(item)
        return out

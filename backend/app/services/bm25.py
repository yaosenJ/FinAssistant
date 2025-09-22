from typing import List, Dict, Any
import math
from collections import Counter

# 轻量 BM25 演示版：用于关键词召回

class BM25Lite:
    def __init__(self, docs: List[str], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.avgdl = sum(len(d.split()) for d in docs) / (len(docs) or 1)
        self.doc_freq = Counter()
        self.doc_terms = []
        for d in docs:
            terms = d.split()
            self.doc_terms.append(Counter(terms))
            self.doc_freq.update(set(terms))
        self.N = len(docs)

    def idf(self, term: str) -> float:
        n = self.doc_freq.get(term, 0) + 1
        return math.log((self.N - n + 0.5) / (n + 0.5) + 1)

    def score(self, query: str) -> List[float]:
        q_terms = query.split()
        scores = []
        for i, terms in enumerate(self.doc_terms):
            dl = sum(terms.values())
            s = 0.0
            for t in q_terms:
                tf = terms.get(t, 0)
                if tf == 0:
                    continue
                idf = self.idf(t)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                s += idf * (tf * (self.k1 + 1)) / (denom or 1)
            scores.append(s)
        return scores

"""
knowledge_base.py
-----------------
Chhoto RAG knowledge base (data/knowledge_base.json). Retrieval = keyword overlap score
(title ko match 2x weight). Real project ma embeddings/vector DB use garne, yaha demo ko lagi simple.
(Bank ra tyo ko rates sabai FICTIONAL ho.)
"""
import json
from pathlib import Path
from .text_utils import content_tokens

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"


class KnowledgeBase:
    def __init__(self, path=DEFAULT_PATH):
        self.docs = json.loads(Path(path).read_text(encoding="utf-8"))
        self._by_id = {d["id"]: d for d in self.docs}
        self._tokens = {d["id"]: (content_tokens(d["title"]), content_tokens(d["text"])) for d in self.docs}

    def get(self, doc_id: str) -> dict:
        return self._by_id[doc_id]

    def retrieve(self, query: str, k: int = 2, min_score: int = 3) -> list:
        """Query sanga milne top-k docs. min_score bhanda kam bhayo bhane [] (out-of-scope)."""
        q = content_tokens(query)
        scored = []
        for d in self.docs:
            title_t, text_t = self._tokens[d["id"]]
            score = 2 * len(q & title_t) + len(q & text_t)
            if score >= min_score:
                scored.append((score, d))
        scored.sort(key=lambda x: -x[0])
        return [d for _, d in scored[:k]]

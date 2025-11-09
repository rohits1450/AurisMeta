

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
import threading
import json
import os

class SimpleRAGIndex:
    def __init__(self):
        self.lock = threading.Lock()
        self.docs = []           
        self.ids = []
        self.vectorizer = None
        self.matrix = None

    def add_documents(self, doc_list):
        """
        doc_list: list of dicts {"id": str, "text": str, "meta": {...}}
        Adds/updates documents; rebuilds index (cheap for small sets).
        """
        with self.lock:
            existing = {d["id"]: i for i, d in enumerate(self.docs)}
            for d in doc_list:
                if d["id"] in existing:
                    self.docs[existing[d["id"]]] = d
                else:
                    self.docs.append(d)

            texts = [d["text"] for d in self.docs]
            if texts:
                
                self.vectorizer = TfidfVectorizer(ngram_range=(1,2), max_features=2048)
                self.matrix = self.vectorizer.fit_transform(texts)
                self.ids = [d["id"] for d in self.docs]
            else:
                self.vectorizer = None
                self.matrix = None
                self.ids = []

    def retrieve(self, query, top_k=5):
        """
        Return top_k docs: list of dicts with id,text,meta,score
        """
        with self.lock:
            if self.matrix is None or self.vectorizer is None:
                return []
            qv = self.vectorizer.transform([query])
            scores = linear_kernel(qv, self.matrix)[0]
            ranked_idx = scores.argsort()[::-1][:top_k]
            results = []
            for idx in ranked_idx:
                results.append({
                    "id": self.docs[idx]["id"],
                    "text": self.docs[idx]["text"],
                    "meta": self.docs[idx].get("meta", {}),
                    "score": float(scores[idx])
                })
            return results

    def dump(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.docs, f, indent=2)

    def load(self, path):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                docs = json.load(f)
            self.add_documents(docs)
        except Exception:
            pass

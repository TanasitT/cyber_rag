from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from scipy import sparse

from .chunking import Chunk
from .thai import tokenize


class VectorIndex:
    """
    Minimal local "vector DB":
      - TF-IDF vectorizer (keyword search; Thai is split into words by scripts.thai.tokenize)
      - sparse matrix of chunk vectors
      - metadata + chunk texts
    """

    def __init__(self, vectorizer: TfidfVectorizer, matrix: sparse.csr_matrix, chunks: List[Chunk]):
        self.vectorizer = vectorizer
        self.matrix = normalize(matrix)  # cosine similarity via dot product
        self.chunks = chunks

    @staticmethod
    def build(chunks: List[Chunk]) -> "VectorIndex":
        texts = [c.text for c in chunks]
        vectorizer = TfidfVectorizer(
            lowercase=True,
            tokenizer=tokenize,  # also drops English + Thai stop words
            token_pattern=None,
            ngram_range=(1, 2),
            max_features=200_000,
        )
        matrix = vectorizer.fit_transform(texts)
        return VectorIndex(vectorizer, matrix, chunks)

    def save(self, index_dir: str | Path) -> None:
        index_dir = Path(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)

        # Save vectorizer
        import pickle
        with open(index_dir / "tfidf_vectorizer.pkl", "wb") as f:
            pickle.dump(self.vectorizer, f)

        # Save matrix
        sparse.save_npz(index_dir / "chunk_matrix.npz", self.matrix)

        # Save metadata + text
        meta_path = index_dir / "chunk_metadata.jsonl"
        with open(meta_path, "w", encoding="utf-8") as f:
            for c in self.chunks:
                record = {
                    "doc_id": c.doc_id,
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "page": getattr(c, "page", None),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def load(index_dir: str | Path) -> "VectorIndex":
        index_dir = Path(index_dir)
        import pickle

        with open(index_dir / "tfidf_vectorizer.pkl", "rb") as f:
            vectorizer: TfidfVectorizer = pickle.load(f)

        matrix = sparse.load_npz(index_dir / "chunk_matrix.npz")

        chunks: List[Chunk] = []
        with open(index_dir / "chunk_metadata.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                chunks.append(
                    Chunk(
                        doc_id=r["doc_id"],
                        chunk_id=r["chunk_id"],
                        text=r["text"],
                        page=int(r.get("page", -1)),
                    )
                )
        return VectorIndex(vectorizer, matrix, chunks)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        q_vec = self.vectorizer.transform([query])
        q_vec = normalize(q_vec)
        # cosine sim = dot product because both normalized
        scores = (self.matrix @ q_vec.T).toarray().ravel()
        if scores.size == 0:
            return []

        top_idx = np.argsort(-scores)[:top_k]
        results = [(self.chunks[i], float(scores[i])) for i in top_idx]
        # filter zero-score results
        results = [(c, s) for (c, s) in results if s > 0.0]
        return results

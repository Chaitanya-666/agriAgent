"""
src/agronomy/knowledge_store.py
Track 2 / Task 2.2: ChromaDB vector store for ICAR & CIBRC weed-management documents.

Usage:
    python -m src.agronomy.knowledge_store --ingest          # index data/knowledge_base/*
    python -m src.agronomy.knowledge_store --query "Parthenium control in cotton"

Embeddings:
    - default : sentence-transformers 'BAAI/bge-small-en-v1.5' (needs internet once to download)
    - "hash"  : offline, deterministic bag-of-words hashing (used by unit tests / CPU-only CI)
"""
import argparse
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import chromadb
    EmbeddingFunction = chromadb.EmbeddingFunction
except ImportError:
    chromadb = None
    EmbeddingFunction = object

KB_DIR = Path("data/knowledge_base")
DB_DIR = "data/chroma_db"
COLLECTION = "icar_cibrc"
DIM = 384


class HashEmbedding(EmbeddingFunction):
    """Offline fallback embedder: hashed bag-of-words, L2-normalised. Good enough for tests."""

    def __init__(self, dim: int = DIM):
        self.dim = dim

    def __call__(self, input):  # noqa: A002 (chromadb signature)
        out = []
        for text in input:
            v = [0.0] * self.dim
            for tok in re.findall(r"[a-z0-9]+", text.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % self.dim] += 1.0
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out

    @staticmethod
    def name() -> str:
        return "agri_hash_embedding"

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self.dim}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "HashEmbedding":
        return HashEmbedding(config.get("dim", DIM))


def _embedder(embedding: str):
    if embedding == "hash":
        return HashEmbedding()
    from chromadb.utils import embedding_functions
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-small-en-v1.5")


class KnowledgeStore:
    def __init__(self, db_dir: str = DB_DIR, embedding: str = "bge"):
        if chromadb is None:
            raise ImportError(
                "chromadb is required to use KnowledgeStore. Install it with `pip install chromadb`."
            )
        self.client = chromadb.PersistentClient(path=db_dir)
        self.col = self.client.get_or_create_collection(COLLECTION, embedding_function=_embedder(embedding))

    @staticmethod
    def _chunks(text: str, size: int = 900, overlap: int = 150):
        text = re.sub(r"\s+", " ", text).strip()
        step = size - overlap
        for i in range(0, len(text), step):
            piece = text[i:i + size]
            if len(piece) > 40:
                yield piece

    @staticmethod
    def _read(path: Path) -> List[str]:
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
        if path.suffix.lower() in (".txt", ".md"):
            return [path.read_text(encoding="utf-8", errors="ignore")]
        return []

    def ingest(self, kb_dir: Path = KB_DIR, authority: Optional[str] = None) -> int:
        """Index every PDF/TXT/MD under kb_dir. Idempotent (upsert). Returns chunk count."""
        n = 0
        for f in sorted(Path(kb_dir).rglob("*")):
            pages = self._read(f) if f.is_file() else []
            auth = authority or ("CIBRC" if "cib" in f.name.lower() else "ICAR" if "icar" in f.name.lower() else "OTHER")
            for pi, page in enumerate(pages):
                for ci, chunk in enumerate(self._chunks(page)):
                    self.col.upsert(
                        ids=[f"{f.stem}-p{pi}-c{ci}"],
                        documents=[chunk],
                        metadatas=[{"source": f.name, "page": pi + 1, "authority": auth}],
                    )
                    n += 1
        return n

    def query(self, q: str, k: int = 4) -> List[Dict[str, Any]]:
        if self.col.count() == 0:
            return []
        r = self.col.query(query_texts=[q], n_results=min(k, self.col.count()))
        return [
            {"text": d, "distance": dist, **m}
            for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
        ]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--query", type=str)
    ap.add_argument("--hash", action="store_true", help="use offline hash embeddings")
    a = ap.parse_args()
    ks = KnowledgeStore(embedding="hash" if a.hash else "bge")
    if a.ingest:
        print(f"Indexed {ks.ingest()} chunks")
    if a.query:
        for h in ks.query(a.query):
            print(f"[{h['authority']} | {h['source']} p.{h['page']}] {h['text'][:200]}...")

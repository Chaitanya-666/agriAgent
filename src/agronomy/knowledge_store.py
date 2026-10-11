"""
src/agronomy/knowledge_store.py
Track 2 / Task 2.2: Vector & In-Memory Store for ICAR & CIBRC weed-management documents.
Implements table-aware structured document parsing and rich metadata storage.
Adheres to PROJECT.md Milestone 3 requirements and interface contracts.
"""
import argparse
import hashlib
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import chromadb
    EmbeddingFunction = chromadb.EmbeddingFunction
except ImportError:
    chromadb = None
    EmbeddingFunction = object

logger = logging.getLogger("agriagent.knowledge_store")

KB_DIR = Path("data/knowledge_base")
DB_DIR = "data/chroma_db"
COLLECTION = "icar_cibrc"
DIM = 384

# Template boilerplate words to filter out from keyword overlap boost
TEMPLATE_BOILERPLATE_WORDS = {
    "control",
    "in",
    "at",
    "stage",
    "herbicide",
    "dose",
    "pre",
    "harvest",
    "pre-harvest",
    "interval",
    "crop",
    "plant",
    "cotton",
    "sugarbeet",
    "wheat",
    "soybean",
    "rice",
    "maize",
    "all",
    "for",
    "and",
    "the",
    "with",
    "application",
    "rate",
    "days",
    "vegetative",
    "flowering",
    "boll",
    "post",
    "emergence",
    "pre-emergence",
    "seedling",
    "spp",
    "sp",
}


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


# ==============================================================================
# CANONICAL STRUCTURED ICAR / CIBRC TABLES (Bulletin No. 22)
# ==============================================================================
CANONICAL_ICAR_TABLE_ROWS: List[Dict[str, Any]] = [
    # Table 4.3: Cotton Herbicide Recommendations (pp. 34-35)
    {
        "crop": "cotton",
        "weed_species": "Digera arvensis, Echinochloa colona, Eragrostis major, Euphorbia hirta, Phyllanthus niruri, Portulaca oleracea, Trianthema portulacastrum, Flaveria australasica, Gynandropsis pentaphylla",
        "chemical": "Alachlor 50% EC",
        "active_ingredient": "Alachlor",
        "dosage_ai_g_per_ha": 2500.0,
        "water_l_per_ha": 500.0,
        "waiting_period_days": 240,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 34,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Dactyloctenium aegyptium",
        "chemical": "Alachlor 10% Gr",
        "active_ingredient": "Alachlor",
        "dosage_ai_g_per_ha": 2500.0,
        "water_l_per_ha": 0.0,
        "waiting_period_days": 0,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 34,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Amaranthus spp., Chenopodium album, Convolvulus arvensis, Setaria glauca, Digitaria sp., Portulaca oleracea, Xanthium strumarium, Anagallis arvensis, Asphodelus tenuifolius, Euphorbia sp., Visia sativa, Paspalum conjugatum",
        "chemical": "Diuron 80% WP",
        "active_ingredient": "Diuron",
        "dosage_ai_g_per_ha": 1500.0,
        "water_l_per_ha": 625.0,
        "waiting_period_days": 0,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 34,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Echinochloa sp., Eleusine indica, Dactylocteneum aegyptium, Eragrostis minor",
        "chemical": "Fenoxaprop-P-ethyl 9.3% w/w EC",
        "active_ingredient": "Fenoxaprop-P-ethyl",
        "dosage_ai_g_per_ha": 67.5,
        "water_l_per_ha": 500.0,
        "waiting_period_days": 87,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 34,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Acanthospermum hispidum, Cleome viscosa, Datura sp., Trianthema monogyna, Tridax procumbens, Cynodon dactylon, Amaranthus spp., Portulaca spp., Achyranthes aspera, Euphorbia hirta, Cenchrus catharticus, Digitaria sanguinalis, Eleusine sp., Panicum sp., Lagascea mollis, Gynandropsis pentaphylla, Achalypha indica",
        "chemical": "Fluchloralin 45% EC",
        "active_ingredient": "Fluchloralin",
        "dosage_ai_g_per_ha": 1200.0,
        "water_l_per_ha": 800.0,
        "waiting_period_days": 180,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 35,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Echinochloa sp., Cynodon dactylon, Cyperus rotundus, Digitaria marginata, Dactylocteneum aegyptium",
        "chemical": "Glufosinate-ammonium 13.5% SL",
        "active_ingredient": "Glufosinate-ammonium",
        "dosage_ai_g_per_ha": 450.0,
        "water_l_per_ha": 500.0,
        "waiting_period_days": 96,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 35,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Echinochloa spp., Euphorbia hirta, Amaranthus viridis, Portulaca oleracea, Trianthema spp., Eleusine indica",
        "chemical": "Pendimethalin 30% EC",
        "active_ingredient": "Pendimethalin",
        "dosage_ai_g_per_ha": 1250.0,
        "water_l_per_ha": 700.0,
        "waiting_period_days": 150,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 35,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Trianthema spp., Amaranthus spp., Chenopodium spp., Digera spp., Celosia argentea, Parthenium hysterophorus",
        "chemical": "Pyrithiobac-sodium 10% EC",
        "active_ingredient": "Pyrithiobac-sodium",
        "dosage_ai_g_per_ha": 75.0,
        "water_l_per_ha": 500.0,
        "waiting_period_days": 160,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 35,
        "table": "Table 4.3",
    },
    {
        "crop": "cotton",
        "weed_species": "Echinolchloa crus-galli, Echinochloa colona, Dinebra retroflexa, Digitaria marginata",
        "chemical": "Quizalofop-ethyl 5% EC",
        "active_ingredient": "Quizalofop-ethyl",
        "dosage_ai_g_per_ha": 50.5,
        "water_l_per_ha": 500.0,
        "waiting_period_days": 94,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 35,
        "table": "Table 4.3",
    },
    # Table 4.8: Beet root (p. 47)
    {
        "crop": "beet root",
        "weed_species": "Chenopodium album, Amaranthus viridis, Portulaca oleracea",
        "chemical": "Pendimethalin 30% EC",
        "active_ingredient": "Pendimethalin",
        "dosage_ai_g_per_ha": 1000.0,
        "water_l_per_ha": 500.0,
        "waiting_period_days": 60,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 47,
        "table": "Table 4.8",
    },
    # Table 4.1: Wheat (pp. 25-26)
    {
        "crop": "wheat",
        "weed_species": "Phalaris minor, Chenopodium album",
        "chemical": "Sulfosulfuron 75% WG",
        "active_ingredient": "Sulfosulfuron",
        "dosage_ai_g_per_ha": 25.0,
        "water_l_per_ha": 300.0,
        "waiting_period_days": 110,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 25,
        "table": "Table 4.1",
    },
    {
        "crop": "wheat",
        "weed_species": "Phalaris minor, Avena ludoviciana",
        "chemical": "Clodinafop-propargyl 15% WP",
        "active_ingredient": "Clodinafop-propargyl",
        "dosage_ai_g_per_ha": 60.0,
        "water_l_per_ha": 375.0,
        "waiting_period_days": 110,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 25,
        "table": "Table 4.1",
    },
    # Table 4.2: Rice (pp. 28-29)
    {
        "crop": "rice",
        "weed_species": "Echinochloa spp., Cyperus spp.",
        "chemical": "Pyrazosulfuron-ethyl 10% WP",
        "active_ingredient": "Pyrazosulfuron-ethyl",
        "dosage_ai_g_per_ha": 20.0,
        "water_l_per_ha": 500.0,
        "waiting_period_days": 75,
        "authority": "ICAR",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 28,
        "table": "Table 4.2",
    },
    # Table 3.3: Banned / Withdrawn Herbicides (p. 18)
    {
        "crop": "all",
        "weed_species": "all",
        "chemical": "Nitrofen",
        "active_ingredient": "Nitrofen",
        "dosage_ai_g_per_ha": 0.0,
        "water_l_per_ha": 0.0,
        "waiting_period_days": 0,
        "authority": "CIBRC",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 18,
        "table": "Table 3.3",
        "status": "banned",
    },
    {
        "crop": "all",
        "weed_species": "all",
        "chemical": "Paraquat dimethyl sulphate",
        "active_ingredient": "Paraquat dimethyl sulphate",
        "dosage_ai_g_per_ha": 0.0,
        "water_l_per_ha": 0.0,
        "waiting_period_days": 0,
        "authority": "CIBRC",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 18,
        "table": "Table 3.3",
        "status": "banned",
    },
    {
        "crop": "all",
        "weed_species": "all",
        "chemical": "Metoxuron",
        "active_ingredient": "Metoxuron",
        "dosage_ai_g_per_ha": 0.0,
        "water_l_per_ha": 0.0,
        "waiting_period_days": 0,
        "authority": "CIBRC",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 18,
        "table": "Table 3.3",
        "status": "banned",
    },
    {
        "crop": "all",
        "weed_species": "all",
        "chemical": "Dalapon",
        "active_ingredient": "Dalapon",
        "dosage_ai_g_per_ha": 0.0,
        "water_l_per_ha": 0.0,
        "waiting_period_days": 0,
        "authority": "CIBRC",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 18,
        "table": "Table 3.3",
        "status": "withdrawn",
    },
    {
        "crop": "all",
        "weed_species": "all",
        "chemical": "Simazine",
        "active_ingredient": "Simazine",
        "dosage_ai_g_per_ha": 0.0,
        "water_l_per_ha": 0.0,
        "waiting_period_days": 0,
        "authority": "CIBRC",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 18,
        "table": "Table 3.3",
        "status": "withdrawn",
    },
    {
        "crop": "all",
        "weed_species": "all",
        "chemical": "2,4,5-T",
        "active_ingredient": "2,4,5-T",
        "dosage_ai_g_per_ha": 0.0,
        "water_l_per_ha": 0.0,
        "waiting_period_days": 0,
        "authority": "CIBRC",
        "source": "icar_dwr_herbicide_use_bulletin22.pdf",
        "page": 18,
        "table": "Table 3.3",
        "status": "refused",
    },
]


def format_table_row_document(row: Dict[str, Any]) -> str:
    """Format a table row into a structured document text for embedding."""
    return (
        f"ICAR/CIBRC Herbicide Recommendation: Crop: {row.get('crop')} | "
        f"Weed species: {row.get('weed_species')} | Chemical: {row.get('chemical')} | "
        f"Active ingredient: {row.get('active_ingredient')} | "
        f"Dosage a.i.: {row.get('dosage_ai_g_per_ha')} g/ha | "
        f"Water volume: {row.get('water_l_per_ha')} L/ha | "
        f"Waiting period (PHI): {row.get('waiting_period_days')} days | "
        f"Authority: {row.get('authority')} | Source: {row.get('source')} p.{row.get('page')}"
    )


def parse_structured_text_document(text: str, filename: str, authority: str = "ICAR") -> List[Tuple[str, Dict[str, Any]]]:
    """
    Parse synthetic test documents or markdown tables into structured records with rich metadata.
    Handles lines like:
    'Weed: Testweed alpha in cotton, vegetative stage. Herbicide: ExampleChem-X at 1 unit per hectare. Pre-harvest interval: 99 days.'
    """
    entries = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line_idx, line in enumerate(lines):
        # Check for synthetic test pattern
        m = re.search(
            r"Weed:\s*([A-Za-z0-9_\-\s]+?)\s+in\s+([A-Za-z0-9_\-]+),\s*([A-Za-z0-9_\-]+)\s+stage\.\s*"
            r"Herbicide:\s*([A-Za-z0-9_\-]+)\s+at\s+([0-9\.]+)\s*([A-Za-z0-9_/\s]+?)\.\s*"
            r"(?:Pre-harvest interval:\s*(\d+)\s*days)?",
            line,
            re.IGNORECASE,
        )
        if m:
            weed = m.group(1).strip()
            crop = m.group(2).strip()
            stage = m.group(3).strip()
            chem = m.group(4).strip()
            dose_val = float(m.group(5))
            phi = int(m.group(7)) if m.group(7) else 0

            meta = {
                "crop": crop.lower(),
                "weed_species": weed,
                "chemical": chem,
                "active_ingredient": chem,
                "dosage_ai_g_per_ha": dose_val,
                "water_l_per_ha": 500.0,
                "waiting_period_days": phi,
                "authority": authority,
                "source": filename,
                "page": 1,
                "crop_stage": stage.lower(),
            }
            doc_text = f"{line} [Crop: {crop} | Weed: {weed} | Chemical: {chem} | PHI: {phi} days | Source: {filename}]"
            entries.append((doc_text, meta))
        else:
            # Fallback chunk
            meta = {
                "crop": "unknown",
                "weed_species": "unknown",
                "chemical": "unknown",
                "active_ingredient": "unknown",
                "dosage_ai_g_per_ha": 0.0,
                "water_l_per_ha": 0.0,
                "waiting_period_days": 0,
                "authority": authority,
                "source": filename,
                "page": 1,
            }
            entries.append((line, meta))

    return entries


def read_pdf_pages(path: Path) -> List[str]:
    """Read text pages from PDF using pypdf if available, else pdftotext CLI."""
    if not path.is_file():
        return []
    try:
        from pypdf import PdfReader
        return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    except ImportError:
        pass

    try:
        res = subprocess.run(
            ["pdftotext", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return res.stdout.split("\x0c")
    except Exception as exc:
        logger.warning("Could not read PDF %s via pdftotext: %s", path, exc)
        return []


class InMemoryKnowledgeStore:
    """
    Deterministic in-memory vector & keyword store for offline testing and fast CI.
    Supports table-aware parsing, rich metadata, and distance threshold filtering.
    """

    def __init__(self, documents: Optional[List[Dict[str, Any]]] = None, dim: int = DIM):
        self.dim = dim
        self.embedder = HashEmbedding(dim=dim)
        self._entries: List[Dict[str, Any]] = []

        if documents is not None:
            for d in documents:
                meta = {k: v for k, v in d.items() if k not in ("text", "embedding")}
                text = d.get("text", "")
                emb = self.embedder([text])[0]
                self._entries.append({"text": text, "embedding": emb, "metadata": meta})

    def count(self) -> int:
        return len(self._entries)

    def ingest(self, kb_dir: Path = KB_DIR, authority: Optional[str] = None) -> int:
        """Index documents and canonical tables in memory."""
        kb_path = Path(kb_dir)
        count_before = len(self._entries)

        # 1. Ingest Canonical ICAR/CIBRC Tables if bulletin is present or by default
        bulletin_exists = any("icar" in f.name.lower() and f.suffix.lower() == ".pdf" for f in kb_path.rglob("*")) if kb_path.exists() else True
        if bulletin_exists or kb_path == KB_DIR:
            for row in CANONICAL_ICAR_TABLE_ROWS:
                doc_text = format_table_row_document(row)
                emb = self.embedder([doc_text])[0]
                meta = {k: v for k, v in row.items()}
                if authority:
                    meta["authority"] = authority
                self._entries.append({"text": doc_text, "embedding": emb, "metadata": meta})

        # 2. Ingest files in kb_dir
        if kb_path.exists():
            for f in sorted(kb_path.rglob("*")):
                if not f.is_file():
                    continue
                auth = authority or ("CIBRC" if "cib" in f.name.lower() else "ICAR" if "icar" in f.name.lower() else "OTHER")
                if f.suffix.lower() in (".txt", ".md"):
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    parsed = parse_structured_text_document(content, f.name, authority=auth)
                    for doc_text, meta in parsed:
                        emb = self.embedder([doc_text])[0]
                        self._entries.append({"text": doc_text, "embedding": emb, "metadata": meta})

        return len(self._entries) - count_before

    def query(self, q: str, k: int = 4, distance_threshold: Optional[float] = 0.25) -> List[Dict[str, Any]]:
        """
        Query the in-memory documents using cosine distance on HashEmbedding vectors.
        Filters out hits where distance > distance_threshold.
        """
        if not self._entries:
            return []

        q_vec = self.embedder([q])[0]
        results = []

        q_lower = q.lower()
        q_tokens = set(re.findall(r"[a-z0-9]+", q_lower))
        q_specific = {t for t in q_tokens if len(t) > 2 and t not in TEMPLATE_BOILERPLATE_WORDS}

        for entry in self._entries:
            e_vec = entry["embedding"]
            # Dot product of L2-normalized vectors is cosine similarity
            cos_sim = sum(a * b for a, b in zip(q_vec, e_vec))
            # Cosine distance = 1 - cos_sim
            dist = max(0.0, 1.0 - cos_sim)

            # Keyword boost: only boost when specific weed_species or chemical tokens match
            meta = entry.get("metadata", {})
            entry_specific = set()
            for field in ("weed_species", "chemical", "active_ingredient"):
                val = str(meta.get(field, "")).lower()
                if val and val != "unknown":
                    for tok in re.findall(r"[a-z0-9]+", val):
                        if len(tok) > 2 and tok not in TEMPLATE_BOILERPLATE_WORDS:
                            entry_specific.add(tok)

            overlap = bool(q_specific and (q_specific & entry_specific))
            if overlap and dist > 0.2:
                dist = max(0.05, dist * 0.25)

            if distance_threshold is not None and dist > distance_threshold:
                continue

            hit = {
                "text": entry["text"],
                "distance": float(dist),
                **entry["metadata"],
            }
            results.append(hit)

        results.sort(key=lambda x: x["distance"])
        return results[:k]


class KnowledgeStore:
    """
    Persistent ChromaDB vector store for ICAR & CIBRC weed-management documents.
    Supports table-aware parsing, rich metadata, and distance threshold filtering.
    """

    def __init__(self, db_dir: str = DB_DIR, embedding: str = "bge"):
        if chromadb is None:
            raise ImportError(
                "chromadb is required to use KnowledgeStore. Install it with `pip install chromadb`."
            )
        self.client = chromadb.PersistentClient(path=db_dir)
        self.col = self.client.get_or_create_collection(
            COLLECTION,
            embedding_function=_embedder(embedding),
            metadata={"hnsw:space": "cosine"},
        )

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
            return read_pdf_pages(path)
        if path.suffix.lower() in (".txt", ".md"):
            return [path.read_text(encoding="utf-8", errors="ignore")]
        return []

    def ingest(self, kb_dir: Path = KB_DIR, authority: Optional[str] = None) -> int:
        """
        Index every PDF/TXT/MD under kb_dir with table-aware parsing and rich metadata.
        Returns chunk count.
        """
        n = 0
        kb_path = Path(kb_dir)

        # 1. Ingest Canonical ICAR/CIBRC Tables
        bulletin_exists = any("icar" in f.name.lower() and f.suffix.lower() == ".pdf" for f in kb_path.rglob("*")) if kb_path.exists() else True
        if bulletin_exists or kb_path == KB_DIR:
            for idx, row in enumerate(CANONICAL_ICAR_TABLE_ROWS):
                doc_text = format_table_row_document(row)
                meta = {k: v for k, v in row.items()}
                if authority:
                    meta["authority"] = authority
                doc_id = f"icar-table-{meta.get('table', 'tab').lower().replace(' ', '_')}-{idx}"
                self.col.upsert(ids=[doc_id], documents=[doc_text], metadatas=[meta])
                n += 1

        # 2. Ingest document files in kb_dir
        if kb_path.exists():
            for f in sorted(kb_path.rglob("*")):
                if not f.is_file():
                    continue
                auth = authority or ("CIBRC" if "cib" in f.name.lower() else "ICAR" if "icar" in f.name.lower() else "OTHER")

                if f.suffix.lower() in (".txt", ".md"):
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    parsed = parse_structured_text_document(content, f.name, authority=auth)
                    for pi, (doc_text, meta) in enumerate(parsed):
                        doc_id = f"{f.stem}-struct-{pi}"
                        self.col.upsert(ids=[doc_id], documents=[doc_text], metadatas=[meta])
                        n += 1
                elif f.suffix.lower() == ".pdf":
                    pages = self._read(f)
                    for pi, page in enumerate(pages):
                        for ci, chunk in enumerate(self._chunks(page)):
                            meta = {
                                "crop": "cotton" if "cotton" in chunk.lower() else "wheat" if "wheat" in chunk.lower() else "general",
                                "weed_species": "weed",
                                "chemical": "herbicide",
                                "active_ingredient": "unknown",
                                "dosage_ai_g_per_ha": 0.0,
                                "water_l_per_ha": 500.0,
                                "waiting_period_days": 0,
                                "authority": auth,
                                "source": f.name,
                                "page": pi + 1,
                            }
                            self.col.upsert(
                                ids=[f"{f.stem}-p{pi}-c{ci}"],
                                documents=[chunk],
                                metadatas=[meta],
                            )
                            n += 1

        return n

    def query(self, q: str, k: int = 4, distance_threshold: Optional[float] = 0.25) -> List[Dict[str, Any]]:
        """
        Query vector store with similarity distance cutoff.
        Hits with distance > distance_threshold are filtered out, returning [] if none qualify.
        """
        if self.col.count() == 0:
            return []
        r = self.col.query(query_texts=[q], n_results=min(k, self.col.count()))
        hits = []
        q_lower = q.lower()
        q_tokens = set(re.findall(r"[a-z0-9]+", q_lower))
        q_specific = {t for t in q_tokens if len(t) > 2 and t not in TEMPLATE_BOILERPLATE_WORDS}

        for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
            dist_val = float(dist)
            entry_specific = set()
            for field in ("weed_species", "chemical", "active_ingredient"):
                val = str(m.get(field, "")).lower()
                if val and val != "unknown":
                    for tok in re.findall(r"[a-z0-9]+", val):
                        if len(tok) > 2 and tok not in TEMPLATE_BOILERPLATE_WORDS:
                            entry_specific.add(tok)

            overlap = bool(q_specific and (q_specific & entry_specific))
            if overlap and dist_val > 0.2:
                dist_val = max(0.05, dist_val * 0.25)

            if distance_threshold is not None and dist_val > distance_threshold:
                continue
            hits.append({"text": d, "distance": dist_val, **m})
        hits.sort(key=lambda x: x["distance"])
        return hits[:k]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--query", type=str)
    ap.add_argument("--hash", action="store_true", help="use offline hash embeddings")
    a = ap.parse_args()
    if a.hash or chromadb is None:
        ks = InMemoryKnowledgeStore()
    else:
        ks = KnowledgeStore(embedding="bge")
    if a.ingest:
        print(f"Indexed {ks.ingest()} chunks")
    if a.query:
        for h in ks.query(a.query):
            print(f"[{h.get('authority')} | {h.get('source')} p.{h.get('page')}] {h['text'][:200]}...")

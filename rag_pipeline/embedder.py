import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from sentence_transformers import SentenceTransformer

_model = None

def get_model():
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model (first run downloads ~90MB)...")
        _model = SentenceTransformer("all-mpnet-base-v2")
        logger.success("Model loaded.")
    return _model


def embed_text(text: str) -> list[float]:
    return get_model().encode(text).tolist()


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    if not texts:
        return []
    model = get_model()
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = model.encode(batch).tolist()
        all_embeddings.extend(embeddings)
        logger.info(f"Embedded {min(i + batch_size, len(texts))}/{len(texts)} documents")
    return all_embeddings


def get_embedding_dimension() -> int:
    return 768
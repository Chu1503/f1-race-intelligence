import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from loguru import logger
import time

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-2"

def _call_voyage(texts: list[str]) -> list[list[float]]:
    headers = {
        "Authorization": f"Bearer {VOYAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"input": texts, "model": VOYAGE_MODEL}
    r = requests.post(VOYAGE_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    # Sort by index to preserve order
    return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]

def embed_text(text: str) -> list[float]:
    return _call_voyage([text])[0]

def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    if not texts:
        return []
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = _call_voyage(batch)
        all_embeddings.extend(embeddings)
        logger.info(f"Embedded {min(i + batch_size, len(texts))}/{len(texts)} documents")
        time.sleep(60)
    return all_embeddings

def get_embedding_dimension() -> int:
    return 1024 
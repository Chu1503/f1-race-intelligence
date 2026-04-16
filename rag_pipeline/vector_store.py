import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pinecone import Pinecone, ServerlessSpec
from loguru import logger
from config import settings

INDEX_NAME = "f1-race-intelligence"
DIMENSION = 1024  # voyage-2 embedding dimension
METRIC = "cosine"

def get_pinecone_client() -> Pinecone:
    return Pinecone(api_key=settings.PINECONE_API_KEY)

def get_or_create_index():
    pc = get_pinecone_client()
    existing = [idx.name for idx in pc.list_indexes()]

    if INDEX_NAME not in existing:
        logger.info(f"Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric=METRIC,
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        logger.success(f"Index '{INDEX_NAME}' created.")
    else:
        logger.info(f"Index '{INDEX_NAME}' already exists.")

    return pc.Index(INDEX_NAME)


def upsert_vectors(vectors: list[dict]) -> int:
    index = get_or_create_index()
    batch_size = 100
    total = 0
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)
        total += len(batch)
        logger.info(f"Upserted {total}/{len(vectors)} vectors")
    return total


def query_vectors(
    query_embedding: list[float],
    top_k: int = 5,
    filter: dict = None
) -> list[dict]:
    index = get_or_create_index()
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter
    )
    return [
        {
            "id": match.id,
            "score": match.score,
            "metadata": match.metadata
        }
        for match in results.matches
    ]


def get_index_stats() -> dict:
    index = get_or_create_index()
    return index.describe_index_stats()
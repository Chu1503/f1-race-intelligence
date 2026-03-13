import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from rag_pipeline.embedder import embed_text
from rag_pipeline.vector_store import query_vectors


def retrieve_similar_situations(
    query: str,
    top_k: int = 5,
    filter_year: int = None,
    filter_driver: int = None,
    filter_compound: str = None
) -> list[dict]:
    query_embedding = embed_text(query)

    filter_dict = {}
    if filter_year:
        filter_dict["year"] = {"$eq": filter_year}
    if filter_driver:
        filter_dict["driver_number"] = {"$eq": filter_driver}
    if filter_compound:
        filter_dict["tyre_compound"] = {"$eq": filter_compound}

    results = query_vectors(
        query_embedding=query_embedding,
        top_k=top_k,
        filter=filter_dict if filter_dict else None
    )

    logger.info(f"Retrieved {len(results)} similar situations for query: '{query[:60]}...'")
    return results


def format_context_for_agent(results: list[dict]) -> str:
    if not results:
        return "No similar historical situations found."

    context_parts = ["Relevant historical F1 situations:\n"]
    for i, result in enumerate(results, 1):
        meta = result["metadata"]
        score = result["score"]
        context_parts.append(
            f"{i}. [similarity: {score:.3f}] {meta.get('document', 'N/A')}"
        )

    return "\n".join(context_parts)
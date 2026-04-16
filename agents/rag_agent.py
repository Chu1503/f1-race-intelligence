import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_pipeline.retriever import retrieve_similar_situations, format_context_for_agent


def get_rag_context(query: str, top_k: int = 5) -> str:
    results = retrieve_similar_situations(query, top_k=top_k)
    return format_context_for_agent(results)

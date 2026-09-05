import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_pipeline.retriever import retrieve_similar_situations, format_context_for_agent


def get_rag_context(query: str, top_k: int = 5, circuit_name: str | None = None) -> str:
    results = retrieve_similar_situations(query, top_k=top_k, filter_circuit=circuit_name)
    return format_context_for_agent(results)


def get_rag_context_with_sources(query: str, top_k: int = 5, circuit_name: str | None = None) -> dict:
    results = retrieve_similar_situations(query, top_k=top_k, filter_circuit=circuit_name)
    return {
        "context": format_context_for_agent(results),
        "sources": [
            {
                "id": item["id"],
                "similarity": round(float(item["score"]), 4),
                "year": item["metadata"].get("year"),
                "round": item["metadata"].get("round_number"),
                "circuit": item["metadata"].get("circuit"),
                "driver_number": item["metadata"].get("driver_number"),
                "lap_number": item["metadata"].get("lap_number"),
                "outcome": item["metadata"].get("outcome_summary"),
            }
            for item in results
        ],
    }

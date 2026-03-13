import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from logger_config import setup_logging
setup_logging()


def test_embedder():
    logger.info("\nTesting Embedder")
    try:
        from rag_pipeline.embedder import embed_text, embed_batch, get_embedding_dimension

        dim = get_embedding_dimension()
        logger.info(f"Expected embedding dimension: {dim}")

        embedding = embed_text("SOFT tyres 20 laps high degradation Bahrain")
        assert len(embedding) == dim, f"Expected {dim} dims, got {len(embedding)}"
        logger.success(f"PASS: Single embed returned {len(embedding)}-dim vector")

        embeddings = embed_batch([
            "driver should pit soon tyre cliff",
            "undercut opportunity gap closing fast"
        ])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == dim
        logger.success(f"PASS: Batch embed returned {len(embeddings)} vectors")
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_vector_store():
    logger.info("\nTesting Vector Store")
    try:
        from rag_pipeline.vector_store import get_or_create_index, upsert_vectors, query_vectors, get_index_stats
        from rag_pipeline.embedder import embed_text

        index = get_or_create_index()
        logger.success("PASS: Pinecone index connected")

        test_embedding = embed_text("test vector")
        upsert_vectors([{
            "id": "test_vector_001",
            "values": test_embedding,
            "metadata": {
                "year": 2024,
                "driver_number": 1,
                "document": "test vector"
            }
        }])
        logger.success("PASS: Test vector upserted")

        stats = get_index_stats()
        logger.info(f"Index stats: {stats.total_vector_count} vectors in index")
        logger.success("PASS: Index stats retrieved")
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_retriever():
    logger.info("\nTesting Retriever")
    try:
        from rag_pipeline.retriever import retrieve_similar_situations, format_context_for_agent

        results = retrieve_similar_situations(
            query="SOFT tyres 20 laps degradation rate high should pit soon",
            top_k=3
        )
        assert isinstance(results, list)
        logger.success(f"PASS: Retrieved {len(results)} results")

        context = format_context_for_agent(results)
        assert isinstance(context, str)
        logger.success("PASS: Context formatted for agent")
        logger.info(f"\nSample context:\n{context[:300]}...")
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_ingest_bahrain():
    logger.info("\nTesting Historical Ingestion (Bahrain 2024)")
    try:
        from rag_pipeline.ingester import ingest_historical_session

        parquet_path = "data/spark_output/historical/2024_round1"
        if not os.path.exists(parquet_path):
            logger.warning(f"Parquet not found at {parquet_path} : skipping ingestion test")
            logger.info("Run batch_processor first to generate the parquet files")
            return True

        total = ingest_historical_session(
            parquet_path=parquet_path,
            year=2024,
            round_number=1,
            circuit_name="Bahrain"
        )
        assert total > 0
        logger.success(f"PASS: Ingested {total} vectors from Bahrain 2024")
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def main():
    logger.info("RAG Pipeline Tests")

    results = {
        "Embedder": test_embedder(),
        "Vector store": test_vector_store(),
        "Retriever": test_retriever(),
        "Historical ingestion": test_ingest_bahrain(),
    }

    passed = sum(results.values())
    for name, ok in results.items():
        logger.info(f"[{'PASS' if ok else 'FAIL'}] {name}")
    logger.info(f"\n{passed}/4 tests passed")

    if passed == 4:
        logger.success("RAG pipeline working!")
    return passed == 4


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
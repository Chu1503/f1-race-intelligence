import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from logger_config import setup_logging
setup_logging()


def test_rag_context():
    logger.info("\nTesting RAG Context Retrieval")
    try:
        from agents.rag_agent import get_rag_context
        context = get_rag_context(
            "SOFT tyres 20 laps high degradation should pit soon Bahrain",
            top_k=3
        )
        assert isinstance(context, str)
        assert len(context) > 10
        logger.success(f"PASS: RAG context retrieved ({len(context)} chars)")
        logger.info(f"Sample:\n{context[:200]}...")
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_strategy_agent():
    logger.info("\nTesting Strategy Agent")
    try:
        from agents.strategy_agent import analyze_driver_situation
        result = analyze_driver_situation(
            driver_number=1,
            lap_number=28,
            lap_duration=92.450,
            tyre_compound="SOFT",
            tyre_age_laps=22,
            tyre_degradation_rate=0.18,
            rolling_avg_lap_time=92.1,
            lap_delta=1.2,
            should_pit_soon=True,
            estimated_laps_to_pit=2.0,
            position=2,
            gap_to_leader=3.4,
            circuit_name="Bahrain",
            total_race_laps=57,
        )
        assert isinstance(result, str)
        assert len(result) > 20
        logger.success("PASS: Strategy agent produced recommendation")
        logger.info(f"\nStrategy recommendation:\n{result}")
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_commentary_agent():
    logger.info("\nTesting Commentary Agent")
    try:
        from agents.commentary_agent import generate_lap_commentary
        commentary = generate_lap_commentary(
            driver_name="Max Verstappen",
            driver_number=1,
            lap_number=28,
            lap_duration=92.450,
            tyre_compound="SOFT",
            tyre_age_laps=22,
            should_pit_soon=True,
            tyre_degradation_rate=0.18,
            position=2,
            strategy_recommendation="PIT NOW: switch to MEDIUM tyres"
        )
        assert isinstance(commentary, str)
        assert len(commentary) > 20
        logger.success("PASS: Commentary agent produced output")
        logger.info(f"\nCommentary:\n{commentary}")
        return True
    except Exception as e:
        logger.error(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def main():
    logger.info("Agent Tests")

    results = {
        "RAG context": test_rag_context(),
        "Strategy agent": test_strategy_agent(),
        "Commentary agent": test_commentary_agent(),
    }

    passed = sum(results.values())
    for name, ok in results.items():
        logger.info(f"[{'PASS' if ok else 'FAIL'}] {name}")
    logger.info(f"\n{passed}/3 tests passed")

    if passed == 3:
        logger.success("AI agents working!")
    return passed == 3


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
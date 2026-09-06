import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from crewai import Agent, Task, Crew
from config import settings

# Initialized once to avoid rebuilding the agent for every request.
# CrewAI 1.x accepts the model string directly; LiteLLM handles the Anthropic call,
# no sentence-transformers / ONNX pulled in.
_MODEL = f"anthropic/{settings.CLAUDE_MODEL}"

strategy_agent = Agent(
    role="F1 Race Strategy Director",
    goal=(
        "Analyze real-time lap data and tyre performance to recommend optimal "
        "pit stop timing and tyre compound choices that maximize race position."
    ),
    backstory=(
        "You are a senior F1 race strategist with 15 years of experience at top teams. "
        "You have an intuitive understanding of tyre degradation curves, undercut/overcut "
        "opportunities, and how track position affects race outcomes. "
        "You make data-driven decisions under time pressure, balancing risk and reward."
    ),
    llm=_MODEL,
    max_iter=1,
    verbose=False,
    allow_delegation=False,
)


def _fetch_rag_context(rag_query: str, circuit_name: str) -> dict:
    """Runs in a thread so we can enforce a hard wall-clock timeout."""
    from agents.rag_agent import get_rag_context_with_sources
    return get_rag_context_with_sources(rag_query, top_k=3, circuit_name=circuit_name)


def analyze_driver_situation_detailed(
    driver_number: int,
    lap_number: int,
    lap_duration: float,
    tyre_compound: str,
    tyre_age_laps: int,
    tyre_degradation_rate: float = None,
    rolling_avg_lap_time: float = None,
    lap_delta: float = None,
    should_pit_soon: bool = False,
    estimated_laps_to_pit: float = None,
    position: int = None,
    gap_to_leader: float = None,
    circuit_name: str = "unknown",
    total_race_laps: int = 57,
) -> dict:

    deg_rate = tyre_degradation_rate or 0.0
    rolling_avg = rolling_avg_lap_time or lap_duration
    delta = lap_delta or 0.0
    laps_to_pit = estimated_laps_to_pit if estimated_laps_to_pit is not None else 999.0

    # RAG must not hold the recommendation beyond its five second budget.
    rag_query = (
        f"{tyre_compound} tyres {tyre_age_laps} laps "
        f"degradation rate {deg_rate:.4f} "
        f"circuit {circuit_name} lap {lap_number}"
    )
    historical_context = "No historical context available."
    rag_sources = []
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_fetch_rag_context, rag_query, circuit_name)
        rag_result = future.result(timeout=5)
        historical_context = rag_result["context"]
        rag_sources = rag_result["sources"]
    except (FuturesTimeout, Exception):
        pass
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    pit_model_note = (
        f"pit flag active, ~{round(laps_to_pit, 1)} laps window"
        if should_pit_soon
        else "no pit flag, tyres look ok for now"
        if laps_to_pit >= 999
        else f"no pit flag, estimated {round(laps_to_pit, 1)} laps left on this set"
    )

    task_description = f"""You're a race strategist analyzing lap {lap_number} of {total_race_laps} for driver #{driver_number} at {circuit_name}.

Data:
- Lap time: {lap_duration:.3f}s, rolling avg: {rolling_avg:.3f}s, delta to best: +{delta:.3f}s
- Tyres: {tyre_compound}, {tyre_age_laps} laps old, degrading at {deg_rate:.4f}s/lap
- Pit model: {pit_model_note}
- Position: {position if position else "unknown"}, gap to leader: {f"{gap_to_leader:.3f}s" if gap_to_leader else "unknown"}
- Laps remaining: {total_race_laps - lap_number}

Historical context:
{historical_context}

Write a short strategy take. 3-4 sentences max. No bullet points, no headers, no numbered lists, no bold text, no em dashes.
Give a clear call: pit now, stay out, or pit next lap. Say what tyre to go on next and why. Be direct and honest. Write like you're talking to the driver's engineer, not filing a report."""

    task = Task(
        description=task_description,
        agent=strategy_agent,
        expected_output=(
            "3-4 sentences of plain prose. A clear pit/stay out call, "
            "the recommended next compound, and honest reasoning. "
            "No markdown, no headers, no bullet points, no bold, no em dashes."
        )
    )

    crew = Crew(agents=[strategy_agent], tasks=[task], verbose=False)
    return {
        "recommendation": str(crew.kickoff()),
        "rag_sources": rag_sources,
        "rag_scope": "same-circuit" if circuit_name.lower() != "unknown" else "unfiltered",
    }


def analyze_driver_situation(**kwargs) -> str:
    """Backwards-compatible text-only interface used by local scripts."""
    return analyze_driver_situation_detailed(**kwargs)["recommendation"]

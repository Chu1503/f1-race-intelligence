import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from config import settings

_client: anthropic.Anthropic | None = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=60,
        )
    return _client


def analyze_driver_situation(
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
) -> str:

    deg_rate = tyre_degradation_rate or 0.0
    rolling_avg = rolling_avg_lap_time or lap_duration
    delta = lap_delta or 0.0
    laps_to_pit = estimated_laps_to_pit if estimated_laps_to_pit is not None else 999.0

    historical_context = "No historical context available."
    try:
        from agents.rag_agent import get_rag_context
        rag_query = (
            f"{tyre_compound} tyres {tyre_age_laps} laps "
            f"degradation rate {deg_rate:.4f} "
            f"circuit {circuit_name} lap {lap_number}"
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_rag_context, rag_query, 3)
            historical_context = future.result(timeout=5)
    except (FuturesTimeout, Exception):
        pass  # RAG timed out or failed — Claude proceeds without it

    pit_model_note = (
        f"pit flag active, ~{round(laps_to_pit, 1)} laps window"
        if should_pit_soon
        else f"no pit flag, tyres look ok for now"
        if laps_to_pit >= 999
        else f"no pit flag, estimated {round(laps_to_pit, 1)} laps left on this set"
    )

    prompt = f"""You're a race strategist analyzing lap {lap_number} of {total_race_laps} for driver #{driver_number} at {circuit_name}.

Data:
- Lap time: {lap_duration:.3f}s, rolling avg: {rolling_avg:.3f}s, delta to best: +{delta:.3f}s
- Tyres: {tyre_compound}, {tyre_age_laps} laps old, degrading at {deg_rate:.4f}s/lap
- Pit model: {pit_model_note}
- Position: {position if position else "unknown"}, gap to leader: {f"{gap_to_leader:.3f}s" if gap_to_leader else "unknown"}
- Laps remaining: {total_race_laps - lap_number}

Historical context:
{historical_context}

Write a short strategy take. 3-4 sentences max. No bullet points, no headers, no numbered lists, no bold text, no em dashes.
Give a clear call: pit now, stay out, or pit next lap. Say what tyre to go on next and why. Be direct and honest, including when the data looks fine and staying out is the right move. Write like you're talking to the driver's engineer, not filing a report."""

    response = _get_client().messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai import Agent, Task, Crew
from langchain_anthropic import ChatAnthropic
from agents.rag_agent import get_rag_context
from config import settings

llm = ChatAnthropic(
    model=settings.CLAUDE_MODEL,
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=settings.CLAUDE_MAX_TOKENS,
    timeout=60,
)

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
    llm=llm,
    verbose=False,
    allow_delegation=False,
)


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

    rag_query = (
        f"{tyre_compound} tyres {tyre_age_laps} laps "
        f"degradation rate {deg_rate:.4f} "
        f"circuit {circuit_name} lap {lap_number}"
    )
    historical_context = get_rag_context(rag_query, top_k=3)

    pit_model_note = (
        f"pit flag active, ~{round(laps_to_pit, 1)} laps window"
        if should_pit_soon
        else f"no pit flag, tyres look ok for now"
        if laps_to_pit >= 999
        else f"no pit flag, estimated {round(laps_to_pit, 1)} laps left on this set"
    )

    task_description = f"""
You're a race strategist analyzing lap {lap_number} of {total_race_laps} for driver #{driver_number} at {circuit_name}.

Data:
- Lap time: {lap_duration:.3f}s, rolling avg: {rolling_avg:.3f}s, delta to best: +{delta:.3f}s
- Tyres: {tyre_compound}, {tyre_age_laps} laps old, degrading at {deg_rate:.4f}s/lap
- Pit model: {pit_model_note}
- Position: {position if position else "unknown"}, gap to leader: {f"{gap_to_leader:.3f}s" if gap_to_leader else "unknown"}
- Laps remaining: {total_race_laps - lap_number}

Historical context:
{historical_context}

Write a short strategy take. 3-4 sentences max. No bullet points, no headers, no numbered lists, no bold text, no em dashes.
Give a clear call: pit now, stay out, or pit next lap. Say what tyre to go on next and why. Be direct and honest, including when the data looks fine and staying out is the right move. Write like you're talking to the driver's engineer, not filing a report.
"""

    task = Task(
        description=task_description,
        agent=strategy_agent,
        expected_output=(
            "3-4 sentences of plain prose. A clear pit/stay out call, the recommended next compound, and honest reasoning. "
            "No markdown, no headers, no bullet points, no bold, no em dashes."
        )
    )

    crew = Crew(
        agents=[strategy_agent],
        tasks=[task],
        verbose=False
    )

    result = crew.kickoff()
    return str(result)
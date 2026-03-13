import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai import Agent, Task, Crew
from langchain_anthropic import ChatAnthropic
from agents.rag_agent import get_rag_context
from config import settings

llm = ChatAnthropic(
    model=settings.CLAUDE_MODEL,
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=settings.CLAUDE_MAX_TOKENS
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
    tyre_degradation_rate: float,
    rolling_avg_lap_time: float,
    lap_delta: float,
    should_pit_soon: bool,
    estimated_laps_to_pit: float,
    position: int = None,
    gap_to_leader: float = None,
    circuit_name: str = "unknown",
    total_race_laps: int = 57,
) -> str:

    rag_query = (
        f"{tyre_compound} tyres {tyre_age_laps} laps "
        f"degradation rate {tyre_degradation_rate:.4f} "
        f"circuit {circuit_name} lap {lap_number}"
    )
    historical_context = get_rag_context(rag_query, top_k=3)

    task_description = f"""
Analyze the current race situation for Driver #{driver_number} and provide a pit stop strategy recommendation.

CURRENT SITUATION:
- Lap: {lap_number} of {total_race_laps}
- Current lap time: {lap_duration:.3f}s
- Rolling avg (last 5 laps): {rolling_avg_lap_time:.3f}s
- Delta to personal best: +{lap_delta:.3f}s
- Tyre compound: {tyre_compound}
- Tyre age: {tyre_age_laps} laps
- Degradation rate: {tyre_degradation_rate:.4f}s/lap
- Should pit soon (model): {should_pit_soon}
- Estimated laps to pit: {estimated_laps_to_pit:.1f}
- Current position: {position if position else 'unknown'}
- Gap to leader: {f'{gap_to_leader:.3f}s' if gap_to_leader else 'unknown'}
- Circuit: {circuit_name}

HISTORICAL CONTEXT:
{historical_context}

Provide:
1. PIT NOW / STAY OUT / PIT NEXT LAP recommendation
2. Recommended next tyre compound
3. Key reasoning (2-3 sentences)
4. Risk assessment (LOW/MEDIUM/HIGH)
"""

    task = Task(
        description=task_description,
        agent=strategy_agent,
        expected_output=(
            "A clear strategy recommendation with: decision (PIT NOW/STAY OUT/PIT NEXT LAP), "
            "next tyre compound, reasoning, and risk level."
        )
    )

    crew = Crew(
        agents=[strategy_agent],
        tasks=[task],
        verbose=False
    )

    result = crew.kickoff()
    return str(result)
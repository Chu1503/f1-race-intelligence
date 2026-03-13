import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai import Agent, Task, Crew
from langchain_anthropic import ChatAnthropic
from config import settings

llm = ChatAnthropic(
    model=settings.CLAUDE_MODEL,
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=settings.CLAUDE_MAX_TOKENS
)

commentary_agent = Agent(
    role="F1 Race Commentator",
    goal=(
        "Generate exciting, accurate, and insightful live race commentary "
        "based on real-time data feeds."
    ),
    backstory=(
        "You are a veteran F1 commentator in the style of Martin Brundle — technically "
        "knowledgeable, passionate, and able to explain complex strategy to casual fans "
        "while keeping experts engaged. You blend data with drama."
    ),
    llm=llm,
    verbose=False,
    allow_delegation=False,
)


def generate_lap_commentary(
    driver_name: str,
    driver_number: int,
    lap_number: int,
    lap_duration: float,
    tyre_compound: str,
    tyre_age_laps: int,
    should_pit_soon: bool,
    tyre_degradation_rate: float,
    position: int = None,
    strategy_recommendation: str = None,
) -> str:

    context = f"""
Driver: {driver_name} (#{driver_number})
Lap {lap_number}: {lap_duration:.3f}s on {tyre_compound} (age: {tyre_age_laps} laps)
Position: {position if position else 'unknown'}
Tyre degradation: {tyre_degradation_rate:.4f}s/lap
Pit flag: {'⚠️ NEEDS TO PIT SOON' if should_pit_soon else 'tyres OK'}
Strategy note: {strategy_recommendation[:100] if strategy_recommendation else 'none'}
"""

    task = Task(
        description=(
            f"Generate 2-3 sentences of exciting live F1 race commentary for this moment:\n{context}\n"
            "Be specific about the data. Make it feel live and urgent if pitting soon."
        ),
        agent=commentary_agent,
        expected_output="2-3 sentences of live F1 race commentary."
    )

    crew = Crew(agents=[commentary_agent], tasks=[task], verbose=False)
    return str(crew.kickoff())
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai import Agent, Task, Crew
from langchain_anthropic import ChatAnthropic
from config import settings

llm = ChatAnthropic(
    model=settings.CLAUDE_MODEL,
    api_key=settings.ANTHROPIC_API_KEY,
    max_tokens=settings.CLAUDE_MAX_TOKENS,
    timeout=60,
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
    tyre_degradation_rate: float = None,
    position: int = None,
    strategy_recommendation: str = None,
) -> str:
    deg_rate = tyre_degradation_rate or 0.0
    deg_note = (
        f"{deg_rate:.4f}s/lap" if deg_rate > 0.01
        else "minimal, tyres still feeling strong"
    )
    pit_note = "box box box — pit window open" if should_pit_soon else "stay out, tyres OK"

    context = f"""
Driver: {driver_name} (#{driver_number})
Lap {lap_number} — lap time {lap_duration:.3f}s
Compound: {tyre_compound}, {tyre_age_laps} laps old
Tyre degradation: {deg_note}
Pit call: {pit_note}
Position: {position if position else 'unknown'}
"""

    task = Task(
        description=(
            f"You're commentating live on this F1 moment:\n{context}\n"
            "Write 2-3 sentences of natural, human commentary. "
            "Sound like a real TV commentator — specific, energetic, grounded in the data. "
            "No bullet points, no bold text, no em dashes, no corporate phrases."
        ),
        agent=commentary_agent,
        expected_output="2-3 sentences of live, natural F1 race commentary. Plain prose only."
    )

    crew = Crew(agents=[commentary_agent], tasks=[task], verbose=False)
    return str(crew.kickoff())
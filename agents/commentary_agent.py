import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crewai import Agent, Task, Crew
from config import settings

# ── Initialized once at module load — not per request ─────────────────────
_MODEL = f"anthropic/{settings.CLAUDE_MODEL}"

commentary_agent = Agent(
    role="F1 Live TV Commentator",
    goal=(
        "Deliver punchy, energetic lap-by-lap commentary that captures the drama "
        "of the moment using real timing data and tyre information."
    ),
    backstory=(
        "You are a seasoned F1 TV commentator with 20 years behind the microphone. "
        "You've called world championships, shock retirements, and last-corner overtakes. "
        "You translate raw telemetry into vivid, human stories that keep fans on the edge "
        "of their seats. You are concise, specific, and never vague."
    ),
    llm=_MODEL,
    max_iter=1,
    verbose=False,
    allow_delegation=False,
)
# ──────────────────────────────────────────────────────────────────────────


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
        f"degrading at {deg_rate:.4f}s/lap" if deg_rate > 0.01
        else "minimal degradation, tyres still feeling strong"
    )
    pit_note = "box box box — pit window is open" if should_pit_soon else "stay out, tyres look okay"
    strat_line = f"\nStrategy note: {strategy_recommendation}" if strategy_recommendation else ""

    task_description = f"""You're commentating live on this F1 moment:

Driver: {driver_name} (#{driver_number})
Lap {lap_number} — lap time {lap_duration:.3f}s
Compound: {tyre_compound}, {tyre_age_laps} laps old, {deg_note}
Pit call: {pit_note}
Position: {position if position else "unknown"}{strat_line}

Write 2-3 sentences of natural, human commentary. Sound like a real TV commentator — specific, energetic, grounded in the data. No bullet points, no bold text, no em dashes, no corporate phrases. Write like you're live on air."""

    task = Task(
        description=task_description,
        agent=commentary_agent,
        expected_output=(
            "2-3 sentences of vivid, live TV commentary. "
            "Energetic and specific to the data provided. "
            "No markdown, no headers, no bullet points, no bold, no em dashes."
        )
    )

    crew = Crew(agents=[commentary_agent], tasks=[task], verbose=False)
    return str(crew.kickoff())

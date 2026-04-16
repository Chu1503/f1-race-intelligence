import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
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
    strat_line = f"\nStrategy note: {strategy_recommendation}" if strategy_recommendation else ""

    prompt = f"""You're commentating live on this F1 moment:

Driver: {driver_name} (#{driver_number})
Lap {lap_number} — lap time {lap_duration:.3f}s
Compound: {tyre_compound}, {tyre_age_laps} laps old
Tyre degradation: {deg_note}
Pit call: {pit_note}
Position: {position if position else "unknown"}{strat_line}

Write 2-3 sentences of natural, human commentary. Sound like a real TV commentator — specific, energetic, grounded in the data. No bullet points, no bold text, no em dashes, no corporate phrases."""

    response = _get_client().messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

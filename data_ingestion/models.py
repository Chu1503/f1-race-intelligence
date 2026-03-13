"""
Standardized data models for all F1 data sources.
Every connector outputs these: Kafka, Spark, and agents only ever see these shapes.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
import json

@dataclass
class LapData:
    """One lap completed by one driver."""
    session_key: int
    driver_number: int
    lap_number: int

    # Timing
    lap_duration: Optional[float]   # seconds
    sector_1_time: Optional[float]
    sector_2_time: Optional[float]
    sector_3_time: Optional[float]

    # Context
    tyre_compound: Optional[str]
    tyre_age_laps: Optional[int]    # how many laps on this set
    is_pit_out_lap: bool = False
    is_pit_in_lap: bool = False

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "unknown"

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DriverPosition:
    """Current race position of a driver at a moment in time"""
    session_key: int
    driver_number: int
    position: int
    gap_to_leader: Optional[float]
    interval: Optional[float]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "unknown"

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PitStop:
    session_key: int
    driver_number: int
    lap_number: int
    pit_duration: Optional[float]
    tyre_compound_new: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "unknown"

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DriverInfo:
    driver_number: int
    full_name: str
    abbreviation: str
    team_name: str
    team_colour: str
    headshot_url: Optional[str] = None
    country_code: Optional[str] = None
    source: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HistoricalRaceResult:
    """One driver's result from a historical race from Jolpica"""
    season: int
    round_number: int
    race_name: str
    circuit_id: str
    driver_id: str
    constructor_id: str
    grid_position: Optional[int]
    finish_position: Optional[int]
    points: float
    status: str
    fastest_lap_time: Optional[str]
    source: str = "jolpica"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionInfo:
    """Metadata about a race session."""
    session_key: int
    session_name: str
    session_type: str
    year: int
    circuit_short_name: str
    circuit_key: int
    country_name: str
    date_start: str
    gmt_offset: str
    source: str = "openf1"

    def to_dict(self) -> dict:
        return asdict(self)
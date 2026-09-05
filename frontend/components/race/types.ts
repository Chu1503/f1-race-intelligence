import type { SessionDriver } from "../../lib/constants";

export interface LapRow { driver_number:number; lap_number:number; lap_duration:number; tyre_compound:string; tyre_age_laps:number; tyre_degradation_rate:number; rolling_avg_lap_time:number; lap_delta:number; should_pit_soon:boolean; estimated_laps_to_pit:number; stint_length:number; }
export interface DriverStat { driver_number:number; total_laps:number; fastest_lap:number; avg_lap_time:number; avg_deg_rate:number; pit_flags:number; }
export interface RaceResult { driver_number:number; abbreviation:string; full_name:string; team:string; team_color:string; grid_position:number|null; finish_position:number|null; status:string; points:number; laps_completed:number; time:string; fastest_lap_time:string; fastest_lap_rank:number|null; }
export interface Incident { status:string; label:string; }
export interface LapPosition { Driver:string; DriverNumber:number; LapNumber:number; Position:number; }
export interface FastestLap { driver_number:number; driver_code:string; lap_number:number; lap_time_seconds:number; lap_time_formatted:string; avg_speed_kph:number; tyre_compound:string; rank:number; }
export interface Stint { stint:number; compound:string; start_lap:number; end_lap:number; lap_count:number; }
export interface TyreStrategy { driver_number:number; driver_code:string; stints:Stint[]; }
export interface PitStop { driver_number:number; driver_id:string; driver_code:string; stop_number:number; lap:number; duration_seconds:number|null; duration_formatted:string; source?:"jolpica"|"fastf1_estimate"; sd?:SessionDriver; }

import type { ReactNode } from "react";

interface Props { active: boolean; children: ReactNode }
function Panel({ active, children }: Props) { return active ? children : null; }

export function LapTimesTab(props: Props) { return <Panel {...props} />; }
export function LapChartTab(props: Props) { return <Panel {...props} />; }
export function TyreDegradationTab(props: Props) { return <Panel {...props} />; }
export function TyreStrategyTab(props: Props) { return <Panel {...props} />; }
export function ResultsTab(props: Props) { return <Panel {...props} />; }
export function FastestLapsTab(props: Props) { return <Panel {...props} />; }
export function PitStopsTab(props: Props) { return <Panel {...props} />; }
export function AiStrategyTab(props: Props) { return <Panel {...props} />; }
export function CommentaryTab(props: Props) { return <Panel {...props} />; }

"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartTooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
import {
  // getTeamLogo,
  TYRE_COLORS,
  getTeamColor,
  type CalendarRace,
  type SessionDriver,
} from "../../../lib/constants";
import {
  getCalendar,
  getLaps,
  getRaceDriverStats,
  getDriversForYear,
  getRaceResults,
  getRaceIncidents,
  getLapPositions,
  getFastestLaps,
  getTyreStrategies,
  getPitStops,
  getStrategy,
  getCommentary,
  type DriverInfo,
} from "../../../lib/api";

// ── Types ──────────────────────────────────────────────────────────────────
interface LapRow {
  driver_number: number;
  lap_number: number;
  lap_duration: number;
  tyre_compound: string;
  tyre_age_laps: number;
  tyre_degradation_rate: number;
  rolling_avg_lap_time: number;
  lap_delta: number;
  should_pit_soon: boolean;
  estimated_laps_to_pit: number;
  stint_length: number;
}
interface DriverStat {
  driver_number: number;
  total_laps: number;
  fastest_lap: number;
  avg_lap_time: number;
  avg_deg_rate: number;
  pit_flags: number;
}
interface RaceResult {
  driver_number: number;
  abbreviation: string;
  full_name: string;
  team: string;
  team_color: string;
  grid_position: number | null;
  finish_position: number | null;
  status: string;
  points: number;
  laps_completed: number;
  time: string;
  fastest_lap_time: string;
  fastest_lap_rank: number | null;
}
interface Incident {
  status: string;
  label: string;
}
interface LapPosition {
  Driver: string;
  DriverNumber: number;
  LapNumber: number;
  Position: number;
}
interface FastestLap {
  driver_number: number;
  driver_code: string;
  lap_number: number;
  lap_time_seconds: number;
  lap_time_formatted: string;
  avg_speed_kph: number;
  tyre_compound: string;
  rank: number;
}
interface Stint {
  stint: number;
  compound: string;
  start_lap: number;
  end_lap: number;
  lap_count: number;
}
interface TyreStrategy {
  driver_number: number;
  driver_code: string;
  stints: Stint[];
}
interface PitStop {
  driver_number: number;
  driver_id: string;
  driver_code: string;
  stop_number: number;
  lap: number;
  duration_seconds: number | null;
  duration_formatted: string;
  sd?: SessionDriver;
}

// ── Tokens ─────────────────────────────────────────────────────────────────
const C = {
  black: "#080808",
  dark: "#0e0e0e",
  card: "#131313",
  card2: "#181818",
  border: "#222222",
  border2: "#2e2e2e",
  red: "#e8002d",
  redDim: "#e8002d18",
  muted: "#555555",
  text: "#ffffff",
  text2: "#aaaaaa",
  gold: "#f5a623",
  silver: "#c0c0c0",
  bronze: "#cd7f32",
};
const yearColors: Record<number, string> = {
  2026: "#e8002d",
  2025: "#FF8000",
  2024: "#3671C6",
  2023: "#27F4D2",
};
const card: React.CSSProperties = {
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 4,
  padding: 24,
};

// ── Perceived-luminance helper ─────────────────────────────────────────────
// Returns true if bg is dark → use white text; false if light → use black text
function bgIsDark(hex: string): boolean {
  const h = hex.replace("#", "");
  if (h.length < 6) return true;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return 0.299 * r + 0.587 * g + 0.114 * b < 155;
}
function textOn(bg: string) {
  return bgIsDark(bg) ? "#ffffff" : "#111111";
}
function subOn(bg: string) {
  return bgIsDark(bg) ? "rgba(255,255,255,0.68)" : "rgba(0,0,0,0.55)";
}

// ── Shared grid strings (header + row MUST be identical) ───────────────────
// Results:    [driver 2.8fr] [team 1fr] [grid .55fr] [laps .55fr] [time 1fr] [status .9fr] [pts .45fr]
const R_COLS =
  "minmax(0,2.8fr) minmax(0,1fr) minmax(0,.55fr) minmax(0,.55fr) minmax(0,1fr) minmax(0,.9fr) minmax(0,.45fr)";
// FastestLap: [driver 2.8fr] [team 1fr] [time 1fr] [lapno .7fr] [tyre .7fr]
const FL_COLS =
  "minmax(0,2.8fr) minmax(0,1fr) minmax(0,1fr) minmax(0,.7fr) minmax(0,.7fr)";
// PitStops:   [driver 2.8fr] [team 1fr] [stopno .8fr] [lap .7fr] [dur 1fr]
const PS_COLS =
  "minmax(0,2.8fr) minmax(0,1fr) minmax(0,.8fr) minmax(0,.7fr) minmax(0,1fr)";

// left black cell is always exactly 60px wide, accounted for in the header by a 60px spacer.

// ── Helpers ────────────────────────────────────────────────────────────────
function statusLabel(s: string): { label: string; color: string } {
  if (!s || s === "Unknown") return { label: "—", color: C.muted };
  if (s === "Finished") return { label: "Finished", color: "#22c55e" };
  if (s.startsWith("+")) return { label: s, color: "#22c55e" };
  if (s === "Did Not Start" || s === "DNS")
    return { label: "DNS", color: "#ef4444" };
  if (s.includes("Lap") && !s.startsWith("+"))
    return { label: s, color: "#22c55e" };
  return { label: `DNF: ${s}`, color: "#f59e0b" };
}

// ── Small reusable components ──────────────────────────────────────────────
function AccentBar({ color }: { color?: string }) {
  return (
    <div
      style={{
        width: 32,
        height: 3,
        background: color || C.red,
        marginBottom: 14,
        borderRadius: 1,
      }}
    />
  );
}
function SectionTitle({
  children,
  sub,
  accent,
}: {
  children: React.ReactNode;
  sub?: string;
  accent?: string;
}) {
  return (
    <div style={{ marginBottom: 20 }}>
      <AccentBar color={accent} />
      <div
        style={{
          fontFamily: "'Barlow Condensed',sans-serif",
          fontWeight: 900,
          fontStyle: "italic",
          fontSize: 24,
          textTransform: "uppercase",
          letterSpacing: "0.02em",
          color: C.text,
          lineHeight: 1,
        }}
      >
        {children}
      </div>
      {/* {sub && (
        <div
          style={{
            fontSize: 14,
            color: C.muted,
            marginTop: 4,
            textTransform: "uppercase",
          }}
        >
          {sub}
        </div>
      )} */}
    </div>
  );
}
function InfoTip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-flex", marginLeft: 4 }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span
        style={{
          color: "#444",
          cursor: "help",
          fontSize: 10,
          border: "1px solid #333",
          borderRadius: "50%",
          width: 14,
          height: 14,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        ?
      </span>
      {show && (
        <span
          style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: "50%",
            transform: "translateX(-50%)",
            background: "#1a1a1a",
            color: "#ccc",
            fontSize: 11,
            padding: "6px 12px",
            borderRadius: 3,
            whiteSpace: "nowrap",
            zIndex: 200,
            border: `1px solid ${C.border2}`,
            pointerEvents: "none",
            boxShadow: "0 8px 24px #000a",
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}
function StatCard({
  label,
  value,
  red,
  tip,
  accent,
}: {
  label: string;
  value: string;
  red?: boolean;
  tip?: string;
  accent?: string;
}) {
  return (
    <div style={{ ...card, padding: 20, position: "relative" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(90deg,${
            accent || (red ? C.red : C.border2)
          },transparent)`,
        }}
      />
      <div
        style={{
          fontFamily: "'Barlow Condensed',sans-serif",
          fontWeight: 900,
          fontStyle: "italic",
          fontSize: 30,
          color: red ? C.red : C.text,
          lineHeight: 1,
          letterSpacing: "0.02em",
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: 14,
          color: C.muted,
          marginTop: 6,
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          fontFamily: "'Barlow Condensed',sans-serif",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
        }}
      >
        {label}
        {tip && <InfoTip text={tip} />}
      </div>
    </div>
  );
}
function TyreChip({ compound, small }: { compound: string; small?: boolean }) {
  const color = TYRE_COLORS[compound] || "#888";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        padding: small ? "1px 6px" : "2px 8px",
        borderRadius: 2,
        border: `1px solid ${color}66`,
        color,
        fontSize: small ? 10 : 11,
        fontFamily: "'Barlow Condensed',sans-serif",
        fontWeight: 700,
        letterSpacing: "0.08em",
        background: `${color}12`,
      }}
    >
      ● {compound}
    </span>
  );
}
function TyreChipContrast({ compound }: { compound: string }) {
  const TYRE: Record<string, string> = {
    SOFT: "#E8002D", MEDIUM: "#FFD700", HARD: "#EEEEEE",
    INTER: "#39B54A", INTERMEDIATE: "#39B54A", WET: "#0067FF",
  };
  const color = TYRE[compound] || "#888";
  const isHard = compound === "HARD";
  const displayColor = isHard ? "#000" : color;
  const bg = bgIsDark(displayColor) ? "#000" : "#000";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "2px 8px", borderRadius: 2,
      border: `1px solid ${color}`,
      color: color,
      fontSize: 11, fontFamily: "'Barlow Condensed',sans-serif",
      fontWeight: 700, letterSpacing: "0.08em",
      background: bg,
    }}>{compound}</span>
  );
}
function StatusBadge({ label, color }: { label: string; color: string }) {
  const bg = bgIsDark(color) ? "#000" : "#000";
  return (
    <span style={{
      fontFamily: "'Barlow Condensed',sans-serif", fontSize: 13, fontWeight: 700,
      letterSpacing: "0.08em", padding: "3px 10px", borderRadius: 2,
      border: `1px solid ${color}`,
      color: color,
      background: bg,
      whiteSpace: "nowrap", display: "inline-block",
    }}>{label}</span>
  );
}
function PitFlagBadge({ yes }: { yes: boolean }) {
  return (
    <span
      style={{
        fontFamily: "'Barlow Condensed',sans-serif",
        fontWeight: 700,
        fontSize: 11,
        letterSpacing: "0.1em",
        padding: "2px 8px",
        borderRadius: 2,
        color: yes ? C.red : "#22c55e",
        border: `1px solid ${yes ? C.red : "#22c55e"}66`,
        background: yes ? C.redDim : "#22c55e12",
      }}
    >
      {yes ? "⚠ PIT SOON" : "✓ STAY OUT"}
    </span>
  );
}
function DriverBadge({
  num,
  sd,
  active,
  raceStatus,
  onClick,
}: {
  num: number;
  sd?: SessionDriver;
  active: boolean;
  raceStatus?: { label: string; color: string };
  onClick: () => void;
}) {
  const [hov, setHov] = useState(false);
  const color = sd?.color || "#555";
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "7px 12px",
        borderRadius: 3,
        border: `1px solid ${active ? color : hov ? C.border2 : C.border}`,
        background: active ? `${color}18` : hov ? C.card2 : C.dark,
        cursor: "pointer",
        transition: "all 0.15s",
        color: active ? C.text : C.text2,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {active && (
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 2,
            background: color,
          }}
        />
      )}
      <span
        style={{
          fontFamily: "'Barlow Condensed',sans-serif",
          fontWeight: 900,
          fontStyle: "italic",
          fontSize: 20,
          color: active ? color : "#444",
          minWidth: 24,
          textAlign: "right",
          lineHeight: 1,
        }}
      >
        {num}
      </span>
      <div>
        <div
          style={{
            fontFamily: "'Barlow Condensed',sans-serif",
            fontSize: 14,
            fontWeight: 700,
            letterSpacing: "0.05em",
          }}
        >
          {sd?.code || `#${num}`}
        </div>
        <div style={{ fontSize: 11, color: C.muted, letterSpacing: "0.08em" }}>
          {sd?.team?.split(" ")[0] || "—"}
        </div>
      </div>
      {raceStatus &&
        raceStatus.label !== "Finished" &&
        !raceStatus.label.startsWith("+") &&
        raceStatus.label !== "—" && (
          <span
            style={{
              fontSize: 8,
              fontWeight: 700,
              fontFamily: "'Barlow Condensed',sans-serif",
              color: raceStatus.color,
              border: `1px solid ${raceStatus.color}66`,
              padding: "1px 4px",
              borderRadius: 2,
              letterSpacing: "0.08em",
            }}
          >
            {raceStatus.label.startsWith("DNF") ? "DNF" : raceStatus.label}
          </span>
        )}
    </button>
  );
}
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#111",
        border: `1px solid ${C.border2}`,
        borderRadius: 3,
        padding: "10px 14px",
        fontSize: 12,
        boxShadow: "0 12px 40px #000c",
      }}
    >
      <div
        style={{
          fontFamily: "'Barlow Condensed',sans-serif",
          color: C.red,
          fontWeight: 700,
          marginBottom: 6,
          fontSize: 14,
          letterSpacing: "0.05em",
        }}
      >
        LAP {label}
      </div>
      {payload.map((p: any, i: number) => (
        <div
          key={i}
          style={{
            color: p.color,
            display: "flex",
            justifyContent: "space-between",
            gap: 20,
            marginBottom: 2,
          }}
        >
          <span
            style={{
              fontFamily: "'Barlow Condensed',sans-serif",
              letterSpacing: "0.05em",
            }}
          >
            {p.name}
          </span>
          <span style={{ fontFamily: "monospace", fontWeight: 700 }}>
            {typeof p.value === "number"
              ? Number.isInteger(p.value)
                ? `P${p.value}`
                : `${p.value.toFixed(3)}s`
              : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}
function TabBtn({
  active,
  onClick,
  children,
  accent,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  accent?: string;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "14px 16px",
        fontSize: 15,
        fontWeight: 700,
        cursor: "pointer",
        background: "none",
        border: "none",
        whiteSpace: "nowrap",
        fontFamily: "'Barlow Condensed',sans-serif",
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        color: active ? C.text : hov ? C.text2 : C.muted,
        borderBottom: `2px solid ${active ? accent || C.red : "transparent"}`,
        transition: "all 0.15s",
      }}
    >
      {children}
    </button>
  );
}
function Sel({
  value,
  onChange,
  children,
  style,
}: {
  value: string | number;
  onChange: (v: string) => void;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        background: C.dark,
        border: `1px solid ${C.border}`,
        color: C.text,
        padding: "8px 12px",
        borderRadius: 3,
        fontSize: 13,
        fontFamily: "'Barlow Condensed',sans-serif",
        fontWeight: 600,
        letterSpacing: "0.05em",
        outline: "none",
        cursor: "pointer",
        width: "100%",
        ...style,
      }}
    >
      {children}
    </select>
  );
}
function ActionBtn({
  onClick,
  disabled,
  loading,
  children,
  accent,
}: {
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  children: React.ReactNode;
  accent?: string;
}) {
  const [hov, setHov] = useState(false);
  const bg = accent || C.red;
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "10px 20px",
        borderRadius: 3,
        fontFamily: "'Barlow Condensed',sans-serif",
        fontWeight: 700,
        fontSize: 13,
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled || loading ? 0.5 : 1,
        background: hov && !disabled && !loading ? bg : `${bg}cc`,
        color: C.text,
        border: `1px solid ${bg}`,
        display: "flex",
        alignItems: "center",
        gap: 8,
        width: "100%",
        justifyContent: "center",
        transition: "all 0.15s",
        boxShadow: hov && !disabled ? `0 4px 20px ${bg}30` : "none",
      }}
    >
      {loading && (
        <span
          style={{
            animation: "spin 1s linear infinite",
            display: "inline-block",
          }}
        >
          ⟳
        </span>
      )}
      {children}
    </button>
  );
}
function InfoRow({
  label,
  value,
  tip,
}: {
  label: string;
  value: React.ReactNode;
  tip?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "9px 0",
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <span
        style={{
          fontSize: 12,
          color: C.muted,
          fontFamily: "'Barlow Condensed',sans-serif",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          display: "flex",
          alignItems: "center",
        }}
      >
        {label}
        {tip && <InfoTip text={tip} />}
      </span>
      <span style={{ fontSize: 13, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

// ── F1-style coloured row ──────────────────────────────────────────────────
// The row is: [60px black left cell] + [coloured right section using CSS grid]
// IMPORTANT: the header must have the same structure: [60px spacer] + [same grid]
function F1Row({
  pos,
  posColor,
  rowColor,
  cols,
  children,
}: {
  pos: React.ReactNode;
  posColor?: string;
  rowColor: string;
  cols: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        marginBottom: 8,
        borderRadius: 4,
        overflow: "hidden",
        minWidth: 0,
      }}
    >
      {/* Left black position cell — fixed 60px */}
      <div
        style={{
          width: 60,
          minWidth: 60,
          flexShrink: 0,
          background: "#000",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 6px",
          minHeight: 62,
        }}
      >
        {pos}
      </div>
      {/* Coloured content area */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          background: rowColor,
          display: "grid",
          gridTemplateColumns: cols,
          alignItems: "center",
          padding: "10px 16px 10px 12px",
          gap: 12,
          minHeight: 62,
          overflow: "hidden",
        }}
      >
        {children}
      </div>
    </div>
  );
}

// Header row aligned to F1Row — 60px spacer + same grid + same padding
function F1Header({ cols, labels }: { cols: string; labels: string[] }) {
  return (
    <div style={{ display: "flex", marginBottom: 10 }}>
      <div style={{ width: 60, minWidth: 60, flexShrink: 0 }} />
      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: cols,
          padding: "0 16px 0 12px",
          gap: 12,
        }}
      >
        {labels.map((h) => (
          <div
            key={h}
            style={{
              fontFamily: "'Barlow Condensed',sans-serif",
              fontSize: 13,
              fontWeight: 700,
              color: C.muted,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              whiteSpace: "nowrap",
            }}
          >
            {h}
          </div>
        ))}
      </div>
    </div>
  );
}

function DriverName({
  // logo,
  team,
  full,
  sub,
  bgColor,
}: {
  // logo: string | null;
  team: string;
  full: string;
  sub?: string;
  bgColor: string;
}) {
  const fg = textOn(bgColor);
  const sub_ = subOn(bgColor);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      {/* <div
        style={{
          width: 48,
          minWidth: 48,
          height: 36,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          background: "rgba(0,0,0,0.22)",
          borderRadius: 3,
        }}
      >
        {logo && (
          <img
            src={logo}
            alt={team}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
            style={{
              maxWidth: 40,
              maxHeight: 28,
              objectFit: "contain",
              display: "block",
            }}
          />
        )}
      </div> */}
      <div style={{ minWidth: 0, flex: 1, paddingRight: 8 }}>
        <div
          style={{
            fontFamily: "'Barlow Condensed',sans-serif",
            fontWeight: 900,
            fontStyle: "italic",
            fontSize: 22,
            letterSpacing: "-0.01em",
            lineHeight: 1,
            color: fg,
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {full}
        </div>
        {/* {sub && (
          <div
            style={{
              fontFamily: "'Barlow Condensed',sans-serif",
              fontSize: 12,
              letterSpacing: "0.10em",
              color: sub_,
              marginTop: 3,
              textTransform: "uppercase",
              whiteSpace: "nowrap",
            }}
          >
            {sub}
          </div>
        )} */}
      </div>
    </div>
  );
}

// Generic cell for coloured rows
function Val({
  children,
  mono,
  size,
  bold,
  bgColor,
  override,
}: {
  children: React.ReactNode;
  mono?: boolean;
  size?: number;
  bold?: boolean;
  bgColor: string;
  override?: string;
}) {
  return (
    <div
      style={{
        fontFamily: mono ? "monospace" : "'Barlow Condensed',sans-serif",
        fontSize: size || 15,
        fontWeight: bold ? 700 : 400,
        color: override || textOn(bgColor),
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {children}
    </div>
  );
}

// ── Charts ─────────────────────────────────────────────────────────────────
function TyreStrategyChart({
  strategies,
  sdByNum,
  results,
  maxLap,
  selectedDrivers,
  accent,
}: {
  strategies: TyreStrategy[];
  sdByNum: Record<number, SessionDriver>;
  results: RaceResult[];
  maxLap: number;
  selectedDrivers: number[];
  accent: string;
}) {
  const filtered = strategies.filter((s) =>
    selectedDrivers.includes(s.driver_number)
  );
  const sorted = [...filtered].sort((a, b) => {
    const ra = results.find((r) => r.abbreviation === a.driver_code);
    const rb = results.find((r) => r.abbreviation === b.driver_code);
    return (ra?.finish_position || 99) - (rb?.finish_position || 99);
  });
  const rowH = 36,
    leftPad = 56,
    rightPad = 24,
    topPad = 20,
    chartW = 860;
  const totalH = sorted.length * rowH + topPad + 44;
  const usableW = chartW - leftPad - rightPad;
  const xPos = (lap: number) => leftPad + (lap / maxLap) * usableW;
  const CC: Record<string, string> = {
    SOFT: "#E8002D",
    MEDIUM: "#FFD700",
    HARD: "#EEEEEE",
    INTER: "#39B54A",
    WET: "#0067FF",
    UNKNOWN: "#444",
  };
  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={chartW} height={totalH} style={{ display: "block" }}>
        {Array.from({ length: Math.ceil(maxLap / 5) + 1 }, (_, i) => i * 5).map(
          (lap) => (
            <g key={lap}>
              <line
                x1={xPos(lap)}
                y1={topPad}
                x2={xPos(lap)}
                y2={totalH - 34}
                stroke="#1a1a1a"
                strokeWidth={1}
              />
              <text
                x={xPos(lap)}
                y={totalH - 14}
                fill={C.muted}
                fontSize={13}
                textAnchor="middle"
                fontFamily="'Barlow Condensed',sans-serif"
              >
                {lap}
              </text>
            </g>
          )
        )}
        {sorted.map((s, i) => {
          const y = topPad + i * rowH;
          const sd = sdByNum[s.driver_number];
          return (
            <g key={s.driver_number}>
              <text
                x={leftPad - 8}
                y={y + rowH / 2 + 5}
                fill={sd?.color || C.muted}
                fontSize={20}
                fontWeight="900"
                textAnchor="end"
                fontStyle="italic"
                fontFamily="'Barlow Condensed',sans-serif"
              >
                {s.driver_code}
              </text>
              <rect
                x={xPos(0)}
                y={y + 5}
                width={xPos(maxLap) - xPos(0)}
                height={rowH - 10}
                fill="#111"
                rx={2}
              />
              {s.stints.map((stint) => {
                const color = CC[stint.compound] || "#444";
                const x1 = xPos(stint.start_lap - 1);
                const x2 = xPos(stint.end_lap);
                const w = Math.max(x2 - x1, 2);
                const textDark =
                  stint.compound === "MEDIUM" || stint.compound === "HARD";
                return (
                  <g key={stint.stint}>
                    <rect
                      x={x1}
                      y={y + 5}
                      width={w}
                      height={rowH - 10}
                      fill={color}
                      fillOpacity={0.92}
                      rx={2}
                    />
                    {w > 20 && (
                      <text
                        x={x1 + w / 2}
                        y={y + rowH / 2 + 5}
                        fill={textDark ? "#111" : "#fff"}
                        fontSize={13}
                        fontWeight="900"
                        textAnchor="middle"
                        fontFamily="'Barlow Condensed',sans-serif"
                      >
                        {stint.compound[0]}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
        <text
          x={leftPad + usableW / 2}
          y={totalH - 2}
          fill={C.muted}
          fontSize={10}
          textAnchor="middle"
          fontFamily="'Barlow Condensed',sans-serif"
          letterSpacing="0.15em"
        >
          LAP
        </text>
      </svg>
      <div
        style={{ display: "flex", gap: 20, marginTop: 14, flexWrap: "wrap" }}
      >
        {Object.entries(CC)
          .filter(([k]) => k !== "UNKNOWN")
          .map(([compound, color]) => (
            <span
              key={compound}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <span
                style={{
                  width: 18,
                  height: 12,
                  borderRadius: 2,
                  background: color,
                  display: "inline-block",
                  border: "1px solid #333",
                }}
              />
              <span
                style={{
                  fontFamily: "'Barlow Condensed',sans-serif",
                  fontSize: 11,
                  color: C.muted,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                {compound}
              </span>
            </span>
          ))}
      </div>
    </div>
  );
}
function LapPositionChart({
  positions,
  sdByNum,
  selectedDrivers,
}: {
  positions: LapPosition[];
  sdByNum: Record<number, SessionDriver>;
  selectedDrivers: number[];
}) {
  const nums = [...new Set(positions.map((p) => p.DriverNumber))].filter((n) =>
    selectedDrivers.includes(n)
  );
  const maxLap = Math.max(...positions.map((p) => p.LapNumber));
  const data = Array.from({ length: maxLap }, (_, i) => {
    const lap = i + 1;
    const row: any = { lap };
    for (const num of nums) {
      const sd = sdByNum[num];
      const key = sd?.code || `D${num}`;
      const pos = positions.find(
        (p) => p.DriverNumber === num && p.LapNumber === lap
      );
      row[key] = pos ? pos.Position : null;
    }
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={420}>
      <LineChart
        data={data}
        margin={{ top: 5, right: 30, bottom: 25, left: 10 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#151515" />
        <XAxis
          dataKey="lap"
          stroke={C.muted}
          tick={{ fill: C.muted, fontSize: 11 }}
          label={{
            value: "LAP",
            fill: C.muted,
            fontSize: 11,
            position: "insideBottom",
            offset: -12,
            fontFamily: "'Barlow Condensed',sans-serif",
            letterSpacing: "0.15em",
          }}
        />
        <YAxis
          stroke={C.muted}
          tick={{ fill: C.muted, fontSize: 11 }}
          reversed
          domain={[1, 22]}
          label={{
            value: "POSITION",
            fill: C.muted,
            fontSize: 11,
            angle: -90,
            position: "insideLeft",
            offset: 12,
            fontFamily: "'Barlow Condensed',sans-serif",
          }}
          tickFormatter={(v) => `P${v}`}
        />
        <RechartTooltip content={<ChartTooltip />} />
        <Legend
          wrapperStyle={{
            color: C.muted,
            fontSize: 12,
            paddingTop: 16,
            fontFamily: "'Barlow Condensed',sans-serif",
          }}
        />
        {nums.map((n) => {
          const sd = sdByNum[n];
          return (
            <Line
              key={n}
              type="monotone"
              dataKey={sd?.code || `D${n}`}
              stroke={sd?.color || "#888"}
              dot={false}
              strokeWidth={2}
              connectNulls={false}
            />
          );
        })}
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────
export default function RacePage() {
  const params = useParams();
  const router = useRouter();
  const year = Number(params.year);
  const round = Number(params.round);
  const accent = yearColors[year] || C.red;

  const [calendar, setCalendar] = useState<CalendarRace[]>([]);
  const [laps, setLaps] = useState<LapRow[] | null>(null);
  const [driverStats, setDriverStats] = useState<DriverStat[]>([]);
  const [jolpicaByCode, setJolpica] = useState<Record<string, DriverInfo>>({});
  const [sdByNum, setSdByNum] = useState<Record<number, SessionDriver>>({});
  const [results, setResults] = useState<RaceResult[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [lapPositions, setLapPos] = useState<LapPosition[]>([]);
  const [fastestLaps, setFastestLaps] = useState<FastestLap[]>([]);
  const [tyreStrategies, setTyreStrats] = useState<TyreStrategy[]>([]);
  const [pitStops, setPitStops] = useState<PitStop[]>([]);
  const [selectedDrivers, setSelected] = useState<number[]>([]);
  const [tab, setTab] = useState<
    | "laps"
    | "positions"
    | "deg"
    | "tyre-strategy"
    | "results"
    | "fastest-laps"
    | "pit-stops"
    | "ai-strategy"
    | "commentary"
  >("laps");
  const [dataLoading, setDataLoading] = useState(true);
  const [stratDriver, setStratDriver] = useState(0);
  const [stratLap, setStratLap] = useState(30);
  const [stratResult, setStratResult] = useState("");
  const [stratLoading, setStratLoading] = useState(false);
  const [commResult, setCommResult] = useState("");
  const [commLoading, setCommLoading] = useState(false);

  const resultStatusMap: Record<number, { label: string; color: string }> = {};
  for (const r of results)
    resultStatusMap[r.driver_number] = statusLabel(r.status);

  function buildSdMap(
    fl: FastestLap[],
    pos: LapPosition[],
    ts: TyreStrategy[],
    jolpica: Record<string, DriverInfo>,
    raceResults: RaceResult[]
  ): Record<number, SessionDriver> {
    const map: Record<number, SessionDriver> = {};

    // Build code→result lookup from Jolpica (accurate name/team)
    const resultByCode: Record<string, RaceResult> = {};
    for (const r of raceResults) resultByCode[r.abbreviation] = r;

    // Collect pairs from FastF1 — these driver_numbers are the real car numbers
    const pairs: { num: number; code: string }[] = [];
    for (const f of fl)
      pairs.push({ num: f.driver_number, code: f.driver_code });
    for (const p of pos)
      if (!pairs.find((x) => x.num === p.DriverNumber))
        pairs.push({ num: p.DriverNumber, code: p.Driver });
    for (const t of ts)
      if (!pairs.find((x) => x.num === t.driver_number))
        pairs.push({ num: t.driver_number, code: t.driver_code });

    for (const { num, code } of pairs) {
      // Match by 3-letter code to Jolpica result — gets correct name and team
      const fromResult = resultByCode[code];
      map[num] = {
        race_number: num,
        code,
        full_name: fromResult?.full_name || jolpica[code]?.full_name || code,
        team: fromResult?.team || jolpica[code]?.team || "",
        color: getTeamColor(fromResult?.team || jolpica[code]?.team || ""),
      };
    }

    return map;
  }

  useEffect(() => {
    Promise.all([getCalendar(year), getDriversForYear(year)]).then(
      ([cal, dd]) => {
        setCalendar(cal?.races || []);
        if (dd?.drivers) {
          const m: Record<string, DriverInfo> = {};
          for (const d of dd.drivers) m[d.code] = d;
          setJolpica(m);
        }
      }
    );
  }, [year]);

  const load = useCallback(async () => {
    setDataLoading(true);
    setLaps(null);
    setDriverStats([]);
    setResults([]);
    setIncidents([]);
    setLapPos([]);
    setFastestLaps([]);
    setTyreStrats([]);
    setPitStops([]);
    setSdByNum({});
    const [l, s, res, inc, pos, fl, ts, ps] = await Promise.all([
      getLaps(year, round),
      getRaceDriverStats(year, round),
      getRaceResults(year, round),
      getRaceIncidents(year, round),
      getLapPositions(year, round),
      getFastestLaps(year, round),
      getTyreStrategies(year, round),
      getPitStops(year, round),
    ]);
    setLaps(l);
    setDriverStats(s || []);
    setResults(res?.results || []);
    setIncidents(inc?.incidents || []);
    setLapPos(Array.isArray(pos) ? pos : []);
    setFastestLaps(Array.isArray(fl) ? fl : []);
    setTyreStrats(Array.isArray(ts) ? ts : []);
    setPitStops(Array.isArray(ps) ? ps : []);
    if (l?.length) {
      const nums = [
        ...new Set(l.map((x: LapRow) => x.driver_number)),
      ] as number[];
      setSelected(nums.slice(0, 5));
      setStratDriver(nums[0]);
      setStratLap(
        Math.floor(Math.max(...l.map((x: LapRow) => x.lap_number)) / 2)
      );
    }
    setDataLoading(false);
  }, [year, round]);

  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    const m = buildSdMap(
      fastestLaps,
      lapPositions,
      tyreStrategies,
      jolpicaByCode,
      results
    );
    if (Object.keys(m).length > 0) setSdByNum(m);
  }, [fastestLaps, lapPositions, tyreStrategies, jolpicaByCode, results]);

  const handleStrategy = async () => {
    if (!laps) return;
    setStratLoading(true);
    setStratResult("");
    try {
      const row = laps.find(
        (l) => l.driver_number === stratDriver && l.lap_number === stratLap
      );
      if (!row) {
        setStratResult("No data for this lap.");
        return;
      }
      const circuitName =
        calendar.find((c) => c.round === round)?.name || "Unknown";
      const r = await getStrategy({
        driver_number: row.driver_number,
        lap_number: row.lap_number,
        lap_duration: row.lap_duration,
        tyre_compound: row.tyre_compound || "UNKNOWN",
        tyre_age_laps: row.tyre_age_laps || 0,
        tyre_degradation_rate: row.tyre_degradation_rate,
        rolling_avg_lap_time: row.rolling_avg_lap_time,
        lap_delta: row.lap_delta,
        should_pit_soon: row.should_pit_soon,
        estimated_laps_to_pit: row.estimated_laps_to_pit,
        circuit_name: circuitName,
        total_race_laps: Math.max(...laps.map((l) => l.lap_number)),
      });
      setStratResult(r?.recommendation || r?.detail || "Something went wrong. Try again.");
    } catch {
      setStratResult("Something went wrong. Try again.");
    } finally {
      setStratLoading(false);
    }
  };
  const handleCommentary = async () => {
    if (!laps) return;
    setCommLoading(true);
    setCommResult("");
    const row = laps.find(
      (l) => l.driver_number === stratDriver && l.lap_number === stratLap
    );
    if (!row) {
      setCommLoading(false);
      return;
    }
    const sd = sdByNum[row.driver_number];
    const r = await getCommentary({
      driver_name: sd?.full_name || `Driver ${row.driver_number}`,
      driver_number: row.driver_number,
      lap_number: row.lap_number,
      lap_duration: row.lap_duration,
      tyre_compound: row.tyre_compound || "UNKNOWN",
      tyre_age_laps: row.tyre_age_laps || 0,
      should_pit_soon: row.should_pit_soon,
      tyre_degradation_rate: row.tyre_degradation_rate,
    });
    setCommResult(r.commentary || "");
    setCommLoading(false);
  };

  const allNums = laps
    ? [...new Set(laps.map((l) => l.driver_number))].sort((a, b) => a - b)
    : [];
  const dnsNums = results
    .filter(
      (r) =>
        statusLabel(r.status).label === "DNS" &&
        !allNums.includes(r.driver_number)
    )
    .map((r) => r.driver_number);
  const allDriverNums = [...allNums, ...dnsNums];
  const maxLap = laps ? Math.max(...laps.map((l) => l.lap_number)) : 57;
  const currentRace = calendar.find((c) => c.round === round);

  const chartData = (() => {
    if (!laps) return [];
    const map: Record<number, any> = {};
    laps
      .filter((l) => selectedDrivers.includes(l.driver_number))
      .forEach((l) => {
        if (!map[l.lap_number]) map[l.lap_number] = { lap: l.lap_number };
        const sd = sdByNum[l.driver_number];
        const key = sd?.code || `D${l.driver_number}`;
        map[l.lap_number][key] = l.lap_duration > 0 ? l.lap_duration : null;
        map[l.lap_number][`${key}_deg`] =
          l.tyre_degradation_rate > 0 && l.tyre_degradation_rate < 0.8
            ? l.tyre_degradation_rate
            : null;
      });
    return Object.values(map).sort((a: any, b: any) => a.lap - b.lap);
  })();

  const dnfAnnotations = selectedDrivers
    .filter((n) => resultStatusMap[n]?.label.startsWith("DNF"))
    .map((n) => {
      const dl = laps?.filter((l) => l.driver_number === n) || [];
      const lastLap = dl.length
        ? Math.max(...dl.map((l) => l.lap_number))
        : null;
      const sd = sdByNum[n];
      return {
        num: n,
        lastLap,
        code: sd?.code || `D${n}`,
        color: sd?.color || "#888",
      };
    })
    .filter((d) => d.lastLap !== null);

  const selectedRow = laps?.find(
    (l) => l.driver_number === stratDriver && l.lap_number === stratLap
  );

  const enrichedPitStops: PitStop[] = pitStops.map(ps => {
    let sd: SessionDriver | undefined;
  
    // Priority 1: match by driver_code (3-letter) — same as fastest laps, most reliable
    if (ps.driver_code) {
      sd = Object.values(sdByNum).find(s => s.code === ps.driver_code.toUpperCase());
    }
  
    // Priority 2: match by driver_id slug against full names in sdByNum
    if (!sd && ps.driver_id) {
      const slug = ps.driver_id.toLowerCase().replace(/_/g, "");
      sd = Object.values(sdByNum).find(s => {
        const fullSlug = s.full_name.toLowerCase().replace(/\s/g, "");
        const surname = s.full_name.split(" ").pop()?.toLowerCase() || "";
        const firstname = s.full_name.split(" ")[0]?.toLowerCase() || "";
        return (
          fullSlug === slug ||
          slug === firstname + surname ||
          slug.includes(surname) ||
          s.code.toLowerCase() === ps.driver_id.toLowerCase()
        );
      });
    }
  
    // Priority 3: match by driver_number directly
    if (!sd) {
      sd = sdByNum[ps.driver_number];
    }
  
    // Priority 4: match driver_id against results by surname
    if (!sd && ps.driver_id) {
      const slug = ps.driver_id.toLowerCase().replace(/_/g, "");
      const mr = results.find(r => {
        const full = r.full_name.toLowerCase().replace(/\s/g, "");
        const surname = r.full_name.split(" ").pop()?.toLowerCase() || "";
        return full === slug || slug.includes(surname) || r.abbreviation.toLowerCase() === ps.driver_id.toLowerCase();
      });
      if (mr) {
        // Find in sdByNum by abbreviation
        sd = Object.values(sdByNum).find(s => s.code === mr.abbreviation);
      }
    }
  
    return { ...ps, sd, driver_number: sd?.race_number || ps.driver_number };
  });

  const fastestStopDur = (() => {
    const v = enrichedPitStops.filter(
      (p) =>
        p.duration_seconds && p.duration_seconds > 1 && p.duration_seconds < 60
    );
    return v.length ? Math.min(...v.map((p) => p.duration_seconds!)) : null;
  })();
  function sdForResult(r: RaceResult) {
    return (
      Object.values(sdByNum).find((s) => s.code === r.abbreviation) ||
      sdByNum[r.driver_number]
    );
  }
  return (
    <div style={{ minHeight: "100vh", background: C.black }}>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}@keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}`}</style>

      {/* ── Header ── */}
      <header
        style={{
          borderBottom: `1px solid ${C.border}`,
          background: `${C.dark}ee`,
          backdropFilter: "blur(20px)",
          position: "sticky",
          top: 0,
          zIndex: 50,
        }}
      >
        <div
          style={{
            maxWidth: 1400,
            margin: "0 auto",
            padding: "0 24px",
            height: 64,
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}
        >
          <button
            onClick={() => router.push(`/${year}`)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontFamily: "'Barlow Condensed',sans-serif",
              fontSize: 16,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              transition: "color 0.15s",
              color: C.muted,
              padding: "4px 0",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = C.text)}
            onMouseLeave={(e) => (e.currentTarget.style.color = C.muted)}
          >
            <ArrowLeft size={16} style={{ color: accent }} /> RACES
          </button>
          <div style={{ width: 1, height: 24, background: C.border }} />
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                background: accent,
                padding: "5px 14px",
                fontFamily: "'Barlow Condensed',sans-serif",
                fontWeight: 900,
                fontStyle: "italic",
                fontSize: 24,
                letterSpacing: "-0.02em",
              }}
            >
              {year}
            </div>
            <div
              style={{
                fontFamily: "'Barlow Condensed',sans-serif",
                fontWeight: 700,
                fontSize: 18,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: C.text2,
              }}
            >
              Formula 1 World Championship
            </div>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1440, margin: "0 auto", padding: "32px 28px" }}>
        {/* Loading */}
        {dataLoading && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: 400,
              gap: 16,
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                border: `2px solid ${C.border}`,
                borderTop: `2px solid ${accent}`,
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
              }}
            />
            <div
              style={{
                fontFamily: "'Barlow Condensed',sans-serif",
                fontSize: 13,
                color: C.muted,
                letterSpacing: "0.2em",
              }}
            >
              LOADING RACE DATA…
            </div>
          </div>
        )}

        {/* No data */}
        {!dataLoading && !laps && (
          <div
            style={{
              ...card,
              textAlign: "center",
              padding: 80,
              maxWidth: 520,
              margin: "80px auto",
            }}
          >
            <div style={{ fontSize: 56, marginBottom: 20 }}>🏎</div>
            <AccentBar color={accent} />
            <div
              style={{
                fontFamily: "'Barlow Condensed',sans-serif",
                fontWeight: 900,
                fontStyle: "italic",
                fontSize: 28,
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              No Data Available
            </div>
            <p
              style={{
                color: C.text2,
                fontSize: 14,
                marginBottom: 8,
                lineHeight: 1.6,
              }}
            >
              <strong style={{ color: C.text }}>
                {year} {currentRace?.full_name || `Round ${round}`}
              </strong>
            </p>
            <p
              style={{
                color: C.muted,
                fontSize: 13,
                marginBottom: 32,
                lineHeight: 1.6,
              }}
            >
              Go back to the season page and click{" "}
              <strong style={{ color: accent }}>LOAD DATA</strong> on this race
              card.
            </p>
            <ActionBtn onClick={() => router.push(`/${year}`)} accent={accent}>
              <ArrowLeft size={16} /> BACK TO {year} SEASON
            </ActionBtn>
          </div>
        )}

        {/* ── Race content ── */}
        {!dataLoading && laps && (
          <>
            {/* Title */}
            <div
              style={{ marginBottom: 36, animation: "slideUp 0.4s ease both" }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: 16,
                }}
              >
                <div>
                  <div
                    style={{
                      fontFamily: "'Barlow Condensed',sans-serif",
                      fontWeight: 900,
                      fontStyle: "italic",
                      fontSize: "clamp(40px,6vw,80px)",
                      lineHeight: 0.9,
                      textTransform: "uppercase",
                      letterSpacing: "-0.02em",
                    }}
                  >
                    <span style={{ color: C.text }}>
                      {currentRace?.name || `Round ${round}`}{" "}
                    </span>
                    <span style={{ color: accent }}>Grand Prix</span>
                  </div>
                  <div
                    style={{
                      height: 3,
                      width: 60,
                      background: accent,
                      marginTop: 10,
                    }}
                  />
                  {currentRace && (
                    <div
                      style={{
                        fontFamily: "'Barlow Condensed',sans-serif",
                        fontSize: 16,
                        color: "white",
                        marginTop: 8,
                        letterSpacing: "0.08em",
                      }}
                    >
                      {currentRace.circuit} · {currentRace.locality},{" "}
                      {currentRace.country}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 1 }}>
                  {[
                    { label: "LAPS", value: `${maxLap}` },
                    { label: "PIT STOPS", value: `${enrichedPitStops.length}` },
                  ].map((s, i) => (
                    <div
                      key={s.label}
                      style={{
                        background: i === 0 ? accent : C.card,
                        border: `1px solid ${i === 0 ? accent : C.border}`,
                        padding: "12px 20px",
                        textAlign: "center",
                        minWidth: 80,
                        borderRadius: i === 0 ? "3px 0 0 3px" : "0 3px 3px 0",
                      }}
                    >
                      <div
                        style={{
                          fontFamily: "'Barlow Condensed',sans-serif",
                          fontWeight: 900,
                          fontStyle: "italic",
                          fontSize: 28,
                          lineHeight: 1,
                          color:
                            i === 0
                              ? accent === C.red
                                ? "#fff"
                                : C.black
                              : C.text,
                        }}
                      >
                        {s.value}
                      </div>
                      <div
                        style={{
                          fontFamily: "'Barlow Condensed',sans-serif",
                          fontSize: 14,
                          letterSpacing: "0.15em",
                          marginTop: 2,
                          color:
                            i === 0
                              ? accent === C.red
                                ? "#fff9"
                                : C.black + "99"
                              : C.muted,
                        }}
                      >
                        {s.label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Stat cards */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4,1fr)",
                gap: 8,
                marginBottom: 20,
              }}
            >
              <StatCard
                label="Fastest Lap"
                value={fastestLaps[0] ? fastestLaps[0].lap_time_formatted : "—"}
                accent={accent}
              />
              <StatCard
                label="Race Winner"
                value={
                  results.find((r) => r.finish_position === 1)?.abbreviation ||
                  "—"
                }
                accent={accent}
              />
              <StatCard
                label="Pit Flags"
                value={laps.filter((l) => l.should_pit_soon).length.toString()}
                red
                tip="Laps where tyre degradation > 0.15s/lap"
              />
              <StatCard
                label="Avg Tyre Deg"
                value={(() => {
                  const v = laps.filter(
                    (l) =>
                      l.tyre_degradation_rate > 0 && l.tyre_degradation_rate < 2
                  );
                  return `${(
                    v.reduce((s, l) => s + l.tyre_degradation_rate, 0) /
                    Math.max(1, v.length)
                  ).toFixed(4)}s`;
                })()}
                accent={accent}
                tip="Avg seconds per lap lost to tyre wear"
              />
            </div>

            {/* Driver selector */}
            <div style={{ ...card, marginBottom: 12, padding: "14px 16px" }}>
              <div
                style={{
                  fontFamily: "'Barlow Condensed',sans-serif",
                  fontSize: 13,
                  color: C.muted,
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  marginBottom: 10,
                }}
              >
                COMPARE DRIVERS · CLICK TO TOGGLE
                {dnsNums.length > 0 && (
                  <span style={{ color: "#ef4444", marginLeft: 12 }}>
                    · DNS CANNOT BE PLOTTED
                  </span>
                )}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {allDriverNums.map((n) => (
                  <DriverBadge
                    key={n}
                    num={n}
                    sd={sdByNum[n]}
                    active={selectedDrivers.includes(n)}
                    raceStatus={resultStatusMap[n]}
                    onClick={() => {
                      if (dnsNums.includes(n)) return;
                      setSelected((p) =>
                        p.includes(n) ? p.filter((x) => x !== n) : [...p, n]
                      );
                    }}
                  />
                ))}
              </div>
            </div>

            {/* Tab bar */}
            <div
              style={{
                borderBottom: `1px solid ${C.border}`,
                marginBottom: 20,
                display: "flex",
                overflowX: "auto",
              }}
            >
              {(
                [
                  ["laps", "LAP TIMES"],
                  ["positions", "LAP CHART"],
                  ["deg", "TYRE DEG"],
                  ["tyre-strategy", "STRATEGIES"],
                  ["results", "RESULTS"],
                  ["fastest-laps", "FASTEST LAPS"],
                  ["pit-stops", "PIT STOPS"],
                  ["ai-strategy", "AI STRATEGY"],
                  ["commentary", "COMMENTARY"],
                ] as [string, string][]
              ).map(([key, label]) => (
                <TabBtn
                  key={key}
                  active={tab === key}
                  onClick={() => setTab(key as any)}
                  accent={accent}
                >
                  {label}
                </TabBtn>
              ))}
            </div>

            {/* ── LAP TIMES ── */}
            {tab === "laps" && (
              <div style={card}>
                <SectionTitle
                  accent={accent}
                  sub="Each line = one driver's lap times. Spikes = pit out-laps / safety car. DNF drivers shown as dashed lines."
                >
                  Lap Time Comparison
                </SectionTitle>
                {results.filter((r) => {
                  const s = statusLabel(r.status);
                  return (
                    s.label !== "Finished" &&
                    !s.label.startsWith("+") &&
                    s.label !== "—"
                  );
                }).length > 0 && (
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 6,
                      marginBottom: 16,
                    }}
                  >
                    {results
                      .filter((r) => {
                        const s = statusLabel(r.status);
                        return (
                          s.label !== "Finished" &&
                          !s.label.startsWith("+") &&
                          s.label !== "—"
                        );
                      })
                      .map((r) => {
                        const s = statusLabel(r.status);
                        const sd = sdForResult(r);
                        return (
                          <span
                            key={r.driver_number}
                            style={{
                              fontFamily: "'Barlow Condensed',sans-serif",
                              fontSize: 11,
                              padding: "2px 8px",
                              borderRadius: 2,
                              border: `1px solid ${s.color}66`,
                              color: s.color,
                              background: `${s.color}10`,
                              fontWeight: 700,
                              letterSpacing: "0.08em",
                            }}
                          >
                            {sd?.code || r.abbreviation} {s.label}
                            {r.laps_completed > 0
                              ? ` (LAP ${r.laps_completed})`
                              : ""}
                          </span>
                        );
                      })}
                  </div>
                )}
                {selectedDrivers.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 60,
                      color: C.muted,
                      fontFamily: "'Barlow Condensed',sans-serif",
                      letterSpacing: "0.15em",
                    }}
                  >
                    SELECT DRIVERS ABOVE
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={420}>
                    <LineChart
                      data={chartData}
                      margin={{ top: 5, right: 30, bottom: 25, left: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#151515" />
                      <XAxis
                        dataKey="lap"
                        stroke={C.muted}
                        tick={{ fill: C.muted, fontSize: 11 }}
                        label={{
                          value: "LAP",
                          fill: C.muted,
                          fontSize: 11,
                          position: "insideBottom",
                          offset: -12,
                          fontFamily: "'Barlow Condensed',sans-serif",
                          letterSpacing: "0.15em",
                        }}
                      />
                      <YAxis
                        stroke={C.muted}
                        tick={{ fill: C.muted, fontSize: 11 }}
                        domain={["auto", "auto"]}
                        label={{
                          value: "LAP TIME (s)",
                          fill: C.muted,
                          fontSize: 11,
                          angle: -90,
                          position: "insideLeft",
                          offset: 12,
                          fontFamily: "'Barlow Condensed',sans-serif",
                        }}
                      />
                      <RechartTooltip content={<ChartTooltip />} />
                      <Legend
                        wrapperStyle={{
                          color: C.muted,
                          fontSize: 11,
                          paddingTop: 16,
                          fontFamily: "'Barlow Condensed',sans-serif",
                          letterSpacing: "0.08em",
                        }}
                      />
                      {dnfAnnotations.map((d) => (
                        <ReferenceLine
                          key={d.num}
                          x={d.lastLap!}
                          stroke={d.color}
                          strokeDasharray="4 4"
                          strokeOpacity={0.5}
                          label={{
                            value: `${d.code} DNF`,
                            fill: d.color,
                            fontSize: 10,
                            position: "top",
                            fontFamily: "'Barlow Condensed',sans-serif",
                          }}
                        />
                      ))}
                      {selectedDrivers.map((n) => {
                        const sd = sdByNum[n];
                        const key = sd?.code || `D${n}`;
                        const isDNF =
                          resultStatusMap[n]?.label.startsWith("DNF");
                        return (
                          <Line
                            key={n}
                            type="monotone"
                            dataKey={key}
                            name={key}
                            stroke={sd?.color || "#888"}
                            dot={false}
                            strokeWidth={isDNF ? 1.5 : 2}
                            strokeDasharray={isDNF ? "4 2" : undefined}
                            connectNulls={false}
                          />
                        );
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            )}

            {/* ── LAP CHART ── */}
            {tab === "positions" && (
              <div style={card}>
                <SectionTitle
                  accent={accent}
                  sub="Position on every lap. P1 at top."
                >
                  Lap Chart — Race Positions
                </SectionTitle>
                {lapPositions.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 60,
                      color: C.muted,
                      fontFamily: "'Barlow Condensed',sans-serif",
                      letterSpacing: "0.15em",
                    }}
                  >
                    POSITION DATA NOT AVAILABLE
                  </div>
                ) : selectedDrivers.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 60,
                      color: C.muted,
                      fontFamily: "'Barlow Condensed',sans-serif",
                      letterSpacing: "0.15em",
                    }}
                  >
                    SELECT DRIVERS ABOVE
                  </div>
                ) : (
                  <LapPositionChart
                    positions={lapPositions}
                    sdByNum={sdByNum}
                    selectedDrivers={selectedDrivers}
                  />
                )}
              </div>
            )}

            {/* ── TYRE DEG ── */}
            {tab === "deg" && (
              <div
                style={{ display: "flex", flexDirection: "column", gap: 12 }}
              >
                <div style={card}>
                  <SectionTitle
                    accent={accent}
                    sub="Seconds per lap lost to tyre wear. Above the red line = AI flags a pit stop."
                  >
                    Tyre Degradation Rate
                  </SectionTitle>
                  <ResponsiveContainer width="100%" height={340}>
                    <LineChart
                      data={chartData}
                      margin={{ top: 5, right: 30, bottom: 25, left: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#151515" />
                      <XAxis
                        dataKey="lap"
                        stroke={C.muted}
                        tick={{ fill: C.muted, fontSize: 11 }}
                        label={{
                          value: "LAP",
                          fill: C.muted,
                          fontSize: 11,
                          position: "insideBottom",
                          offset: -12,
                          fontFamily: "'Barlow Condensed',sans-serif",
                          letterSpacing: "0.15em",
                        }}
                      />
                      <YAxis
                        stroke={C.muted}
                        tick={{ fill: C.muted, fontSize: 11 }}
                        domain={[0, 0.6]}
                        allowDataOverflow={true}
                        label={{
                          value: "DEG (s/lap)",
                          fill: C.muted,
                          fontSize: 11,
                          angle: -90,
                          position: "insideLeft",
                          offset: 12,
                          fontFamily: "'Barlow Condensed',sans-serif",
                        }}
                      />
                      <RechartTooltip content={<ChartTooltip />} />
                      <ReferenceLine
                        y={0.15}
                        stroke={C.red}
                        strokeDasharray="5 5"
                        label={{
                          value: "PIT THRESHOLD 0.15s/lap",
                          fill: C.red,
                          fontSize: 9,
                          position: "right",
                          fontFamily: "'Barlow Condensed',sans-serif",
                          letterSpacing: "0.1em",
                        }}
                      />
                      <Legend
                        wrapperStyle={{
                          color: C.muted,
                          fontSize: 11,
                          paddingTop: 16,
                          fontFamily: "'Barlow Condensed',sans-serif",
                        }}
                      />
                      {selectedDrivers.map((n) => {
                        const sd = sdByNum[n];
                        const key = sd?.code || `D${n}`;
                        return (
                          <Line
                            key={n}
                            type="monotone"
                            dataKey={`${key}_deg`}
                            name={key}
                            stroke={sd?.color || "#888"}
                            dot={false}
                            strokeWidth={1.5}
                            connectNulls={false}
                          />
                        );
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))",
                    gap: 8,
                  }}
                >
                  {driverStats
                    .filter((d) => selectedDrivers.includes(d.driver_number))
                    .sort((a, b) => b.avg_deg_rate - a.avg_deg_rate)
                    .map((d) => {
                      const sd = sdByNum[d.driver_number];
                      const high = d.avg_deg_rate > 0.15;
                      const rs = resultStatusMap[d.driver_number];
                      return (
                        <div
                          key={d.driver_number}
                          style={{
                            ...card,
                            padding: 16,
                            position: "relative",
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              position: "absolute",
                              top: 0,
                              left: 0,
                              right: 0,
                              height: 2,
                              background: sd?.color || C.border,
                            }}
                          />
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "flex-start",
                              marginBottom: 8,
                            }}
                          >
                            <span
                              style={{
                                fontFamily: "'Barlow Condensed',sans-serif",
                                fontWeight: 900,
                                fontStyle: "italic",
                                fontSize: 28,
                                color: sd?.color || "#888",
                                lineHeight: 1,
                              }}
                            >
                              {d.driver_number}
                            </span>
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 3,
                                alignItems: "flex-end",
                              }}
                            >
                              {high && (
                                <span
                                  style={{
                                    fontFamily: "'Barlow Condensed',sans-serif",
                                    fontSize: 8,
                                    color: C.red,
                                    border: `1px solid ${C.red}66`,
                                    padding: "2px 5px",
                                    borderRadius: 2,
                                    letterSpacing: "0.1em",
                                  }}
                                >
                                  HIGH WEAR
                                </span>
                              )}
                              {rs &&
                                rs.label !== "Finished" &&
                                !rs.label.startsWith("+") && (
                                  <span
                                    style={{
                                      fontFamily:
                                        "'Barlow Condensed',sans-serif",
                                      fontSize: 8,
                                      color: rs.color,
                                      border: `1px solid ${rs.color}66`,
                                      padding: "2px 5px",
                                      borderRadius: 2,
                                      letterSpacing: "0.1em",
                                    }}
                                  >
                                    {rs.label.startsWith("DNF")
                                      ? "DNF"
                                      : rs.label}
                                  </span>
                                )}
                            </div>
                          </div>
                          <div
                            style={{
                              fontFamily: "'Barlow Condensed',sans-serif",
                              fontWeight: 700,
                              fontSize: 14,
                              letterSpacing: "0.05em",
                            }}
                          >
                            {sd?.code || `D${d.driver_number}`}
                          </div>
                          <div
                            style={{
                              fontFamily: "'Barlow Condensed',sans-serif",
                              fontSize: 13,
                              color: C.muted,
                              marginBottom: 5,
                              letterSpacing: "0.05em",
                            }}
                          >
                            {sd?.team || "—"}
                          </div>
                          <div
                            style={{
                              fontFamily: "'Barlow Condensed',sans-serif",
                              fontWeight: 900,
                              fontStyle: "italic",
                              fontSize: 22,
                              color: high ? C.red : C.text,
                            }}
                          >
                            {d.avg_deg_rate?.toFixed(4)}s
                          </div>
                          <div
                            style={{
                              fontFamily: "'Barlow Condensed',sans-serif",
                              fontSize: 11,
                              color: C.muted,
                              letterSpacing: "0.12em",
                            }}
                          >
                            AVG PER LAP
                          </div>
                          <div
                            style={{
                              marginTop: 8,
                              fontFamily: "'Barlow Condensed',sans-serif",
                              fontSize: 13,
                            }}
                          >
                            Pit flags:{" "}
                            <strong style={{ color: C.red }}>
                              {d.pit_flags}
                            </strong>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            {/* ── TYRE STRATEGY ── */}
            {tab === "tyre-strategy" && (
              <div style={card}>
                <SectionTitle
                  accent={accent}
                  sub="Compound and stint length per driver, sorted by finish position."
                >
                  Tyre Strategies
                </SectionTitle>
                {tyreStrategies.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 60,
                      color: C.muted,
                      fontFamily: "'Barlow Condensed',sans-serif",
                      letterSpacing: "0.15em",
                    }}
                  >
                    NO DATA AVAILABLE
                  </div>
                ) : selectedDrivers.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 60,
                      color: C.muted,
                      fontFamily: "'Barlow Condensed',sans-serif",
                      letterSpacing: "0.15em",
                    }}
                  >
                    SELECT DRIVERS
                  </div>
                ) : (
                  <TyreStrategyChart
                    strategies={tyreStrategies}
                    sdByNum={sdByNum}
                    results={results}
                    maxLap={maxLap}
                    selectedDrivers={selectedDrivers}
                    accent={accent}
                  />
                )}
              </div>
            )}

            {/* ── RACE RESULTS ── */}
            {tab === "results" && (
              <div
                style={{ display: "flex", flexDirection: "column", gap: 12 }}
              >
                <div style={card}>
                  <SectionTitle
                    accent={accent}
                    sub="Grid, finish position, status, fastest lap, and points."
                  >
                    Race Results
                  </SectionTitle>
                  {results.length === 0 ? (
                    <div
                      style={{
                        textAlign: "center",
                        padding: 48,
                        color: C.muted,
                        fontFamily: "'Barlow Condensed',sans-serif",
                        letterSpacing: "0.15em",
                      }}
                    >
                      RESULTS NOT YET AVAILABLE
                    </div>
                  ) : (
                    <div>
                      <F1Header
                        cols={R_COLS}
                        labels={[
                          "Driver",
                          "Team",
                          "Grid",
                          "Laps",
                          "Time / Gap",
                          "Status",
                          "Pts",
                        ]}
                      />
                      {results.map((r, i) => {
                        const sd = sdForResult(r);
                        const color = sd?.color || getTeamColor(r.team || "");
                        // const logo = getTeamLogo(r.team || "");
                        const s = statusLabel(r.status);
                        const isDNS = s.label === "DNS";
                        const podium = [C.gold, C.silver, C.bronze];
                        return (
                          <F1Row
                            key={i}
                            cols={R_COLS}
                            rowColor={color}
                            pos={
                              <span
                                style={{
                                  fontFamily: "'Barlow Condensed',sans-serif",
                                  fontWeight: 900,
                                  fontStyle: "italic",
                                  fontSize: 26,
                                  color: isDNS
                                    ? "#ef4444"
                                    : i < 3
                                    ? podium[i]
                                    : C.text,
                                  lineHeight: 1,
                                }}
                              >
                                {isDNS ? "DNS" : r.finish_position || "—"}
                              </span>
                            }
                          >
                            <DriverName
                              // logo={logo}
                              team={r.team}
                              full={r.full_name}
                              sub={r.abbreviation}
                              bgColor={color}
                            />
                            <Val bgColor={color}>
                              <span
                                style={{
                                  fontFamily: "'Barlow Condensed',sans-serif",
                                  fontSize: 14,
                                  fontWeight: 700,
                                }}
                              >
                                {r.team}
                              </span>
                            </Val>
                            <Val bgColor={color} mono size={15}>
                              {isDNS ? "—" : r.grid_position || "—"}
                            </Val>
                            <Val bgColor={color} mono size={15}>
                              {r.laps_completed || "—"}
                            </Val>
                            <Val bgColor={color} mono size={15}>
                              {r.time || "—"}
                            </Val>
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                                minWidth: 0,
                              }}
                            >
                              <StatusBadge
                                label={s.label}
                                color={s.color}
                                // bgColor={color}
                              />
                              {r.fastest_lap_rank === 1 && (
                                <span
                                  style={{
                                    fontSize: 10,
                                    color: "#a855f7",
                                    background: "#000",
                                    border: "1px solid #a855f766",
                                    padding: "1px 5px",
                                    borderRadius: 2,
                                    fontFamily: "'Barlow Condensed',sans-serif",
                                    letterSpacing: "0.08em",
                                    whiteSpace: "nowrap",
                                    flexShrink: 0,
                                  }}
                                >
                                FL
                                </span>
                              )}
                            </div>
                            {/* Points — black/white based on bg, uses accent colour for non-zero */}
                            <Val bgColor={color}>
                              <span
                                style={{
                                  fontFamily: "'Barlow Condensed',sans-serif",
                                  fontWeight: 900,
                                  fontStyle: "italic",
                                  fontSize: 22,
                                  lineHeight: 1,
                                  color:
                                    r.points > 0 ? textOn(color) : subOn(color),
                                }}
                              >
                                {r.points > 0 ? r.points : "—"}
                              </span>
                            </Val>
                          </F1Row>
                        );
                      })}
                    </div>
                  )}
                  {incidents.length > 0 && (
                    <div
                      style={{ ...card, padding: "12px 16px", marginTop: 16 }}
                    >
                      <div
                        style={{
                          fontFamily: "'Barlow Condensed',sans-serif",
                          fontSize: 13,
                          color: C.muted,
                          letterSpacing: "0.2em",
                          marginBottom: 8,
                        }}
                      >
                        RACE INCIDENTS
                      </div>
                      <div
                        style={{ display: "flex", flexWrap: "wrap", gap: 8 }}
                      >
                        {incidents.map((inc, i) => {
                          const ic =
                            inc.status === "5"
                              ? "#ef4444"
                              : inc.status === "4"
                              ? "#f59e0b"
                              : "#eab308";
                          return (
                            <span
                              key={i}
                              style={{
                                fontFamily: "'Barlow Condensed',sans-serif",
                                fontSize: 14,
                                fontWeight: 700,
                                letterSpacing: "0.12em",
                                padding: "3px 10px",
                                borderRadius: 2,
                                border: `1px solid ${ic}66`,
                                color: ic,
                                background: `${ic}10`,
                              }}
                            >
                              {inc.label}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── FASTEST LAPS ── */}
            {tab === "fastest-laps" && (
              <div style={card}>
                <SectionTitle
                  accent={accent}
                  sub="Each driver's personal fastest lap."
                >
                  Fastest Laps
                </SectionTitle>
                {fastestLaps.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 48,
                      color: C.muted,
                      fontFamily: "'Barlow Condensed',sans-serif",
                      letterSpacing: "0.15em",
                    }}
                  >
                    NO DATA AVAILABLE
                  </div>
                ) : (
                  <div>
                    <F1Header
                      cols={FL_COLS}
                      labels={["Driver", "Team", "Lap Time", "Lap No.", "Tyre"]}
                    />
                    {fastestLaps.map((fl, i) => {
                      const sd = sdByNum[fl.driver_number];
                      const color = sd?.color || "#888";
                      // const logo = getTeamLogo(sd?.team || "");
                      return (
                        <F1Row
                          key={i}
                          cols={FL_COLS}
                          rowColor={color}
                          pos={
                            <span
                              style={{
                                fontFamily: "'Barlow Condensed',sans-serif",
                                fontWeight: 900,
                                fontStyle: "italic",
                                fontSize: 26,
                                color: fl.rank === 1 ? "#a855f7" : C.text,
                                lineHeight: 1,
                              }}
                            >
                              {fl.rank}
                            </span>
                          }
                        >
                          <DriverName
                            // logo={logo}
                            team={sd?.team || ""}
                            full={sd?.full_name || fl.driver_code}
                            sub={fl.driver_code}
                            bgColor={color}
                          />
                          <Val bgColor={color}>
                            <span
                              style={{
                                fontFamily: "'Barlow Condensed',sans-serif",
                                fontSize: 14,
                                fontWeight: 700,
                              }}
                            >
                              {sd?.team || "—"}
                            </span>
                          </Val>
                          <Val
                            bgColor={color}
                            mono
                            bold
                            size={16}
                            override={fl.rank === 1 ? "#a855f7" : undefined}
                          >
                            {fl.lap_time_formatted}
                          </Val>
                          <Val bgColor={color} mono size={15}>
                            Lap {fl.lap_number}
                          </Val>
                          {/* Tyre WITHOUT bullet, contrast-aware */}
                          <div
                            style={{ display: "flex", alignItems: "center" }}
                          >
                            <TyreChipContrast
                              compound={fl.tyre_compound}
                              // bgColor={color}
                            />
                          </div>
                        </F1Row>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ── PIT STOPS ── */}
            {tab === "pit-stops" && (
              <div style={card}>
                <SectionTitle
                  accent={accent}
                  sub="Every pit stop. Sorted by lap. Green = fastest stop."
                >
                  Pit Stop Times
                </SectionTitle>
                {enrichedPitStops.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 48,
                      color: C.muted,
                      fontFamily: "'Barlow Condensed',sans-serif",
                      letterSpacing: "0.15em",
                    }}
                  >
                    PIT STOP DATA NOT YET AVAILABLE
                    <br />
                    <span
                      style={{ fontSize: 11, marginTop: 4, display: "block" }}
                    >
                      Jolpica processes this 1–2 days after the race
                    </span>
                  </div>
                ) : (
                  <>
                    {/* Summary cards */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3,1fr)",
                        gap: 8,
                        marginBottom: 24,
                      }}
                    >
                      {(() => {
                        const v = enrichedPitStops.filter(
                          (p) =>
                            p.duration_seconds &&
                            p.duration_seconds > 1 &&
                            p.duration_seconds < 60
                        );
                        const fastest = v.length
                          ? Math.min(...v.map((p) => p.duration_seconds!))
                          : null;
                        const avg = v.length
                          ? v.reduce((a, b) => a + b.duration_seconds!, 0) /
                            v.length
                          : null;
                        const slowest = v.length
                          ? Math.max(...v.map((p) => p.duration_seconds!))
                          : null;
                        return [
                          {
                            label: "FASTEST STOP",
                            val: fastest,
                            color: "#22c55e",
                          },
                          { label: "AVERAGE STOP", val: avg, color: C.text },
                          { label: "SLOWEST STOP", val: slowest, color: C.red },
                        ].map((s) => (
                          <div
                            key={s.label}
                            style={{
                              background: C.dark,
                              border: `1px solid ${C.border}`,
                              borderRadius: 3,
                              padding: "16px 20px",
                              textAlign: "center",
                              position: "relative",
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                position: "absolute",
                                top: 0,
                                left: 0,
                                right: 0,
                                height: 2,
                                background: `linear-gradient(90deg,${s.color},transparent)`,
                              }}
                            />
                            <div
                              style={{
                                fontFamily: "'Barlow Condensed',sans-serif",
                                fontWeight: 900,
                                fontStyle: "italic",
                                fontSize: 28,
                                color: s.color,
                                letterSpacing: "-0.02em",
                              }}
                            >
                              {s.val ? `${s.val.toFixed(3)}s` : "—"}
                            </div>
                            <div
                              style={{
                                fontFamily: "'Barlow Condensed',sans-serif",
                                fontSize: 10,
                                color: C.muted,
                                marginTop: 4,
                                letterSpacing: "0.15em",
                              }}
                            >
                              {s.label}
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                    <F1Header
                      cols={PS_COLS}
                      labels={["Driver", "Team", "Stop No.", "Lap", "Duration"]}
                    />
                    {enrichedPitStops
                      .sort((a, b) => a.lap - b.lap)
                      .map((ps, i) => {
                        const sd = (ps as any).sd || sdByNum[ps.driver_number];
                        const color = sd?.color || "#888";
                        // const logo = getTeamLogo(sd?.team || "");
                        const dur = ps.duration_seconds;
                        const isFastest =
                          fastestStopDur !== null && dur === fastestStopDur;
                        const durColor = isFastest
                          ? "#22c55e"
                          : dur && dur > 40
                          ? "#f59e0b"
                          : undefined;
                        return (
                          <F1Row
                            key={i}
                            cols={PS_COLS}
                            rowColor={color}
                            pos={
                              <span
                                style={{
                                  fontFamily: "'Barlow Condensed',sans-serif",
                                  fontWeight: 900,
                                  fontStyle: "italic",
                                  fontSize: 22,
                                  color: C.text,
                                  lineHeight: 1,
                                }}
                              >
                                {ps.stop_number}
                              </span>
                            }
                          >
                            <DriverName
                              // logo={logo}
                              team={sd?.team || ""}
                              full={
                                sd?.full_name || ps.driver_code || ps.driver_id
                              }
                              sub={sd?.code || ps.driver_code || ""}
                              bgColor={color}
                            />
                            <Val bgColor={color}>
                              <span
                                style={{
                                  fontFamily: "'Barlow Condensed',sans-serif",
                                  fontSize: 14,
                                  fontWeight: 700,
                                }}
                              >
                                {sd?.team || "—"}
                              </span>
                            </Val>
                            <Val bgColor={color}>
                              <span
                                style={{
                                  fontFamily: "'Barlow Condensed',sans-serif",
                                  fontSize: 15,
                                  letterSpacing: "0.06em",
                                }}
                              >
                                STOP {ps.stop_number}
                              </span>
                            </Val>
                            <Val bgColor={color} mono bold size={15}>
                              LAP {ps.lap}
                            </Val>
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                              }}
                            >
                              <span
                                style={{
                                  fontFamily: "monospace",
                                  fontWeight: 700,
                                  fontSize: 16,
                                  color: durColor || textOn(color),
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {ps.duration_formatted}
                                {isFastest && (
                                  <span
                                    style={{
                                      fontFamily:
                                        "'Barlow Condensed',sans-serif",
                                      fontSize: 10,
                                      marginLeft: 8,
                                      color: "#22c55e",
                                      border: "1px solid #22c55e66",
                                      padding: "1px 5px",
                                      borderRadius: 2,
                                      letterSpacing: "0.1em",
                                    }}
                                  >
                                    FASTEST
                                  </span>
                                )}
                              </span>
                            </div>
                          </F1Row>
                        );
                      })}
                  </>
                )}
              </div>
            )}

            {/* ── AI STRATEGY ── */}
            {tab === "ai-strategy" && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "340px 1fr",
                  gap: 12,
                }}
              >
                <div style={card}>
                  <SectionTitle accent={accent}>
                    Configure Analysis
                  </SectionTitle>
                  <p
                    style={{
                      fontFamily: "'Barlow Condensed',sans-serif",
                      fontSize: 13,
                      color: C.muted,
                      marginBottom: 16,
                      lineHeight: 1.5,
                      letterSpacing: "0.02em",
                    }}
                  >
                    The AI Strategy Agent retrieves similar historical
                    situations from Pinecone RAG, then recommends whether to
                    pit.
                  </p>
                  <div
                    style={{
                      fontFamily: "'Barlow Condensed',sans-serif",
                      fontSize: 10,
                      color: C.muted,
                      textTransform: "uppercase",
                      letterSpacing: "0.15em",
                      marginBottom: 6,
                    }}
                  >
                    Driver
                  </div>
                  <Sel
                    value={stratDriver}
                    onChange={(v) => setStratDriver(Number(v))}
                  >
                    {allNums.map((n) => {
                      const sd = sdByNum[n];
                      return (
                        <option key={n} value={n}>
                          #{n} {sd?.code || "?"} —{" "}
                          {sd?.full_name || `Driver ${n}`}
                        </option>
                      );
                    })}
                  </Sel>
                  <div style={{ height: 16 }} />
                  <div
                    style={{
                      fontFamily: "'Barlow Condensed',sans-serif",
                      fontSize: 10,
                      color: C.muted,
                      textTransform: "uppercase",
                      letterSpacing: "0.15em",
                      marginBottom: 6,
                    }}
                  >
                    LAP {stratLap} OF {maxLap}
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={maxLap}
                    value={stratLap}
                    onChange={(e) => setStratLap(Number(e.target.value))}
                    style={{ width: "100%", marginBottom: 16 }}
                  />
                  {selectedRow ? (
                    <div style={{ marginBottom: 16 }}>
                      <InfoRow
                        label="Lap Time"
                        value={`${selectedRow.lap_duration?.toFixed(3)}s`}
                        tip="Actual lap time"
                      />
                      <InfoRow
                        label="Tyre"
                        value={
                          <TyreChip
                            compound={selectedRow.tyre_compound || "?"}
                          />
                        }
                        tip="Current compound"
                      />
                      <InfoRow
                        label="Tyre Age"
                        value={`${selectedRow.tyre_age_laps} laps`}
                        tip="Laps on this set"
                      />
                      <InfoRow
                        label="Degradation"
                        value={
                          <span
                            style={{
                              fontFamily: "monospace",
                              color:
                                selectedRow.tyre_degradation_rate > 0.15
                                  ? C.red
                                  : C.text,
                            }}
                          >
                            {selectedRow.tyre_degradation_rate?.toFixed(4)}s/lap
                          </span>
                        }
                        tip="Time lost per lap vs stint start."
                      />
                      <InfoRow
                        label="Spark Pit Flag"
                        value={
                          <PitFlagBadge yes={selectedRow.should_pit_soon} />
                        }
                        tip="Spark tyre model flag"
                      />
                    </div>
                  ) : (
                    <div
                      style={{ color: C.muted, fontSize: 13, marginBottom: 16 }}
                    >
                      No data for this lap
                    </div>
                  )}
                  <ActionBtn
                    onClick={handleStrategy}
                    loading={stratLoading}
                    accent={accent}
                  >
                    GET AI RECOMMENDATION
                  </ActionBtn>
                </div>
                <div style={card}>
                  <SectionTitle
                    accent={accent}
                    sub="CrewAI Strategy Agent · RAG retrieval from Pinecone · Spark-computed features"
                  >
                    Strategy Recommendation
                  </SectionTitle>
                  {stratLoading ? (
                    <div
                      style={{
                        height: 320,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        color: C.muted,
                        gap: 14,
                      }}
                    >
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          border: `3px solid ${C.border2}`,
                          borderTop: `3px solid ${accent}`,
                          borderRadius: "50%",
                          animation: "spin 0.9s linear infinite",
                        }}
                      />
                      <span
                        style={{
                          fontFamily: "'Barlow Condensed',sans-serif",
                          fontSize: 12,
                          letterSpacing: "0.12em",
                          textTransform: "uppercase",
                        }}
                      >
                        Analysing...
                      </span>
                    </div>
                  ) : stratResult ? (
                    <div
                      style={{
                        background: C.dark,
                        border: `1px solid ${C.border2}`,
                        borderLeft: `3px solid ${accent}`,
                        borderRadius: 3,
                        padding: 20,
                        fontSize: 14,
                        lineHeight: 1.8,
                        color: C.text2,
                        whiteSpace: "pre-wrap",
                        fontFamily: "'Barlow',sans-serif",
                      }}
                    >
                      {stratResult}
                    </div>
                  ) : (
                    <div
                      style={{
                        height: 320,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        color: C.muted,
                        gap: 8,
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "'Barlow Condensed',sans-serif",
                          fontSize: 12,
                          letterSpacing: "0.12em",
                          textTransform: "uppercase",
                        }}
                      >
                        Select a driver and lap, then click the button
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── COMMENTARY ── */}
            {tab === "commentary" && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "340px 1fr",
                  gap: 12,
                }}
              >
                <div style={card}>
                  <SectionTitle accent={accent}>
                    Generate Commentary
                  </SectionTitle>
                  <p
                    style={{
                      fontFamily: "'Barlow Condensed',sans-serif",
                      fontSize: 13,
                      color: C.muted,
                      marginBottom: 16,
                      lineHeight: 1.5,
                    }}
                  >
                    Martin Brundle-style live commentary from real telemetry
                    data.
                  </p>
                  <div
                    style={{
                      fontFamily: "'Barlow Condensed',sans-serif",
                      fontSize: 10,
                      color: C.muted,
                      textTransform: "uppercase",
                      letterSpacing: "0.15em",
                      marginBottom: 6,
                    }}
                  >
                    Driver
                  </div>
                  <Sel
                    value={stratDriver}
                    onChange={(v) => setStratDriver(Number(v))}
                  >
                    {allNums.map((n) => {
                      const sd = sdByNum[n];
                      return (
                        <option key={n} value={n}>
                          #{n} {sd?.code || "?"} —{" "}
                          {sd?.full_name || `Driver ${n}`}
                        </option>
                      );
                    })}
                  </Sel>
                  <div style={{ height: 16 }} />
                  <div
                    style={{
                      fontFamily: "'Barlow Condensed',sans-serif",
                      fontSize: 10,
                      color: C.muted,
                      textTransform: "uppercase",
                      letterSpacing: "0.15em",
                      marginBottom: 6,
                    }}
                  >
                    LAP {stratLap} OF {maxLap}
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={maxLap}
                    value={stratLap}
                    onChange={(e) => setStratLap(Number(e.target.value))}
                    style={{ width: "100%", marginBottom: 20 }}
                  />
                  <ActionBtn
                    onClick={handleCommentary}
                    loading={commLoading}
                    accent={accent}
                  >
                    🎙 GENERATE COMMENTARY
                  </ActionBtn>
                </div>
                <div style={card}>
                  <SectionTitle
                    accent={accent}
                    sub="Generated from real race telemetry by the CrewAI Commentary Agent"
                  >
                    Live Commentary
                  </SectionTitle>
                  {commResult ? (
                    <div>
                      <div
                        style={{
                          display: "flex",
                          gap: 20,
                          alignItems: "flex-start",
                        }}
                      >
                        <div
                          style={{
                            width: 3,
                            flexShrink: 0,
                            background: accent,
                            borderRadius: 1,
                            alignSelf: "stretch",
                          }}
                        />
                        <blockquote
                          style={{
                            fontFamily: "'Barlow',sans-serif",
                            fontSize: 22,
                            fontWeight: 300,
                            lineHeight: 1.6,
                            color: C.text,
                            fontStyle: "italic",
                            margin: 0,
                            letterSpacing: "0.01em",
                          }}
                        >
                          &ldquo;{commResult}&rdquo;
                        </blockquote>
                      </div>
                      <div
                        style={{
                          marginTop: 20,
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          color: C.muted,
                        }}
                      >
                        <div
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: accent,
                            animation: "pulse 1.5s ease-in-out infinite",
                          }}
                        />
                        <span
                          style={{
                            fontFamily: "'Barlow Condensed',sans-serif",
                            fontSize: 11,
                            letterSpacing: "0.2em",
                          }}
                        >
                          LIVE ·{" "}
                          {sdByNum[stratDriver]?.full_name ||
                            `DRIVER ${stratDriver}`}{" "}
                          · LAP {stratLap}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div
                      style={{
                        height: 200,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        color: C.muted,
                        gap: 12,
                      }}
                    >
                      <span style={{ fontSize: 56 }}>🎙</span>
                      <span
                        style={{
                          fontFamily: "'Barlow Condensed',sans-serif",
                          fontSize: 13,
                          letterSpacing: "0.1em",
                        }}
                      >
                        SELECT DRIVER AND LAP, THEN GENERATE COMMENTARY
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

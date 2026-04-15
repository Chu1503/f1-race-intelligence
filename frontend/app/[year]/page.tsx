"use client";
import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { getCalendar, getAvailableRaces, runBatchProcessor } from "../../lib/api";
import { getFlag, type CalendarRace } from "../../lib/constants";
import { ArrowRight, ArrowLeft } from "lucide-react";

const C = {
  black: "#080808",
  dark: "#0e0e0e",
  card: "#131313",
  border: "#222",
  red: "#e8002d",
  muted: "#555",
  text: "#fff",
  text2: "#aaa",
};

const yearColors: Record<number, string> = {
  2026: "#e8002d",
  2025: "#FF8000",
  2024: "#3671C6",
  2023: "#27F4D2",
};

export default function SeasonPage() {
  const router = useRouter();
  const params = useParams();
  const year = Number(params.year);

  const [calendar, setCalendar] = useState<CalendarRace[]>([]);
  const [available, setAvailable] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const accentColor = yearColors[year] || C.red;

  useEffect(() => {
    Promise.all([getCalendar(year), getAvailableRaces()]).then(
      ([cal, avail]) => {
        setCalendar(cal?.races || []);
        const set = new Set<number>(
          (avail.races || [])
            .filter((r: any) => r.year === year)
            .map((r: any) => r.round)
        );
        setAvailable(set);
        setLoading(false);
      }
    );
  }, [year]);

  const handleLoad = async (e: React.MouseEvent, round: number) => {
    e.stopPropagation();
    setProcessing(round);
    await runBatchProcessor(year, round);
    const poll = setInterval(async () => {
      const avail = await getAvailableRaces();
      const set = new Set<number>(
        (avail.races || [])
          .filter((r: any) => r.year === year)
          .map((r: any) => r.round)
      );
      setAvailable(set);
      if (set.has(round)) {
        clearInterval(poll);
        setProcessing(null);
        router.push(`/${year}/${round}`);
      }
    }, 10000);
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  };

  const isPast = (dateStr: string) => {
    if (!dateStr) return false;
    return new Date(dateStr) < new Date();
  };

  return (
    <div style={{ minHeight: "100vh", background: C.black }}>
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
            onClick={() => router.push("/")}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontFamily: "'Barlow Condensed', sans-serif",
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
            <ArrowLeft size={16} style={{ color: accentColor }} />
            SEASONS
          </button>

          <div style={{ width: 1, height: 24, background: C.border }} />

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                background: accentColor,
                padding: "5px 14px",
                fontFamily: "'Barlow Condensed', sans-serif",
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
                fontFamily: "'Barlow Condensed', sans-serif",
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

          <div style={{ marginLeft: "auto" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: `${accentColor}15`,
                border: `1px solid ${accentColor}40`,
                padding: "5px 16px",
                borderRadius: 2,
              }}
            >
              <div
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: accentColor,
                }}
              />
              <span
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: 13,
                  color: accentColor,
                  letterSpacing: "0.18em",
                  fontWeight: 700,
                }}
              >
                {available.size} / {calendar.length} RACES LOADED
              </span>
            </div>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1400, margin: "0 auto", padding: "32px 28px" }}>
        <div style={{ marginBottom: 36 }}>
          <div
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontWeight: 900,
              fontStyle: "italic",
              fontSize: "clamp(40px, 6vw, 80px)",
              lineHeight: 0.9,
              textTransform: "uppercase",
              letterSpacing: "-0.02em",
            }}
          >
            <span style={{ color: C.text }}>RACE </span>
            <span style={{ color: accentColor }}>CALENDAR</span>
          </div>
          <div
            style={{
              height: 3,
              width: 80,
              background: accentColor,
              marginTop: 14,
            }}
          />
        </div>

        {loading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              color: C.muted,
            }}
          >
            <span
              style={{
                animation: "spin 1s linear infinite",
                display: "inline-block",
                fontSize: 24,
                color: accentColor,
              }}
            >
              ⟳
            </span>
            <span
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                letterSpacing: "0.15em",
                fontSize: 14,
              }}
            >
              LOADING CALENDAR…
            </span>
          </div>
        ) : (
          <>
            <style>{`
              @keyframes spin { to { transform: rotate(360deg); } }
              @keyframes slideUp { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:none} }
              .race-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 12px;
              }
              @media (max-width: 1200px) {
                .race-grid { grid-template-columns: repeat(3, 1fr); }
              }
              @media (max-width: 860px) {
                .race-grid { grid-template-columns: repeat(2, 1fr); }
              }
              @media (max-width: 520px) {
                .race-grid { grid-template-columns: 1fr; }
              }
              .race-card {
                position: relative;
                border-radius: 4px;
                overflow: hidden;
                transition: all 0.2s;
                animation: slideUp 0.3s ease both;
              }
              .race-card:hover .card-action-loaded {
                background: ${accentColor}22 !important;
              }
            `}</style>

            <div className="race-grid">
              {calendar.map((race, idx) => {
                const isLoaded = available.has(race.round);
                const isProc = processing === race.round;
                const past = isPast(race.date);
                const flag = getFlag(race.country);

                return (
                  <div
                    key={race.round}
                    className="race-card"
                    onClick={() =>
                      isLoaded && router.push(`/${year}/${race.round}`)
                    }
                    onMouseEnter={() => setHovered(race.round)}
                    onMouseLeave={() => setHovered(null)}
                    style={{
                      background:
                        hovered === race.round && isLoaded
                          ? `${accentColor}0d`
                          : C.card,
                      border: `1px solid ${
                        hovered === race.round && isLoaded
                          ? accentColor
                          : isLoaded
                          ? "#2a2a2a"
                          : C.border
                      }`,
                      cursor: isLoaded ? "pointer" : "default",
                      opacity: !past && !isLoaded ? 0.45 : 1,
                      transform:
                        hovered === race.round && isLoaded
                          ? "translateY(-3px)"
                          : "none",
                      boxShadow:
                        hovered === race.round && isLoaded
                          ? `0 10px 40px ${accentColor}18`
                          : "none",
                      animationDelay: `${Math.min(idx * 0.025, 0.4)}s`,
                    }}
                  >
                    <div
                      style={{
                        height: 3,
                        background: isLoaded
                          ? `linear-gradient(90deg, ${accentColor}, ${accentColor}44)`
                          : `linear-gradient(90deg, #2a2a2a, transparent)`,
                      }}
                    />

                    <div style={{ padding: "20px 20px 18px" }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          justifyContent: "space-between",
                          marginBottom: 14,
                        }}
                      >
                        <div
                          style={{
                            fontFamily: "'Barlow Condensed', sans-serif",
                            fontSize: 14,
                            fontWeight: 700,
                            letterSpacing: "0.2em",
                            color: isLoaded ? accentColor : C.muted,
                            textTransform: "uppercase",
                          }}
                        >
                          ROUND {race.round}
                        </div>
                        <div
                          style={{
                            width: 48,
                            height: 30,
                            borderRadius: 3,
                            border: "1px solid #2a2a2a",
                            overflow: "hidden",
                            flexShrink: 0,
                            background: "#1a1a1a",
                          }}
                        >
                          <img
                            src={`https://flagcdn.com/w80/${flag}.png`}
                            alt={race.country}
                            style={{
                              width: "100%",
                              height: "100%",
                              objectFit: "cover",
                              objectPosition: "center",
                              display: "block",
                            }}
                          />
                          {/* {isLoaded && (
                            <div
                              style={{
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                background: accentColor,
                                boxShadow: `0 0 8px ${accentColor}`,
                                flexShrink: 0,
                              }}
                            />
                          )} */}
                        </div>
                      </div>

                      <div
                        style={{
                          fontFamily: "'Barlow Condensed', sans-serif",
                          fontWeight: 900,
                          fontStyle: "italic",
                          fontSize: "clamp(26px, 3vw, 34px)",
                          lineHeight: 1,
                          letterSpacing: "-0.01em",
                          textTransform: "uppercase",
                          color: isLoaded ? C.text : C.text2,
                          marginBottom: 4,
                        }}
                      >
                        {race.name}
                      </div>
                      <div
                        style={{
                          fontFamily: "'Barlow Condensed', sans-serif",
                          fontSize: 15,
                          fontWeight: 700,
                          letterSpacing: "0.12em",
                          color: C.muted,
                          textTransform: "uppercase",
                          marginBottom: 14,
                        }}
                      >
                        GRAND PRIX
                      </div>

                      <div
                        style={{
                          fontFamily: "'Barlow Condensed', sans-serif",
                          fontSize: 16,
                          color: C.text2,
                          marginBottom: 2,
                          letterSpacing: "0.02em",
                        }}
                      >
                        {race.circuit}
                      </div>

                      <div
                        style={{
                          fontFamily: "'Barlow Condensed', sans-serif",
                          fontSize: 15,
                          color: C.muted,
                          marginBottom: 18,
                          letterSpacing: "0.04em",
                        }}
                      >
                        {race.locality}, {race.country}
                        {race.date ? ` · ${formatDate(race.date)}` : ""}
                      </div>

                      {isLoaded ? (
                        <div
                          className="card-action-loaded"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "10px 14px",
                            background: `${accentColor}18`,
                            border: `1px solid ${accentColor}44`,
                            borderRadius: 2,
                            transition: "background 0.15s",
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "'Barlow Condensed', sans-serif",
                              fontSize: 13,
                              fontWeight: 700,
                              letterSpacing: "0.15em",
                              color: accentColor,
                              textTransform: "uppercase",
                            }}
                          >
                            VIEW ANALYSIS
                          </span>
                          <ArrowRight
                            size={18}
                            style={{ color: accentColor }}
                          />
                        </div>
                      ) : past ? (
                        <button
                          onClick={(e) => handleLoad(e, race.round)}
                          disabled={isProc}
                          style={{
                            width: "100%",
                            padding: "10px 14px",
                            background: isProc ? "#151515" : C.dark,
                            border: `1px solid ${
                              isProc ? accentColor : "#2a2a2a"
                            }`,
                            borderRadius: 2,
                            cursor: isProc ? "not-allowed" : "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 8,
                            transition: "all 0.15s",
                          }}
                          onMouseEnter={(e) => {
                            if (!isProc)
                              e.currentTarget.style.borderColor = accentColor;
                          }}
                          onMouseLeave={(e) => {
                            if (!isProc)
                              e.currentTarget.style.borderColor = "#2a2a2a";
                          }}
                        >
                          {isProc ? (
                            <>
                              <span
                                style={{
                                  animation: "spin 1s linear infinite",
                                  display: "inline-block",
                                  color: accentColor,
                                  fontSize: 14,
                                }}
                              >
                                ⟳
                              </span>
                              <span
                                style={{
                                  fontFamily: "'Barlow Condensed', sans-serif",
                                  fontSize: 13,
                                  color: accentColor,
                                  letterSpacing: "0.15em",
                                  fontWeight: 700,
                                }}
                              >
                                PROCESSING…
                              </span>
                            </>
                          ) : (
                            <span
                              style={{
                                fontFamily: "'Barlow Condensed', sans-serif",
                                fontSize: 13,
                                color: C.text2,
                                letterSpacing: "0.15em",
                                fontWeight: 700,
                              }}
                            >
                              LOAD DATA
                            </span>
                          )}
                        </button>
                      ) : (
                        <div
                          style={{
                            padding: "10px 14px",
                            background: "#0a0a0a",
                            border: "1px solid #1a1a1a",
                            borderRadius: 2,
                            textAlign: "center",
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "'Barlow Condensed', sans-serif",
                              fontSize: 12,
                              color: "#2a2a2a",
                              letterSpacing: "0.18em",
                              fontWeight: 700,
                            }}
                          >
                            UPCOMING
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

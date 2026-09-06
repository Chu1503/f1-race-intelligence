"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { errorMessage, getSeasons, getAvailableRaces, warmBackend } from "../lib/api";

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

export default function HomePage() {
  const router = useRouter();
  const [seasons, setSeasons] = useState<number[]>([]);
  const [available, setAvailable] = useState<{ year: number; round: number }[]>(
    []
  );
  const [hovered, setHovered] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loadingMessage, setLoadingMessage] = useState("Loading seasons…");

  useEffect(() => {
    warmBackend();
    let cancelled = false;
    const load = async () => {
      let attempt = 0;
      while (!cancelled) {
        attempt += 1;
        try {
          const [s, a] = await Promise.all([getSeasons(), getAvailableRaces()]);
          if (cancelled) return;
          setSeasons(s.seasons);
          setAvailable(a.races);
          setError("");
          setLoading(false);
          return;
        } catch (reason) {
          if (cancelled) return;
          setError(errorMessage(reason));
          setLoading(false);
          setLoadingMessage(`Connecting to the data service… retry ${attempt}`);
          await new Promise((resolve) => setTimeout(resolve, Math.min(10_000, attempt * 2_000)));
        }
      }
    };
    void load();
    return () => { cancelled = true; };
  }, []);

  const racesForYear = (y: number) =>
    available.filter((r) => r.year === y).length;

  const yearColors: Record<number, string> = {
    2026: "#e8002d",
    2025: "#FF8000",
    2024: "#3671C6",
    2023: "#27F4D2",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.black,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          padding: "80px 32px 40px",
          width: "100%",
        }}
      >
        <div style={{ marginBottom: 30 }}>
          <div
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontWeight: 900,
              fontSize: "clamp(48px, 8vw, 96px)",
              lineHeight: 0.9,
              letterSpacing: "-0.02em",
              textTransform: "uppercase",
              animation: "slideUp 0.6s ease forwards",
            }}
          >
            <div>
              <span style={{ color: C.text }}>SELECT </span>
              <span style={{ color: C.red, fontStyle: "italic" }}>SEASON</span>
            </div>
          </div>

          <p
            style={{
              color: C.text2,
              fontSize: 15,
              marginTop: 20,
              maxWidth: 480,
              lineHeight: 1.6,
            }}
          >
            Explore every Grand Prix with lap by lap telemetry, tyre strategies,
            AI race analysis and generated commentary over validated historical
            race data. Live mode is shown only when a processed OpenF1 session is connected.
          </p>
        </div>

        {loading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              color: C.muted,
            }}
          >
            <span
              style={{
                animation: "spin 1s linear infinite",
                display: "inline-block",
                fontSize: 20,
                color: C.red,
              }}
            >
              ⟳
            </span>
            {loadingMessage}
          </div>
        ) : error ? (
          <div
            style={{
              background: C.card,
              border: `1px solid ${C.border}`,
              borderRadius: 4,
              padding: "32px 28px",
              maxWidth: 480,
            }}
          >
            <div
              style={{
                width: 32,
                height: 3,
                background: C.red,
                marginBottom: 16,
                borderRadius: 1,
              }}
            />
            <div
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontWeight: 900,
                fontStyle: "italic",
                fontSize: 22,
                textTransform: "uppercase",
                letterSpacing: "0.02em",
                marginBottom: 8,
              }}
            >
              Data service unavailable
            </div>
            <p style={{ color: C.text2, fontSize: 13, lineHeight: 1.6, marginBottom: 0 }}>
              {error} The connection will retry automatically.
            </p>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: 16,
              maxWidth: 900,
            }}
          >
            {seasons.map((y, idx) => {
              const color = yearColors[y] || C.red;
              const count = racesForYear(y);
              const isHovered = hovered === y;

              return (
                <button
                  key={y}
                  onClick={() => router.push(`/${y}`)}
                  onMouseEnter={() => setHovered(y)}
                  onMouseLeave={() => setHovered(null)}
                  style={{
                    position: "relative",
                    background: isHovered ? `${color}12` : C.card,
                    border: `1px solid ${isHovered ? color : C.border}`,
                    borderRadius: 4,
                    padding: "28px 28px 24px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.2s",
                    overflow: "hidden",
                    animation: `slideUp 0.4s ease ${idx * 0.08}s both`,
                    transform: isHovered ? "translateY(-3px)" : "none",
                    boxShadow: isHovered ? `0 12px 40px ${color}20` : "none",
                  }}
                >
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      right: 0,
                      width: 0,
                      height: 0,
                      borderStyle: "solid",
                      borderWidth: `0 48px 48px 0`,
                      borderColor: `transparent ${
                        isHovered ? color : C.border
                      } transparent transparent`,
                      transition: "all 0.2s",
                    }}
                  />

                  <div
                    style={{
                      position: "absolute",
                      bottom: 0,
                      left: 0,
                      right: 0,
                      height: 3,
                      background: `linear-gradient(90deg, ${color}, transparent)`,
                      opacity: isHovered ? 1 : 0,
                      transition: "opacity 0.2s",
                    }}
                  />

                  <div
                    style={{
                      fontFamily: "'Barlow Condensed', sans-serif",
                      fontWeight: 900,
                      fontStyle: "italic",
                      fontSize: 72,
                      lineHeight: 1,
                      color: isHovered ? color : C.border,
                      letterSpacing: "-0.04em",
                      transition: "color 0.2s",
                      marginBottom: 8,
                    }}
                  >
                    {y}
                  </div>

                  <div
                    style={{
                      fontFamily: "'Barlow Condensed', sans-serif",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.15em",
                      fontSize: 11,
                      color: isHovered ? C.text : C.muted,
                      transition: "color 0.2s",
                      marginBottom: 16,
                    }}
                  >
                    Formula 1 Season
                  </div>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      {count > 0 ? (
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            background: `${color}20`,
                            border: `1px solid ${color}40`,
                            padding: "3px 10px",
                            borderRadius: 2,
                          }}
                        >
                          <div
                            style={{
                              width: 5,
                              height: 5,
                              borderRadius: "50%",
                              background: color,
                            }}
                          />
                          <span
                            style={{
                              fontFamily: "'Barlow Condensed', sans-serif",
                              fontSize: 11,
                              color,
                              fontWeight: 700,
                              letterSpacing: "0.1em",
                            }}
                          >
                            {count} RACES LOADED
                          </span>
                        </div>
                      ) : (
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            background: "#ffffff08",
                            border: "1px solid #333",
                            padding: "3px 10px",
                            borderRadius: 2,
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "'Barlow Condensed', sans-serif",
                              fontSize: 11,
                              color: C.muted,
                              letterSpacing: "0.1em",
                            }}
                          >
                            NO DATA YET
                          </span>
                        </div>
                      )}
                    </div>
                    <div
                      style={{
                        fontFamily: "'Barlow Condensed', sans-serif",
                        fontSize: 22,
                        color: isHovered ? color : C.muted,
                        transition: "all 0.2s",
                        transform: isHovered ? "translateX(4px)" : "none",
                      }}
                    >
                      →
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div
        style={{
          marginTop: "auto",
          borderTop: `1px solid ${C.border}`,
          padding: "16px 32px",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 12,
            color: C.muted,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
          }}
        >
          Made with <span style={{ color: C.red }}>❤️</span> by Chu
        </span>
      </div>
    </div>
  );
}

export default function RaceLoading() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading race analysis"
      style={{ minHeight: "100vh", background: "#080808", padding: "80px 32px" }}
    >
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div style={{ width: 220, height: 18, background: "#222", animation: "pulse 1.2s ease-in-out infinite" }} />
        <div style={{ width: 480, maxWidth: "90%", height: 58, marginTop: 18, background: "#171717", animation: "pulse 1.2s ease-in-out infinite" }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, marginTop: 40 }}>
          {[0, 1, 2, 3].map((item) => (
            <div key={item} style={{ height: 110, background: "#131313", border: "1px solid #222", animation: "pulse 1.2s ease-in-out infinite" }} />
          ))}
        </div>
        <div style={{ height: 420, marginTop: 20, background: "#101010", border: "1px solid #222", animation: "pulse 1.2s ease-in-out infinite" }} />
      </div>
    </main>
  );
}

export default function SeasonLoading() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading season"
      style={{ minHeight: "100vh", background: "#080808", padding: "96px 32px" }}
    >
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ width: 180, height: 18, background: "#222", animation: "pulse 1.2s ease-in-out infinite" }} />
        <div style={{ width: 360, maxWidth: "80%", height: 54, marginTop: 18, background: "#171717", animation: "pulse 1.2s ease-in-out infinite" }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16, marginTop: 48 }}>
          {[0, 1, 2, 3, 4, 5].map((item) => (
            <div key={item} style={{ height: 235, background: "#131313", border: "1px solid #222", animation: "pulse 1.2s ease-in-out infinite" }} />
          ))}
        </div>
      </div>
    </main>
  );
}

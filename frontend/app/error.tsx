"use client";

import { useEffect } from "react";

export default function AppError({ error, unstable_retry }: { error: Error & { digest?: string }; unstable_retry: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24, background: "#080808", color: "white" }}>
      <div role="alert" style={{ maxWidth: 520, padding: 28, background: "#131313", border: "1px solid #e8002d66" }}>
        <h2 style={{ marginBottom: 10 }}>The race view could not be rendered</h2>
        <p style={{ color: "#aaa", marginBottom: 20 }}>{error.message || "An unexpected application error occurred."}</p>
        <button onClick={unstable_retry} style={{ padding: "10px 18px", background: "#e8002d", color: "white", border: 0, cursor: "pointer" }}>Try again</button>
      </div>
    </main>
  );
}

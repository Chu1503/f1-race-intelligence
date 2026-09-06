import type { Metadata } from "next";
import "./globals.css";
import ServiceWorkerCleanup from "../components/ServiceWorkerCleanup";

export const metadata: Metadata = {
  title: "F1 Race Intelligence",
  description: "F1 Race Strategy Analysis Powered by AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        style={{
          minHeight: "100vh",
          background: "#080808",
          position: "relative",
        }}
      >
        <ServiceWorkerCleanup />
        <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
      </body>
    </html>
  );
}

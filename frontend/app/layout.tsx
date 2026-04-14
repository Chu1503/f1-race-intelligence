import type { Metadata } from "next";
import "./globals.css";
import { Barlow, Barlow_Condensed } from "next/font/google";

const barlow = Barlow({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-barlow",
});

const barlowCondensed = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["300", "400", "600", "700", "900"],
  variable: "--font-barlow-condensed",
});

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
    <html
      lang="en"
      className={`${barlow.variable} ${barlowCondensed.variable}`}
    >
      <body
        style={{
          minHeight: "100vh",
          background: "#080808",
          position: "relative",
        }}
      >
        <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
      </body>
    </html>
  );
}

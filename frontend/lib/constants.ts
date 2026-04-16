export const TYRE_COLORS: Record<string, string> = {
  SOFT: "#E8002D",
  MEDIUM: "#FFD700",
  HARD: "#EEEEEE",
  INTER: "#39B54A",
  WET: "#0067FF",
};

export const TEAM_COLORS: Record<string, string> = {
  "mercedes": "#27F4D2",
  "ferrari": "#E8002D",
  "mclaren": "#FF8000",
  "red bull": "#1E2248",
  "aston martin": "#00665E",
  "alpine": "#1E41FF",
  "rb": "#1E41FF",
  "racing bulls": "#1E41FF",
  "williams": "#1E5BFF",
  "kick sauber": "#C00000",
  "sauber": "#C00000",
  "audi": "#D50000",
  "haas": "#F2F2F2",
  "cadillac": "#1B1B1B",
  "andretti": "#1F3275",
  "general motors": "#1F3275",
};

export function getTeamColor(teamName: string): string {
  if (!teamName) return "#888888";
  const t = teamName.toLowerCase();
  for (const [key, color] of Object.entries(TEAM_COLORS)) {
    if (t.includes(key)) return color;
  }
  return "#888888";
}

export function getContrastTextColor(hex: string): string {
  if (!hex) return "#ffffff";
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((c) => c + c)
          .join("")
      : clean;

  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);

  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.65 ? "#0A0A0A" : "#FFFFFF";
}

export const COUNTRY_CODES: Record<string, string> = {
  Australia: "au",
  China: "cn",
  Japan: "jp",
  Bahrain: "bh",
  "Saudi Arabia": "sa",
  USA: "us",
  "United States": "us",
  Italy: "it",
  Monaco: "mc",
  Canada: "ca",
  Spain: "es",
  Austria: "at",
  UK: "gb",
  "Great Britain": "gb",
  Hungary: "hu",
  Belgium: "be",
  Netherlands: "nl",
  Singapore: "sg",
  Mexico: "mx",
  Brazil: "br",
  UAE: "ae",
  "Abu Dhabi": "ae",
  Azerbaijan: "az",
  Qatar: "qa",
  "Las Vegas": "us",
  Miami: "us",
};

// const TEAM_LOGOS: Record<string, string> = {
//   "mclaren": "/logos/mclaren.png",
//   "ferrari": "/logos/ferrari.png",
//   "red bull": "/logos/redbull.png",
//   "mercedes": "/logos/mercedes.png",
//   "aston martin": "/logos/aston.png",
//   "alpine": "/logos/alpine.png",
//   "williams": "/logos/williams.png",
//   "racing bulls": "/logos/rb.png",
//   "rb": "/logos/rb.png",
//   "kick sauber": "/logos/sauber.png",
//   "sauber": "/logos/sauber.png",
//   "audi": "/logos/audi.png",
//   "haas": "/logos/haas.png",
//   "cadillac": "/logos/cadillac.png",
// };

// export function getTeamLogo(teamName: string): string | null {
//   if (!teamName) return null;
//   const t = teamName.toLowerCase();
//   for (const [key, url] of Object.entries(TEAM_LOGOS)) {
//     if (t.includes(key)) return url;
//   }
//   return null;
// }

export function getFlag(country: string): string {
  return COUNTRY_CODES[country] || "un";
}

export function FlagImg({
  country,
  size = 32,
}: {
  country: string;
  size?: number;
}) {
  const code = COUNTRY_CODES[country] || "un";
  return `https://flagcdn.com/w${size}/${code}.png`;
}


export interface DriverInfo {
  driver_number: number;
  code: string;
  full_name: string;
  team: string;
  color: string;
  nationality: string;
}

export interface CalendarRace {
  round: number;
  name: string;
  full_name: string;
  circuit: string;
  country: string;
  locality: string;
  date: string;
}

export interface SessionDriver {
  race_number: number;
  code: string;
  full_name: string;
  team: string;
  color: string;
}


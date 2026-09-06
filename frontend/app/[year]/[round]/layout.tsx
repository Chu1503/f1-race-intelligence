import manifest from "../../../public/data/manifest.json";

export const dynamicParams = true;

export function generateStaticParams() {
  return manifest.availableRaces.map((race) => ({
    year: String(race.year),
    round: String(race.round),
  }));
}

export default function RaceLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}

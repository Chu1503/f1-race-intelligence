import manifest from "../../public/data/manifest.json";

export const dynamicParams = true;

export function generateStaticParams() {
  return manifest.seasons.map((year) => ({ year: String(year) }));
}

export default function YearLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}

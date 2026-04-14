import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "media.formula1.com" },
      { protocol: "https", hostname: "www.formula1.com" },
      { protocol: "https", hostname: "flagcdn.com" },
    ],
  },
};
export default nextConfig;
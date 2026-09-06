import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, errorMessage } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API errors", () => {
  it("preserves the actionable backend message", () => {
    expect(errorMessage(new ApiError("Rate limit exceeded", 429, 20))).toBe("Rate limit exceeded");
  });
  it("does not expose non-error implementation values", () => {
    expect(errorMessage({ secret: "value" })).toBe("Something went wrong. Please try again.");
  });
});

describe("static historical data", () => {
  it("uses the manifest and race bundle without calling the backend", async () => {
    vi.resetModules();
    const bundle = { version: 1, year: 2025, round: 1, laps: [] };
    const manifest = {
      version: 1,
      generatedAt: "2026-09-05T00:00:00Z",
      seasons: [2025],
      availableRaces: [{ year: 2025, round: 1 }],
      years: { "2025": { calendar: [{ round: 1 }], drivers: [] } },
      raceFiles: { "2025-1": "/data/races/2025/1.hash.json" },
    };
    const fetchMock = vi.fn(async (...args: [RequestInfo | URL, RequestInit?]) => ({
      ok: true,
      json: async () => String(args[0]) === "/data/manifest.json" ? manifest : bundle,
    }));
    vi.stubGlobal("fetch", fetchMock);

    const api = await import("./api");
    await expect(api.getAvailableRaces()).resolves.toEqual({ races: [{ year: 2025, round: 1 }] });
    await expect(api.getStaticRaceBundle(2025, 1)).resolves.toEqual(bundle);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/data/manifest.json",
      "/data/races/2025/1.hash.json",
    ]);
    expect(fetchMock.mock.calls[0][1]).toEqual({ cache: "no-cache" });
  });
});

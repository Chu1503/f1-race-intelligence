import { describe, expect, it } from "vitest";
import { ApiError, errorMessage } from "./api";

describe("API errors", () => {
  it("preserves the actionable backend message", () => {
    expect(errorMessage(new ApiError("Rate limit exceeded", 429, 20))).toBe("Rate limit exceeded");
  });
  it("does not expose non-error implementation values", () => {
    expect(errorMessage({ secret: "value" })).toBe("Something went wrong. Please try again.");
  });
});

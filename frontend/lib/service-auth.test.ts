import { describe, expect, it } from "vitest";
import { getServiceApiKey } from "./service-auth";

describe("getServiceApiKey", () => {
  it("uses the shared backend and frontend variable name", () => {
    expect(getServiceApiKey({ SERVICE_API_KEY: "shared-secret" })).toBe("shared-secret");
  });

  it("supports the previous frontend variable name during migration", () => {
    expect(getServiceApiKey({ API_SERVICE_KEY: "legacy-secret" })).toBe("legacy-secret");
  });

  it("prefers the shared variable name", () => {
    expect(getServiceApiKey({ SERVICE_API_KEY: "shared", API_SERVICE_KEY: "legacy" })).toBe("shared");
  });
});

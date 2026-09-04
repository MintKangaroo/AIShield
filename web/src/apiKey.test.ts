import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  API_KEY_HEADER,
  apiKeyHeaders,
  clearApiKey,
  readApiKey,
  UnauthorizedError,
  writeApiKey,
} from "./apiKey";

beforeEach(() => {
  clearApiKey();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearApiKey();
});

describe("api key storage", () => {
  it("reports no key before one is stored", () => {
    expect(readApiKey()).toBeNull();
    expect(apiKeyHeaders()).toEqual({});
  });

  it("round-trips a stored key into a request header", () => {
    writeApiKey("a-key-long-enough");

    expect(readApiKey()).toBe("a-key-long-enough");
    expect(apiKeyHeaders()).toEqual({ [API_KEY_HEADER]: "a-key-long-enough" });
  });

  it("forgets the key on request", () => {
    writeApiKey("a-key-long-enough");

    clearApiKey();

    expect(readApiKey()).toBeNull();
  });

  it("keeps the key out of persistent storage", () => {
    writeApiKey("a-key-long-enough");

    // sessionStorage ends with the tab; localStorage would outlive the session.
    expect(window.sessionStorage.getItem("aishield.apiKey")).toBe("a-key-long-enough");
    expect(window.localStorage.getItem("aishield.apiKey")).toBeNull();
  });

  it("degrades to no key when storage is unavailable", () => {
    // A private window or blocked site data makes the accessor itself throw.
    vi.stubGlobal("window", {
      get sessionStorage(): Storage {
        throw new Error("site data is blocked");
      },
    });

    expect(readApiKey()).toBeNull();
    expect(apiKeyHeaders()).toEqual({});
    expect(() => writeApiKey("a-key-long-enough")).not.toThrow();
    expect(() => clearApiKey()).not.toThrow();
  });

  it("treats an empty stored value as absent", () => {
    writeApiKey("");

    expect(readApiKey()).toBeNull();
  });
});

describe("UnauthorizedError", () => {
  it("is distinguishable from an ordinary failure", () => {
    const error = new UnauthorizedError("an API key is required");

    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(UnauthorizedError);
    expect(error.name).toBe("UnauthorizedError");
    expect(new Error("offline")).not.toBeInstanceOf(UnauthorizedError);
  });
});

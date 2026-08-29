import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, init: { ok?: boolean; status?: number } = {}) {
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    statusText: "OK",
    json: () => Promise.resolve(body),
  };
}

describe("api client", () => {
  it("sends JSON bodies with a content type", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "job-1" }));

    await api.calculateScore(["attack-1", "attack-2"]);

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/v1/registry/robustness-score");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ attack_run_ids: ["attack-1", "attack-2"] });
  });

  it("omits the content type when there is no body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));

    await api.verifyBaseline("baseline-1");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBeUndefined();
    expect(init.headers["Content-Type"]).toBeUndefined();
  });

  it("surfaces the server detail message on an error", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "all 1 evaluation slots are busy" }, { ok: false, status: 429 }),
    );

    await expect(api.attacks()).rejects.toThrow("all 1 evaluation slots are busy");
  });

  it("falls back to the HTTP status when the error body is not JSON", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: () => Promise.reject(new Error("not json")),
    });

    await expect(api.attacks()).rejects.toThrow("502 Bad Gateway");
  });

  it("builds an artifact download path bound to its run", () => {
    expect(api.artifactUrl("run-1", "artifact-2")).toBe(
      "/api/v1/registry/baselines/run-1/artifacts/artifact-2",
    );
  });

  it("reaches every registry collection the dashboard renders", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await Promise.all([
      api.defenses(),
      api.transfers(),
      api.jobs(),
      api.journal(),
      api.training(),
    ]);

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/api/v1/registry/defenses",
      "/api/v1/registry/defenses/transfer",
      "/api/v1/registry/jobs",
      "/api/v1/registry/journal",
      "/api/v1/registry/training",
    ]);
  });
});

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api";
import { makeJob } from "../test/fixtures";
import { useRegistry } from "./useRegistry";

function stubCollections(jobs = [] as ReturnType<typeof makeJob>[]) {
  vi.spyOn(api, "health").mockResolvedValue({
    status: "ok",
    service: "aishield-api",
    version: "0.1.0",
    environment: "test",
    compute_device: "cpu",
  });
  for (const name of [
    "datasets",
    "models",
    "baselines",
    "attacks",
    "defenses",
    "transfers",
    "training",
    "journal",
  ] as const) {
    vi.spyOn(api, name).mockResolvedValue([] as never);
  }
  return vi.spyOn(api, "jobs").mockResolvedValue(jobs);
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useRegistry", () => {
  it("loads every collection and reports the API as ready", async () => {
    stubCollections();

    const { result } = renderHook(() => useRegistry());

    await waitFor(() => expect(result.current.apiState).toBe("ready"));
    expect(result.current.health?.version).toBe("0.1.0");
    expect(result.current.hasPendingJob).toBe(false);
  });

  it("reports the API as offline when a collection fails", async () => {
    stubCollections();
    vi.spyOn(api, "datasets").mockRejectedValue(new Error("connection refused"));

    const { result } = renderHook(() => useRegistry());

    await waitFor(() => expect(result.current.apiState).toBe("offline"));
  });

  it("polls while a job is still running and stops once it finishes", async () => {
    const jobs = stubCollections([makeJob({ status: "running" })]);

    const { result } = renderHook(() => useRegistry());
    await waitFor(() => expect(result.current.hasPendingJob).toBe(true));

    const afterInitialLoad = jobs.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(jobs.mock.calls.length).toBeGreaterThan(afterInitialLoad);

    jobs.mockResolvedValue([makeJob({ status: "succeeded" })]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    await waitFor(() => expect(result.current.hasPendingJob).toBe(false));

    const afterSettled = jobs.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(jobs.mock.calls.length).toBe(afterSettled);
  });

  it("does not poll when nothing is pending", async () => {
    const jobs = stubCollections([makeJob({ status: "succeeded" })]);

    const { result } = renderHook(() => useRegistry());
    await waitFor(() => expect(result.current.apiState).toBe("ready"));

    const settled = jobs.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(jobs.mock.calls.length).toBe(settled);
  });
});

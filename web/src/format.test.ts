import { describe, expect, it } from "vitest";

import {
  formatBytes,
  formatDelta,
  formatDuration,
  formatPercent,
  shortHash,
  sortByCreatedAt,
} from "./format";

describe("formatPercent", () => {
  it("renders a probability with one decimal", () => {
    expect(formatPercent(0.9123)).toBe("91.2%");
    expect(formatPercent(0)).toBe("0.0%");
    expect(formatPercent(1)).toBe("100.0%");
  });
});

describe("formatBytes", () => {
  it("picks the unit from the magnitude", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("keeps the boundary values on the smaller unit", () => {
    expect(formatBytes(1023)).toBe("1023 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
  });
});

describe("shortHash", () => {
  it("keeps both ends of the digest so collisions stay visible", () => {
    const digest = "0123456789abcdef".repeat(4);
    expect(shortHash(digest)).toBe("0123456…bcdef");
  });
});

describe("formatDelta", () => {
  it("signs an improvement and a regression in percentage points", () => {
    expect(formatDelta(0.3, 0.45)).toBe("+15.0 pt");
    expect(formatDelta(0.45, 0.3)).toBe("-15.0 pt");
    expect(formatDelta(0.5, 0.5)).toBe("0.0 pt");
  });
});

describe("formatDuration", () => {
  it("returns a placeholder before the job starts", () => {
    expect(formatDuration(null, null)).toBe("—");
  });

  it("renders sub-minute durations in seconds", () => {
    expect(formatDuration("2026-08-29T00:00:00Z", "2026-08-29T00:00:12.500Z")).toBe("12.5s");
  });

  it("renders longer durations in minutes and seconds", () => {
    expect(formatDuration("2026-08-29T00:00:00Z", "2026-08-29T00:02:05Z")).toBe("2m 5s");
  });
});

describe("sortByCreatedAt", () => {
  it("orders newest first without mutating the input", () => {
    const records = [
      { created_at: "2026-08-01T00:00:00Z", id: "old" },
      { created_at: "2026-08-29T00:00:00Z", id: "new" },
      { created_at: "2026-08-15T00:00:00Z", id: "mid" },
    ];
    const original = [...records];

    expect(sortByCreatedAt(records).map((item) => item.id)).toEqual(["new", "mid", "old"]);
    expect(records).toEqual(original);
  });
});

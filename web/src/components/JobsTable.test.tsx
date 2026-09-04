import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makeJob } from "../test/fixtures";
import { JobsTable } from "./JobsTable";

describe("JobsTable", () => {
  it("invites the first queued run when empty", () => {
    render(<JobsTable jobs={[]} />);

    expect(screen.getByText(/백그라운드 작업이 없습니다/)).toBeInTheDocument();
  });

  it("shows a failed job's error as the result", () => {
    render(
      <JobsTable
        jobs={[
          makeJob({
            status: "failed",
            started_at: "2026-08-29T00:00:00Z",
            finished_at: "2026-08-29T00:00:03Z",
            error: "dataset manifest changed",
          }),
        ]}
      />,
    );

    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("dataset manifest changed")).toBeInTheDocument();
    expect(screen.getByText("3.0s")).toBeInTheDocument();
  });

  it("shows a succeeded job's result identifier", () => {
    render(
      <JobsTable
        jobs={[
          makeJob({
            status: "succeeded",
            started_at: "2026-08-29T00:00:00Z",
            finished_at: "2026-08-29T00:00:01Z",
            result_id: "abcdef12-3456-7890-abcd-ef1234567890",
          }),
        ]}
      />,
    );

    expect(screen.getByText("abcdef12")).toBeInTheDocument();
  });

  it("renders a queued job with no duration yet", () => {
    render(<JobsTable jobs={[makeJob()]} />);

    expect(screen.getByText("queued")).toBeInTheDocument();
    // Both the duration and the result column are still unknown.
    expect(screen.getAllByText("—")).toHaveLength(2);
  });
});

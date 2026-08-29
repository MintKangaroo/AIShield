import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { JournalEntry } from "../types";
import { JournalTable } from "./JournalTable";

const entries: JournalEntry[] = [
  { kind: "dataset", record: { id: "dataset-1234", created_at: "2026-08-29T00:00:00Z" } },
  { kind: "model", record: { id: "model-5678", created_at: "2026-08-29T00:01:00Z" } },
  { kind: "attack", record: { id: "attack-9012", created_at: "2026-08-29T00:02:00Z" } },
  { kind: "attack", record: { id: "attack-3456", created_at: "2026-08-29T00:03:00Z" } },
];

describe("JournalTable", () => {
  it("explains the journal instead of rendering an empty grid", () => {
    render(<JournalTable entries={[]} />);

    expect(screen.getByText(/metadata journal is empty/i)).toBeInTheDocument();
  });

  it("counts each record kind in the filter row", () => {
    render(<JournalTable entries={entries} />);

    expect(screen.getByRole("button", { name: /^all/ })).toHaveTextContent("4");
    expect(screen.getByRole("button", { name: /^attack/ })).toHaveTextContent("2");
  });

  it("filters the listing down to one kind", async () => {
    render(<JournalTable entries={entries} />);

    await userEvent.click(screen.getByRole("button", { name: /^attack/ }));

    expect(screen.getByText("attack-9")).toBeInTheDocument();
    expect(screen.queryByText("dataset-")).not.toBeInTheDocument();
  });

  it("expands one entry to its raw JSON and collapses it again", async () => {
    render(<JournalTable entries={entries} />);
    const row = screen.getAllByRole("button", { expanded: false })[0];

    await userEvent.click(row);
    expect(screen.getByText(/"id": "dataset-1234"/)).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { expanded: true })[0]);
    expect(screen.queryByText(/"id": "dataset-1234"/)).not.toBeInTheDocument();
  });

  it("reads the identity of a nested experiment envelope", () => {
    render(
      <JournalTable
        entries={[
          {
            kind: "experiment",
            record: {
              experiment: { id: "exp-77889900", created_at: "2026-08-29T00:05:00Z" },
            },
          },
        ]}
      />,
    );

    expect(screen.getByText("exp-7788")).toBeInTheDocument();
    expect(screen.getByText("2026-08-29T00:05:00Z")).toBeInTheDocument();
  });

  it("renders a record with no id or timestamp without crashing", () => {
    render(<JournalTable entries={[{ kind: "job", record: { status: "queued" } }]} />);

    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ComparisonView } from "./ComparisonView";
import type { Comparison } from "../compare";

function comparison(overrides: Partial<Comparison> = {}): Comparison {
  return {
    comparable: true,
    blockers: [],
    notes: [],
    sections: [
      {
        title: "Metrics",
        rows: [
          {
            label: "Clean accuracy",
            left: "90.0%",
            right: "95.0%",
            delta: { text: "+5.00 pt", direction: "up" },
            differs: true,
            provenance: false,
          },
        ],
      },
    ],
    ...overrides,
  };
}

describe("ComparisonView", () => {
  it("shows a comparable verdict and the delta", () => {
    render(<ComparisonView comparison={comparison()} />);

    expect(screen.getByText("Comparable")).toBeInTheDocument();
    expect(screen.getByText("+5.00 pt")).toBeInTheDocument();
  });

  it("surfaces blockers and marks the comparison uncontrolled", () => {
    render(
      <ComparisonView
        comparison={comparison({
          comparable: false,
          blockers: ["These runs used different datasets."],
        })}
      />,
    );

    expect(screen.getByText("Not a controlled comparison")).toBeInTheDocument();
    expect(screen.getByText("These runs used different datasets.")).toBeInTheDocument();
  });

  it("renders interpretation notes without blocking", () => {
    render(
      <ComparisonView comparison={comparison({ notes: ["torch differs: 2.13.0 → 2.14.0."] })} />,
    );

    expect(screen.getByText("torch differs: 2.13.0 → 2.14.0.")).toBeInTheDocument();
    expect(screen.getByText("Comparable")).toBeInTheDocument();
  });
});

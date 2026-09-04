import { describe, expect, it } from "vitest";

import { compareAttacks, compareBaselines } from "./compare";
import { makeAttack, makeDataset, makeModel } from "./test/fixtures";
import type { BaselineRunRecord } from "./types";

const datasets = [makeDataset(), makeDataset({ id: "dataset-2", name: "mnist" })];
const models = [makeModel(), makeModel({ id: "model-2", architecture: "ResNet18" })];

function makeBaseline(overrides: Partial<BaselineRunRecord> = {}): BaselineRunRecord {
  return {
    id: "baseline-1",
    created_at: "2026-08-29T00:00:00Z",
    model_version_id: "model-1",
    model_state_sha256: "b".repeat(64),
    model_artifact_sha256: "c".repeat(64),
    dataset_id: "dataset-1",
    dataset_manifest_sha256: "a".repeat(64),
    config: { seed: 1729, batch_size: 64, max_samples: 256, warmup_batches: 1, num_workers: 0 },
    environment: {
      python_version: "3.12.13",
      platform: "linux",
      package_versions: { torch: "2.13.0" },
      git_commit: null,
      container_image_digest: null,
      device: "cpu",
      cuda_version: null,
      cudnn_version: null,
      deterministic_algorithms: true,
    },
    metrics: {
      clean_accuracy: 0.9,
      robust_accuracy: null,
      robust_accuracy_status: "not_evaluated",
      mean_loss: 0.35,
      evaluated_samples: 256,
      confusion_matrix: [[1, 0], [0, 1]],
      per_class: [],
      latency: {
        warmup_batches: 1,
        measured_batches: 4,
        total_forward_ms: 100,
        mean_ms_per_sample: 0.4,
        p50_ms_per_sample: 0.4,
        p95_ms_per_sample: 0.5,
        includes_preprocessing: false,
      },
      prediction_sha256: "d".repeat(64),
    },
    artifacts: [],
    ...overrides,
  };
}

function rowsOf(sections: { rows: { label: string }[] }[]) {
  return sections.flatMap((section) => section.rows);
}

function row(sections: { rows: { label: string }[] }[], label: string) {
  const found = rowsOf(sections).find((item) => item.label === label);
  if (!found) throw new Error(`no row labelled ${label}`);
  return found as never as import("./compare").ComparisonRow;
}

describe("compareBaselines", () => {
  it("treats identical targets and seeds as comparable", () => {
    const result = compareBaselines(makeBaseline(), makeBaseline({ id: "b2" }), datasets, models);

    expect(result.comparable).toBe(true);
    expect(result.blockers).toEqual([]);
  });

  it("reports the accuracy delta in percentage points", () => {
    const result = compareBaselines(
      makeBaseline(),
      makeBaseline({ metrics: { ...makeBaseline().metrics, clean_accuracy: 0.95 } }),
      datasets,
      models,
    );

    expect(row(result.sections, "Clean accuracy").delta).toEqual({
      text: "+5.00 pt",
      direction: "up",
    });
  });

  it("marks an unchanged metric as flat rather than zero", () => {
    const result = compareBaselines(makeBaseline(), makeBaseline(), datasets, models);

    expect(row(result.sections, "Clean accuracy").delta).toEqual({
      text: "no change",
      direction: "flat",
    });
  });

  it("refuses to call runs on different models comparable", () => {
    const result = compareBaselines(
      makeBaseline(),
      makeBaseline({ model_version_id: "model-2" }),
      datasets,
      models,
    );

    expect(result.comparable).toBe(false);
    expect(result.blockers.join(" ")).toContain("different model versions");
  });

  it("refuses to call runs on different datasets comparable", () => {
    const result = compareBaselines(
      makeBaseline(),
      makeBaseline({ dataset_id: "dataset-2" }),
      datasets,
      models,
    );

    expect(result.comparable).toBe(false);
    expect(result.blockers.join(" ")).toContain("different datasets");
  });

  it("blocks when the sample populations differ", () => {
    const base = makeBaseline();
    const result = compareBaselines(
      base,
      makeBaseline({ metrics: { ...base.metrics, evaluated_samples: 128 } }),
      datasets,
      models,
    );

    expect(result.comparable).toBe(false);
    expect(result.blockers.join(" ")).toContain("different sample counts");
  });

  it("blocks a different seed, because part of the delta is variance", () => {
    const base = makeBaseline();
    const result = compareBaselines(
      base,
      makeBaseline({ config: { ...base.config, seed: 7 } }),
      datasets,
      models,
    );

    expect(result.comparable).toBe(false);
    expect(result.blockers.join(" ")).toContain("run-to-run variance");
  });

  it("notes a dependency change without blocking the comparison", () => {
    const base = makeBaseline();
    const result = compareBaselines(
      base,
      makeBaseline({
        environment: { ...base.environment, package_versions: { torch: "2.14.0" } },
      }),
      datasets,
      models,
    );

    expect(result.comparable).toBe(true);
    expect(result.notes.join(" ")).toContain("torch differs: 2.13.0 → 2.14.0");
  });

  it("notes a device change as making latency incomparable", () => {
    const base = makeBaseline();
    const result = compareBaselines(
      base,
      makeBaseline({ environment: { ...base.environment, device: "cuda" } }),
      datasets,
      models,
    );

    expect(result.notes.join(" ")).toContain("latency is not comparable");
  });

  it("labels provenance rows so a difference is not read as a result", () => {
    const result = compareBaselines(makeBaseline(), makeBaseline(), datasets, models);

    expect(row(result.sections, "Model state").provenance).toBe(true);
    expect(row(result.sections, "Clean accuracy").provenance).toBe(false);
  });

  it("shows unrecorded provenance as unrecorded rather than blank", () => {
    const result = compareBaselines(makeBaseline(), makeBaseline(), datasets, models);

    expect(row(result.sections, "Image digest").left).toBe("unrecorded");
    expect(row(result.sections, "Git commit").left).toBe("unrecorded");
  });
});

describe("compareAttacks", () => {
  it("reports robust accuracy and attack success deltas", () => {
    const base = makeAttack();
    const result = compareAttacks(
      base,
      makeAttack({
        id: "attack-2",
        metrics: { ...base.metrics, robust_accuracy: 0.5, attack_success_rate: 0.4 },
      }),
      datasets,
      models,
    );

    expect(row(result.sections, "Robust accuracy").delta?.direction).toBe("up");
    expect(row(result.sections, "Attack success rate").delta?.direction).toBe("down");
  });

  it("warns that a different epsilon does not mean a more robust model", () => {
    const base = makeAttack();
    const result = compareAttacks(
      base,
      makeAttack({ config: { ...base.config, epsilon: 2 / 255 } }),
      datasets,
      models,
    );

    expect(result.notes.join(" ")).toContain("not evidence of a more robust model");
  });

  it("warns when either run reported a flat gradient", () => {
    const base = makeAttack();
    const result = compareAttacks(
      base,
      makeAttack({ metrics: { ...base.metrics, gradient_status: "flat" } }),
      datasets,
      models,
    );

    expect(result.notes.join(" ")).toContain("masking signal");
  });

  it("notes that comparing two algorithms compares attacks, not models", () => {
    const base = makeAttack();
    const result = compareAttacks(
      base,
      makeAttack({ config: { ...base.config, algorithm: "pgd" } }),
      datasets,
      models,
    );

    expect(result.notes.join(" ")).toContain("compares attacks, not model changes");
  });

  it("stays comparable when only the metrics differ", () => {
    const base = makeAttack();
    const result = compareAttacks(
      base,
      makeAttack({ metrics: { ...base.metrics, robust_accuracy: 0.31 } }),
      datasets,
      models,
    );

    expect(result.comparable).toBe(true);
    expect(result.blockers).toEqual([]);
  });

  it("renders an unknown target rather than crashing", () => {
    const result = compareAttacks(
      makeAttack({ model_version_id: "missing", dataset_id: "missing" }),
      makeAttack({ model_version_id: "missing", dataset_id: "missing" }),
      datasets,
      models,
    );

    expect(row(result.sections, "Model").left).toBe("unknown");
    expect(row(result.sections, "Dataset").left).toBe("unknown");
  });
});

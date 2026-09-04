/**
 * Run-to-run comparison.
 *
 * The hard part is not rendering two columns of numbers — it is refusing to
 * imply a conclusion the evidence does not support. Two runs are only
 * comparable when they targeted the same model and dataset over the same sample
 * population; otherwise the deltas are arithmetic, not findings. Every
 * disqualifying difference is reported rather than quietly folded into a number.
 */

import { formatPercent, shortHash } from "./format";
import type { AttackRunRecord, BaselineRunRecord, DatasetRecord, ModelVersionRecord } from "./types";

export type Direction = "up" | "down" | "flat";

export interface ComparisonRow {
  label: string;
  left: string;
  right: string;
  /** Absent when the values are not numeric, so no arithmetic is implied. */
  delta?: { text: string; direction: Direction };
  differs: boolean;
  /** Recorded for provenance rather than measured; a difference is not a result. */
  provenance?: boolean;
}

export interface ComparisonSection {
  title: string;
  rows: ComparisonRow[];
}

export interface Comparison {
  sections: ComparisonSection[];
  /** Reasons the two runs cannot be read as a controlled comparison. */
  blockers: string[];
  /** Differences worth knowing about that do not invalidate the comparison. */
  notes: string[];
  comparable: boolean;
}

function textRow(
  label: string,
  left: string,
  right: string,
  provenance = false,
): ComparisonRow {
  return { label, left, right, differs: left !== right, provenance };
}

/** A numeric row carrying an explicit delta, so the reader never subtracts by eye. */
function numberRow(
  label: string,
  left: number,
  right: number,
  render: (value: number) => string,
  renderDelta: (delta: number) => string,
  epsilon = 1e-9,
): ComparisonRow {
  const difference = right - left;
  const direction: Direction =
    Math.abs(difference) <= epsilon ? "flat" : difference > 0 ? "up" : "down";
  return {
    label,
    left: render(left),
    right: render(right),
    delta: { text: direction === "flat" ? "no change" : renderDelta(difference), direction },
    differs: direction !== "flat",
    provenance: false,
  };
}

const percent = (value: number) => formatPercent(value);
const points = (delta: number) => `${delta > 0 ? "+" : ""}${(delta * 100).toFixed(2)} pt`;
const fixed4 = (value: number) => value.toFixed(4);
const signed4 = (delta: number) => `${delta > 0 ? "+" : ""}${delta.toFixed(4)}`;

function targetBlockers(
  left: { model_version_id: string; dataset_id: string },
  right: { model_version_id: string; dataset_id: string },
  leftSamples: number,
  rightSamples: number,
): string[] {
  const blockers: string[] = [];
  if (left.model_version_id !== right.model_version_id) {
    blockers.push(
      "These runs used different model versions, so a difference in accuracy cannot be attributed to anything else.",
    );
  }
  if (left.dataset_id !== right.dataset_id) {
    blockers.push(
      "These runs used different datasets. Metrics measured on different data are not comparable.",
    );
  }
  if (leftSamples !== rightSamples) {
    blockers.push(
      `These runs evaluated different sample counts (${leftSamples} and ${rightSamples}), so the populations differ.`,
    );
  }
  return blockers;
}

function environmentNotes(
  left: BaselineRunRecord["environment"],
  right: BaselineRunRecord["environment"],
): string[] {
  const notes: string[] = [];
  if (left.device !== right.device) {
    notes.push(`Different devices (${left.device} and ${right.device}); latency is not comparable.`);
  }
  for (const name of new Set([
    ...Object.keys(left.package_versions),
    ...Object.keys(right.package_versions),
  ])) {
    const before = left.package_versions[name];
    const after = right.package_versions[name];
    if (before !== after) {
      notes.push(`${name} differs: ${before ?? "absent"} → ${after ?? "absent"}.`);
    }
  }
  if (left.container_image_digest !== right.container_image_digest) {
    notes.push("The runs were produced by different container images.");
  }
  if (left.git_commit !== right.git_commit) {
    notes.push("The runs were produced by different source commits.");
  }
  return notes;
}

function environmentSection(
  left: BaselineRunRecord["environment"],
  right: BaselineRunRecord["environment"],
): ComparisonSection {
  return {
    title: "Environment",
    rows: [
      textRow("Device", left.device, right.device, true),
      textRow("Torch", left.package_versions.torch ?? "—", right.package_versions.torch ?? "—", true),
      textRow(
        "Image digest",
        left.container_image_digest ? shortHash(left.container_image_digest) : "unrecorded",
        right.container_image_digest ? shortHash(right.container_image_digest) : "unrecorded",
        true,
      ),
      textRow(
        "Git commit",
        left.git_commit ? left.git_commit.slice(0, 12) : "unrecorded",
        right.git_commit ? right.git_commit.slice(0, 12) : "unrecorded",
        true,
      ),
    ],
  };
}

function nameOf(records: { id: string }[], id: string, label: (record: never) => string): string {
  const found = records.find((record) => record.id === id);
  return found ? label(found as never) : "unknown";
}

export function compareBaselines(
  left: BaselineRunRecord,
  right: BaselineRunRecord,
  datasets: DatasetRecord[],
  models: ModelVersionRecord[],
): Comparison {
  const blockers = targetBlockers(
    left,
    right,
    left.metrics.evaluated_samples,
    right.metrics.evaluated_samples,
  );
  if (left.config.seed !== right.config.seed) {
    blockers.push(
      `These runs used different seeds (${left.config.seed} and ${right.config.seed}), so part of the difference is run-to-run variance.`,
    );
  }

  return {
    comparable: blockers.length === 0,
    blockers,
    notes: environmentNotes(left.environment, right.environment),
    sections: [
      {
        title: "Target",
        rows: [
          textRow(
            "Model",
            nameOf(models, left.model_version_id, (m: ModelVersionRecord) => m.architecture),
            nameOf(models, right.model_version_id, (m: ModelVersionRecord) => m.architecture),
            true,
          ),
          textRow(
            "Dataset",
            nameOf(datasets, left.dataset_id, (d: DatasetRecord) => d.name.toUpperCase()),
            nameOf(datasets, right.dataset_id, (d: DatasetRecord) => d.name.toUpperCase()),
            true,
          ),
          textRow("Model state", shortHash(left.model_state_sha256), shortHash(right.model_state_sha256), true),
          textRow(
            "Dataset manifest",
            shortHash(left.dataset_manifest_sha256),
            shortHash(right.dataset_manifest_sha256),
            true,
          ),
        ],
      },
      {
        title: "Metrics",
        rows: [
          numberRow(
            "Clean accuracy",
            left.metrics.clean_accuracy,
            right.metrics.clean_accuracy,
            percent,
            points,
          ),
          numberRow("Mean loss", left.metrics.mean_loss, right.metrics.mean_loss, fixed4, signed4),
          numberRow(
            "Latency / sample",
            left.metrics.latency.mean_ms_per_sample,
            right.metrics.latency.mean_ms_per_sample,
            (value) => `${value.toFixed(2)} ms`,
            (delta) => `${delta > 0 ? "+" : ""}${delta.toFixed(2)} ms`,
          ),
        ],
      },
      {
        title: "Configuration",
        rows: [
          textRow("Seed", String(left.config.seed), String(right.config.seed), true),
          textRow("Batch size", String(left.config.batch_size), String(right.config.batch_size), true),
          textRow(
            "Samples",
            String(left.metrics.evaluated_samples),
            String(right.metrics.evaluated_samples),
            true,
          ),
          textRow(
            "Prediction fingerprint",
            shortHash(left.metrics.prediction_sha256),
            shortHash(right.metrics.prediction_sha256),
            true,
          ),
        ],
      },
      environmentSection(left.environment, right.environment),
    ],
  };
}

export function compareAttacks(
  left: AttackRunRecord,
  right: AttackRunRecord,
  datasets: DatasetRecord[],
  models: ModelVersionRecord[],
): Comparison {
  const blockers = targetBlockers(
    left,
    right,
    left.metrics.evaluated_samples,
    right.metrics.evaluated_samples,
  );
  const notes = environmentNotes(left.environment, right.environment);
  if (left.config.algorithm !== right.config.algorithm) {
    notes.push(
      `Different algorithms (${left.config.algorithm.toUpperCase()} and ${right.config.algorithm.toUpperCase()}); this compares attacks, not model changes.`,
    );
  }
  if (Math.abs(left.config.epsilon - right.config.epsilon) > 1e-12) {
    notes.push(
      "Different epsilon bounds; a weaker attack producing higher robust accuracy is expected, not evidence of a more robust model.",
    );
  }
  if (left.metrics.gradient_status === "flat" || right.metrics.gradient_status === "flat") {
    notes.push(
      "At least one run reported a flat gradient. Treat its robust accuracy as a masking signal rather than a robustness result.",
    );
  }

  return {
    comparable: blockers.length === 0,
    blockers,
    notes,
    sections: [
      {
        title: "Target",
        rows: [
          textRow(
            "Model",
            nameOf(models, left.model_version_id, (m: ModelVersionRecord) => m.architecture),
            nameOf(models, right.model_version_id, (m: ModelVersionRecord) => m.architecture),
            true,
          ),
          textRow(
            "Dataset",
            nameOf(datasets, left.dataset_id, (d: DatasetRecord) => d.name.toUpperCase()),
            nameOf(datasets, right.dataset_id, (d: DatasetRecord) => d.name.toUpperCase()),
            true,
          ),
          textRow("Algorithm", left.config.algorithm.toUpperCase(), right.config.algorithm.toUpperCase(), true),
          textRow("Norm", left.config.norm === "l2" ? "L2" : "L∞", right.config.norm === "l2" ? "L2" : "L∞", true),
        ],
      },
      {
        title: "Metrics",
        rows: [
          numberRow(
            "Clean accuracy",
            left.metrics.clean_accuracy,
            right.metrics.clean_accuracy,
            percent,
            points,
          ),
          numberRow(
            "Robust accuracy",
            left.metrics.robust_accuracy,
            right.metrics.robust_accuracy,
            percent,
            points,
          ),
          numberRow(
            "Attack success rate",
            left.metrics.attack_success_rate,
            right.metrics.attack_success_rate,
            percent,
            points,
          ),
          numberRow(
            "Successful attacks",
            left.metrics.successful_attacks,
            right.metrics.successful_attacks,
            (value) => String(value),
            (delta) => `${delta > 0 ? "+" : ""}${delta}`,
          ),
        ],
      },
      {
        title: "Bound",
        rows: [
          numberRow(
            "Epsilon",
            left.config.epsilon,
            right.config.epsilon,
            (value) => `${(value * 255).toFixed(1)} / 255`,
            (delta) => `${delta > 0 ? "+" : ""}${(delta * 255).toFixed(1)} / 255`,
          ),
          numberRow(
            "Observed L∞",
            left.metrics.maximum_observed_linf,
            right.metrics.maximum_observed_linf,
            (value) => `${(value * 255).toFixed(2)} / 255`,
            (delta) => `${delta > 0 ? "+" : ""}${(delta * 255).toFixed(2)} / 255`,
          ),
          textRow("Iterations", String(left.config.iterations), String(right.config.iterations), true),
          textRow(
            "Gradient",
            left.metrics.gradient_status,
            right.metrics.gradient_status,
            true,
          ),
        ],
      },
      environmentSection(left.environment, right.environment),
    ],
  };
}

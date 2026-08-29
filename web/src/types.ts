export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  compute_device: "cpu" | "cuda";
}

export interface DatasetRecord {
  id: string;
  name: "synthetic" | "mnist" | "cifar10";
  version: string;
  split: "train" | "test";
  source: "generated" | "approved_public";
  source_uri: string;
  manifest_sha256: string;
  sample_count: number;
  num_classes: number;
  input_shape: [number, number, number];
  transform: string;
  torchvision_version: string;
}

export interface ModelArtifactRecord {
  uri: string;
  sha256: string;
  size_bytes: number;
  format: "pytorch_state_dict";
}

export interface ModelVersionRecord {
  id: string;
  name: string;
  version: string;
  source: "small_cnn" | "torchvision" | "trained";
  framework: "pytorch";
  framework_version: string;
  torchvision_version: string | null;
  architecture: string;
  weights: string | null;
  seed: number;
  num_classes: number;
  input_channels: number;
  parameter_count: number;
  state_dict_sha256: string;
  preprocessing: string;
  device: "cpu" | "cuda";
  artifact: ModelArtifactRecord;
}

export interface PerClassMetric {
  class_index: number;
  precision: number;
  recall: number;
  support: number;
}

export interface BaselineArtifact {
  id: string;
  kind: "baseline_report" | "confusion_matrix";
  uri: string;
  sha256: string;
  media_type: "application/json" | "image/png";
  size_bytes: number;
}

export interface BaselineRunRecord {
  id: string;
  created_at: string;
  model_version_id: string;
  model_state_sha256: string;
  model_artifact_sha256: string;
  dataset_id: string;
  dataset_manifest_sha256: string;
  config: {
    seed: number;
    batch_size: number;
    max_samples: number | null;
    warmup_batches: number;
    num_workers: 0;
  };
  environment: {
    python_version: string;
    platform: string;
    package_versions: Record<string, string>;
    git_commit: string | null;
    container_image_digest: string | null;
    device: "cpu" | "cuda";
    cuda_version: string | null;
    cudnn_version: string | null;
    deterministic_algorithms: true;
  };
  metrics: {
    clean_accuracy: number;
    robust_accuracy: null;
    robust_accuracy_status: "not_evaluated";
    mean_loss: number;
    evaluated_samples: number;
    confusion_matrix: number[][];
    per_class: PerClassMetric[];
    latency: {
      warmup_batches: number;
      measured_batches: number;
      total_forward_ms: number;
      mean_ms_per_sample: number;
      p50_ms_per_sample: number;
      p95_ms_per_sample: number;
      includes_preprocessing: false;
    };
    prediction_sha256: string;
  };
  artifacts: BaselineArtifact[];
}

export interface BaselineVerification {
  reference_run_id: string;
  rerun: BaselineRunRecord;
  reproducible: boolean;
  loss_absolute_tolerance: number;
  checks: Array<{
    name: string;
    passed: boolean;
    detail: string;
  }>;
  excluded_from_pass_fail: ["latency"];
}

export interface BaselineRequest {
  model_version_id: string;
  dataset_id: string;
  seed: number;
  batch_size: number;
  max_samples: number | null;
  warmup_batches: number;
}

export interface AttackRunRecord {
  id: string;
  created_at: string;
  model_version_id: string;
  model_state_sha256: string;
  dataset_id: string;
  dataset_manifest_sha256: string;
  config: {
    algorithm: AttackAlgorithm;
    norm: "linf" | "l2";
    epsilon: number;
    step_size: number;
    iterations: number;
    random_start: boolean;
    targeted: false;
    seed: number;
    batch_size: number;
    max_samples: number | null;
  };
  environment: BaselineRunRecord["environment"];
  metrics: {
    clean_accuracy: number;
    robust_accuracy: number;
    attack_success_rate: number;
    evaluated_samples: number;
    clean_correct_samples: number;
    successful_attacks: number;
    maximum_observed_linf: number;
    maximum_observed_l2: number;
    clean_prediction_sha256: string;
    adversarial_prediction_sha256: string;
    gradient_status: "healthy" | "flat";
  };
  warnings: string[];
}

export interface AttackRequest {
  model_version_id: string;
  dataset_id: string;
  algorithm: AttackAlgorithm;
  norm?: "linf" | "l2";
  epsilon: number;
  step_size?: number;
  iterations?: number;
  random_start?: boolean;
  seed: number;
  batch_size: number;
  max_samples: number | null;
}

export interface AttackCurveRequest {
  model_version_id: string;
  dataset_id: string;
  algorithm: "pgd" | "apgd" | "fab" | "square";
  epsilons: number[];
  step_fraction: number;
  iterations: number;
  restarts: number;
  seed: number;
  batch_size: number;
  max_samples: number | null;
}

export type TrainingStrategy = "adversarial_training" | "trades";

export interface TrainingRunRecord {
  id: string;
  created_at: string;
  source_model_version_id: string;
  trained_model_version_id: string;
  dataset_id: string;
  dataset_manifest_sha256: string;
  config: {
    strategy: TrainingStrategy;
    seed: number;
    epochs: number;
    batch_size: number;
    max_samples: number | null;
    epsilon: number;
    step_size: number;
    attack_iterations: number;
    learning_rate: number;
    trades_beta: number;
    num_workers: 0;
  };
  model_state_sha256: string;
  artifact: ModelArtifactRecord;
  environment: BaselineRunRecord["environment"];
  metrics: {
    epochs_completed: number;
    training_samples: number;
    final_training_loss: number;
    final_clean_accuracy: number;
    final_robust_accuracy: number;
    final_attack_success_rate: number;
  };
}

export interface TrainingRequest {
  model_version_id: string;
  dataset_id: string;
  strategy: TrainingStrategy;
  seed: number;
  epochs: number;
  batch_size: number;
  max_samples: number | null;
  epsilon: number;
  step_size: number;
  attack_iterations: number;
  learning_rate: number;
  trades_beta: number;
}

export type AttackAlgorithm =
  | "fgsm"
  | "bim"
  | "pgd"
  | "deepfool"
  | "cw"
  | "autoattack"
  | "apgd"
  | "fab"
  | "square";

export type DefenseKind = "bit_depth";

export interface DefenseRunRecord {
  id: string;
  created_at: string;
  model_version_id: string;
  model_state_sha256: string;
  dataset_id: string;
  dataset_manifest_sha256: string;
  defense: {
    kind: DefenseKind;
    bit_depth: number;
  };
  attack_algorithm: AttackAlgorithm;
  environment: BaselineRunRecord["environment"];
  metrics: {
    clean_accuracy_before: number;
    clean_accuracy_after: number;
    robust_accuracy_before: number;
    robust_accuracy_after: number;
    attack_success_rate_before: number;
    attack_success_rate_after: number;
    evaluated_samples: number;
    adaptive_gradient_status: "healthy" | "flat";
  };
  warnings: string[];
}

export interface DefenseRequest {
  model_version_id: string;
  dataset_id: string;
  defense: DefenseKind;
  bit_depth: number;
  attack_algorithm: AttackAlgorithm;
  epsilon: number;
  step_size?: number;
  iterations?: number;
  seed: number;
  batch_size: number;
  max_samples: number | null;
}

export interface TransferRunRecord {
  id: string;
  created_at: string;
  surrogate_model_version_id: string;
  target_model_version_id: string;
  dataset_id: string;
  dataset_manifest_sha256: string;
  attack: AttackRunRecord["config"];
  environment: BaselineRunRecord["environment"];
  metrics: {
    clean_accuracy: number;
    transferred_robust_accuracy: number;
    transfer_attack_success_rate: number;
    evaluated_samples: number;
    clean_correct_samples: number;
    successful_transfers: number;
    maximum_observed_linf: number;
  };
  warnings: string[];
}

export interface TransferRequest {
  surrogate_model_version_id: string;
  target_model_version_id: string;
  dataset_id: string;
  algorithm: AttackAlgorithm;
  epsilon: number;
  step_size?: number;
  iterations: number;
  seed: number;
  batch_size: number;
  max_samples: number | null;
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface JobRecord {
  id: string;
  kind: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result_id: string | null;
  error: string | null;
}

export interface RobustnessScore {
  formula_version: string;
  model_version_id: string;
  dataset_id: string;
  attack_run_ids: string[];
  score: number;
  evidence_coverage: number;
  attacks_used: string[];
  warnings: string[];
}

export interface JournalEntry {
  kind: string;
  record: Record<string, unknown>;
}

export interface JournalReplaySummary {
  entries_read: number;
  datasets_restored: number;
  models_restored: number;
  baselines_restored: number;
  attacks_restored: number;
  defenses_restored: number;
  transfers_restored: number;
  training_restored: number;
  experiments_restored: number;
  jobs_skipped: number;
  skipped: string[];
}

/**
 * The portable experiment envelope. The dashboard moves it between the export
 * and import endpoints without interpreting it, so it is intentionally opaque
 * apart from the identity fields shown in the UI.
 */
export interface ExperimentResult {
  schema_version: "1.0";
  experiment: {
    id: string;
    name: string;
    status: string;
    seed: number;
    dataset_id: string;
    model_version_id: string;
    created_at: string;
  };
  attack_runs: unknown[];
  defense_runs: unknown[];
  metrics: unknown[];
  artifacts: unknown[];
  robustness_score: { version: string; value: number } | null;
  [key: string]: unknown;
}

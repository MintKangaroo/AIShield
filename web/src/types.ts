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
  source: "small_cnn" | "torchvision";
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
    algorithm: "fgsm" | "pgd";
    norm: "linf";
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
    clean_prediction_sha256: string;
    adversarial_prediction_sha256: string;
    gradient_status: "healthy" | "flat";
  };
  warnings: string[];
}

export interface AttackRequest {
  model_version_id: string;
  dataset_id: string;
  algorithm: "fgsm" | "pgd";
  epsilon: number;
  step_size?: number;
  iterations?: number;
  random_start?: boolean;
  seed: number;
  batch_size: number;
  max_samples: number | null;
}

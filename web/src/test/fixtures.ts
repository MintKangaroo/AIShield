import type {
  AttackRunRecord,
  BaselineRunRecord,
  DatasetRecord,
  JobRecord,
  ModelVersionRecord,
} from "../types";

const environment: BaselineRunRecord["environment"] = {
  python_version: "3.12.13",
  platform: "linux",
  package_versions: { torch: "2.13.0" },
  git_commit: null,
  container_image_digest: null,
  device: "cpu",
  cuda_version: null,
  cudnn_version: null,
  deterministic_algorithms: true,
};

export function makeDataset(overrides: Partial<DatasetRecord> = {}): DatasetRecord {
  return {
    id: "dataset-1",
    name: "synthetic",
    version: "1.0.0",
    split: "test",
    source: "generated",
    source_uri: "generated://signal-10",
    manifest_sha256: "a".repeat(64),
    sample_count: 256,
    num_classes: 10,
    input_shape: [1, 28, 28],
    transform: "to_tensor",
    torchvision_version: "0.28.0",
    ...overrides,
  };
}

export function makeModel(overrides: Partial<ModelVersionRecord> = {}): ModelVersionRecord {
  return {
    id: "model-1",
    name: "SmallCNN",
    version: "1.0.0",
    source: "small_cnn",
    framework: "pytorch",
    framework_version: "2.13.0",
    torchvision_version: "0.28.0",
    architecture: "SmallCNN",
    weights: null,
    seed: 1729,
    num_classes: 10,
    input_channels: 1,
    parameter_count: 1234,
    state_dict_sha256: "b".repeat(64),
    preprocessing: "identity",
    device: "cpu",
    artifact: {
      uri: "file:///artifacts/models/model-1.pt",
      sha256: "c".repeat(64),
      size_bytes: 4096,
      format: "pytorch_state_dict",
    },
    ...overrides,
  };
}

export function makeAttack(overrides: Partial<AttackRunRecord> = {}): AttackRunRecord {
  return {
    id: "attack-1",
    created_at: "2026-08-29T00:00:00Z",
    model_version_id: "model-1",
    model_state_sha256: "b".repeat(64),
    dataset_id: "dataset-1",
    dataset_manifest_sha256: "a".repeat(64),
    config: {
      algorithm: "fgsm",
      norm: "linf",
      epsilon: 8 / 255,
      step_size: 8 / 255,
      iterations: 1,
      random_start: false,
      targeted: false,
      seed: 1729,
      batch_size: 64,
      max_samples: 256,
    },
    environment,
    metrics: {
      clean_accuracy: 0.9,
      robust_accuracy: 0.3,
      attack_success_rate: 0.66,
      evaluated_samples: 256,
      clean_correct_samples: 230,
      successful_attacks: 152,
      maximum_observed_linf: 8 / 255,
      maximum_observed_l2: 0.4,
      clean_prediction_sha256: "d".repeat(64),
      adversarial_prediction_sha256: "e".repeat(64),
      gradient_status: "healthy",
    },
    warnings: [],
    ...overrides,
  };
}

export function makeJob(overrides: Partial<JobRecord> = {}): JobRecord {
  return {
    id: "11111111-2222-3333-4444-555555555555",
    kind: "training",
    status: "queued",
    created_at: "2026-08-29T00:00:00Z",
    started_at: null,
    finished_at: null,
    result_id: null,
    error: null,
    ...overrides,
  };
}

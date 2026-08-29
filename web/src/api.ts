import type {
  AttackCurveRequest,
  AttackRequest,
  AttackRunRecord,
  BaselineRequest,
  BaselineRunRecord,
  BaselineVerification,
  DatasetRecord,
  DefenseRequest,
  DefenseRunRecord,
  ExperimentResult,
  HealthResponse,
  JobRecord,
  JournalEntry,
  JournalReplaySummary,
  ModelVersionRecord,
  RobustnessScore,
  TrainingRequest,
  TrainingRunRecord,
  TransferRequest,
  TransferRunRecord,
} from "./types";

const registryPath = "/api/v1/registry";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Preserve the HTTP status when the server did not return structured JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function post<T>(path: string, payload?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
}

export const api = {
  health: () => request<HealthResponse>("/api/v1/health/live"),
  datasets: () => request<DatasetRecord[]>(`${registryPath}/datasets`),
  models: () => request<ModelVersionRecord[]>(`${registryPath}/models`),
  baselines: () => request<BaselineRunRecord[]>(`${registryPath}/baselines`),
  attacks: () => request<AttackRunRecord[]>(`${registryPath}/attacks`),
  defenses: () => request<DefenseRunRecord[]>(`${registryPath}/defenses`),
  transfers: () => request<TransferRunRecord[]>(`${registryPath}/defenses/transfer`),
  training: () => request<TrainingRunRecord[]>(`${registryPath}/training`),
  jobs: () => request<JobRecord[]>(`${registryPath}/jobs`),
  job: (jobId: string) => request<JobRecord>(`${registryPath}/jobs/${jobId}`),
  journal: () => request<JournalEntry[]>(`${registryPath}/journal`),
  replayJournal: () => post<JournalReplaySummary>(`${registryPath}/journal/replay`),
  experiments: () => request<ExperimentResult[]>(`${registryPath}/experiments`),
  importExperiment: (envelope: ExperimentResult) =>
    post<ExperimentResult>(`${registryPath}/experiments`, envelope),
  loadDataset: (payload: {
    name: DatasetRecord["name"];
    split: DatasetRecord["split"];
    download: boolean;
  }) => post<DatasetRecord>(`${registryPath}/datasets`, payload),
  loadSmallCnn: (payload: { dataset_id: string; seed: number; checkpoint?: string }) =>
    post<ModelVersionRecord>(`${registryPath}/models/small-cnn`, payload),
  runBaseline: (payload: BaselineRequest) =>
    post<BaselineRunRecord>(`${registryPath}/baselines`, payload),
  runAttack: (payload: AttackRequest) =>
    post<AttackRunRecord>(`${registryPath}/attacks`, payload),
  runAttackCurve: (payload: AttackCurveRequest) =>
    post<AttackRunRecord[]>(`${registryPath}/attack-curves`, payload),
  runDefense: (payload: DefenseRequest) =>
    post<DefenseRunRecord>(`${registryPath}/defenses`, payload),
  runTransfer: (payload: TransferRequest) =>
    post<TransferRunRecord>(`${registryPath}/defenses/transfer`, payload),
  runTraining: (payload: TrainingRequest) =>
    post<TrainingRunRecord>(`${registryPath}/training`, payload),
  queueTraining: (payload: TrainingRequest) =>
    post<JobRecord>(`${registryPath}/training/jobs`, payload),
  calculateScore: (attackRunIds: string[]) =>
    post<RobustnessScore>(`${registryPath}/robustness-score`, {
      attack_run_ids: attackRunIds,
    }),
  verifyBaseline: (baselineId: string) =>
    post<BaselineVerification>(`${registryPath}/baselines/${baselineId}/verify`),
  artifactUrl: (baselineId: string, artifactId: string) =>
    `${registryPath}/baselines/${baselineId}/artifacts/${artifactId}`,
  experimentUrl: (baselineId: string) => `${registryPath}/baselines/${baselineId}/experiment`,
};

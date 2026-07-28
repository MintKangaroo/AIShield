import type {
  AttackRequest,
  AttackRunRecord,
  BaselineRequest,
  BaselineRunRecord,
  BaselineVerification,
  DatasetRecord,
  HealthResponse,
  ModelVersionRecord,
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
  verifyBaseline: (baselineId: string) =>
    post<BaselineVerification>(`${registryPath}/baselines/${baselineId}/verify`),
  artifactUrl: (baselineId: string, artifactId: string) =>
    `${registryPath}/baselines/${baselineId}/artifacts/${artifactId}`,
};

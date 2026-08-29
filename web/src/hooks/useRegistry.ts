import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api";
import { sortByCreatedAt } from "../format";
import type {
  AttackRunRecord,
  BaselineRunRecord,
  DatasetRecord,
  DefenseRunRecord,
  HealthResponse,
  JobRecord,
  JournalEntry,
  ModelVersionRecord,
  TrainingRunRecord,
  TransferRunRecord,
} from "../types";

export type ApiState = "checking" | "ready" | "offline";

export interface RegistryData {
  health: HealthResponse | null;
  datasets: DatasetRecord[];
  models: ModelVersionRecord[];
  baselines: BaselineRunRecord[];
  attacks: AttackRunRecord[];
  defenses: DefenseRunRecord[];
  transfers: TransferRunRecord[];
  training: TrainingRunRecord[];
  jobs: JobRecord[];
  journal: JournalEntry[];
}

const emptyData: RegistryData = {
  health: null,
  datasets: [],
  models: [],
  baselines: [],
  attacks: [],
  defenses: [],
  transfers: [],
  training: [],
  jobs: [],
  journal: [],
};

/** Milliseconds between refreshes while a background job is still queued or running. */
const jobPollIntervalMs = 2500;

export function useRegistry() {
  const [data, setData] = useState<RegistryData>(emptyData);
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [refreshing, setRefreshing] = useState(false);
  // Guards against a poll tick stacking on top of an in-flight refresh.
  const inFlight = useRef(false);

  const refresh = useCallback(async (quiet = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (!quiet) setRefreshing(true);
    try {
      const health = await api.health();
      const [
        datasets,
        models,
        baselines,
        attacks,
        defenses,
        transfers,
        training,
        jobs,
        journal,
      ] = await Promise.all([
        api.datasets(),
        api.models(),
        api.baselines(),
        api.attacks(),
        api.defenses(),
        api.transfers(),
        api.training(),
        api.jobs(),
        api.journal(),
      ]);
      setData({
        health,
        datasets,
        models,
        baselines: sortByCreatedAt(baselines),
        attacks: sortByCreatedAt(attacks),
        defenses: sortByCreatedAt(defenses),
        transfers: sortByCreatedAt(transfers),
        training: sortByCreatedAt(training),
        jobs: sortByCreatedAt(jobs),
        journal,
      });
      setApiState("ready");
    } catch {
      setApiState("offline");
    } finally {
      inFlight.current = false;
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const hasPendingJob = data.jobs.some(
    (job) => job.status === "queued" || job.status === "running",
  );

  useEffect(() => {
    if (!hasPendingJob) return;
    const timer = window.setInterval(() => void refresh(true), jobPollIntervalMs);
    return () => window.clearInterval(timer);
  }, [hasPendingJob, refresh]);

  return { ...data, apiState, hasPendingJob, refresh, refreshing };
}

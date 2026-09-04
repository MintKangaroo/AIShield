import { useEffect, useState } from "react";

import { api } from "./api";
import { clearApiKey, writeApiKey } from "./apiKey";
import { Dialog } from "./components/Dialog";
import { Icon, type IconName } from "./components/Icon";
import { ApiKeyForm } from "./forms/ApiKeyForm";
import { AttackForm } from "./forms/AttackForm";
import { BaselineForm } from "./forms/BaselineForm";
import { DatasetForm } from "./forms/DatasetForm";
import { DefenseForm } from "./forms/DefenseForm";
import { ModelForm } from "./forms/ModelForm";
import { RemoteAttackForm } from "./forms/RemoteAttackForm";
import { TrainingForm } from "./forms/TrainingForm";
import { TransferForm } from "./forms/TransferForm";
import { useRegistry } from "./hooks/useRegistry";
import { ArtifactsPage } from "./pages/ArtifactsPage";
import { AttacksPage } from "./pages/AttacksPage";
import { DefensesPage } from "./pages/DefensesPage";
import { ComparePage } from "./pages/ComparePage";
import { RemoteAttacksPage } from "./pages/RemoteAttacksPage";
import { JobsPage } from "./pages/JobsPage";
import { JournalPage } from "./pages/JournalPage";
import { OverviewPage } from "./pages/OverviewPage";
import { RegistryPage } from "./pages/RegistryPage";
import { RunsPage } from "./pages/RunsPage";
import type {
  AttackRequest,
  AttackRunRecord,
  BaselineRequest,
  BaselineRunRecord,
  BaselineVerification,
  DatasetRecord,
  DefenseRequest,
  JournalReplaySummary,
  RemoteAttackRequest,
  RobustnessScore,
  TrainingRequest,
  TransferRequest,
} from "./types";

type Page =
  | "overview"
  | "runs"
  | "attacks"
  | "defenses"
  | "remote"
  | "jobs"
  | "registry"
  | "artifacts"
  | "compare"
  | "journal";

type DialogName =
  | "baseline"
  | "attack"
  | "dataset"
  | "model"
  | "defense"
  | "transfer"
  | "training"
  | "remote-attack"
  | "api-key"
  | null;

interface Toast {
  tone: "success" | "error";
  message: string;
}

const pageCopy: Record<Page, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: "Mission control",
    title: "Research overview",
    description: "A live view of model evidence, reproducibility, and evaluation health.",
  },
  runs: {
    eyebrow: "Experiment ledger",
    title: "Baseline runs",
    description: "Inspect immutable metrics and verify an exact-configuration rerun.",
  },
  attacks: {
    eyebrow: "Adversarial laboratory",
    title: "Attack evaluations",
    description: "Compare paired clean and robust accuracy under bounded first-order attacks.",
  },
  defenses: {
    eyebrow: "Defense laboratory",
    title: "Defenses & transfer",
    description:
      "Measure a preprocessing defense before, after, and under a defense-aware adaptive attack.",
  },
  remote: {
    eyebrow: "Black-box laboratory",
    title: "Remote model attacks",
    description:
      "Query an authorized deployed classifier with images and read only its scores.",
  },
  jobs: {
    eyebrow: "Execution queue",
    title: "Jobs & training",
    description: "Track bounded background workers and the hardened checkpoints they produce.",
  },
  registry: {
    eyebrow: "Trusted inventory",
    title: "Model & dataset registry",
    description: "Every runtime object is bound to versioned, content-addressed evidence.",
  },
  artifacts: {
    eyebrow: "Evidence vault",
    title: "Generated artifacts",
    description: "Download machine-readable reports and publication-ready matrices.",
  },
  compare: {
    eyebrow: "Run-to-run",
    title: "Compare runs",
    description: "Put two runs side by side, with every disqualifying difference called out.",
  },
  journal: {
    eyebrow: "Durable audit trail",
    title: "Metadata journal",
    description: "Read the append-only record that survives the in-memory registry index.",
  },
};

function App() {
  const {
    apiState,
    attacks,
    baselines,
    datasets,
    defenses,
    hasPendingJob,
    health,
    jobs,
    journal,
    models,
    refresh,
    refreshing,
    remoteAttacks,
    training,
    transfers,
  } = useRegistry();

  const [page, setPage] = useState<Page>("overview");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedAttackId, setSelectedAttackId] = useState<string | null>(null);
  const [selectedDefenseId, setSelectedDefenseId] = useState<string | null>(null);
  const [curveRuns, setCurveRuns] = useState<AttackRunRecord[]>([]);
  const [scoreSelection, setScoreSelection] = useState<ReadonlySet<string>>(new Set());
  const [score, setScore] = useState<RobustnessScore | null>(null);
  const [replaySummary, setReplaySummary] = useState<JournalReplaySummary | null>(null);
  const [dialog, setDialog] = useState<DialogName>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [verifications, setVerifications] = useState<Record<string, BaselineVerification>>({});

  useEffect(() => {
    if (baselines.length && !baselines.some((run) => run.id === selectedId)) {
      setSelectedId(baselines[0].id);
    }
  }, [baselines, selectedId]);

  useEffect(() => {
    if (attacks.length && !attacks.some((attack) => attack.id === selectedAttackId)) {
      setSelectedAttackId(attacks[0].id);
    }
  }, [attacks, selectedAttackId]);

  useEffect(() => {
    if (defenses.length && !defenses.some((defense) => defense.id === selectedDefenseId)) {
      setSelectedDefenseId(defenses[0].id);
    }
  }, [defenses, selectedDefenseId]);

  useEffect(() => {
    // The API answered but refused us: ask for a key instead of reporting an outage.
    if (apiState === "unauthorized") {
      setDialog("api-key");
    }
  }, [apiState]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const selectedRun = baselines.find((run) => run.id === selectedId) ?? baselines[0] ?? null;
  const selectedDataset = datasets.find((item) => item.id === selectedRun?.dataset_id);
  const selectedModel = models.find((item) => item.id === selectedRun?.model_version_id);
  const selectedAttack =
    attacks.find((attack) => attack.id === selectedAttackId) ?? attacks[0] ?? null;
  const attackDataset = datasets.find((item) => item.id === selectedAttack?.dataset_id);
  const attackModel = models.find((item) => item.id === selectedAttack?.model_version_id);
  const selectedDefense =
    defenses.find((defense) => defense.id === selectedDefenseId) ?? defenses[0] ?? null;
  const artifactCount = baselines.reduce((total, run) => total + run.artifacts.length, 0);
  const copy = pageCopy[page];

  async function perform(action: () => Promise<void>, successMessage: string) {
    setBusy(true);
    try {
      await action();
      setToast({ tone: "success", message: successMessage });
      setDialog(null);
    } catch (error) {
      setToast({
        tone: "error",
        message: error instanceof Error ? error.message : "The operation could not be completed.",
      });
    } finally {
      setBusy(false);
    }
  }

  async function createBaseline(payload: BaselineRequest) {
    await perform(async () => {
      const run = await api.runBaseline(payload);
      await refresh(true);
      setSelectedId(run.id);
      setPage("runs");
    }, "Baseline sealed with reproducible evidence.");
  }

  async function createAttack(payload: AttackRequest) {
    await perform(async () => {
      const attack = await api.runAttack(payload);
      await refresh(true);
      setSelectedAttackId(attack.id);
      setPage("attacks");
    }, `${payload.algorithm.toUpperCase()} evaluation completed within the configured bound.`);
  }

  async function createDefense(payload: DefenseRequest) {
    await perform(async () => {
      const defense = await api.runDefense(payload);
      await refresh(true);
      setSelectedDefenseId(defense.id);
      setPage("defenses");
    }, "Defense evaluated before, after, and adaptively.");
  }

  async function createTransfer(payload: TransferRequest) {
    await perform(async () => {
      await api.runTransfer(payload);
      await refresh(true);
      setPage("defenses");
    }, "Black-box transfer evidence recorded.");
  }

  async function createRemoteAttack(payload: RemoteAttackRequest) {
    await perform(async () => {
      await api.runRemoteAttack(payload);
      await refresh(true);
      setPage("remote");
    }, "Black-box attack completed against the remote target.");
  }

  // The remote attack needs a dataset to probe with, but no local model.
  function openRemoteAttackDialog() {
    setDialog(datasets.length ? "remote-attack" : "dataset");
  }

  async function createTraining(payload: TrainingRequest, queued: boolean) {
    await perform(
      async () => {
        if (queued) {
          await api.queueTraining(payload);
        } else {
          await api.runTraining(payload);
        }
        await refresh(true);
        setPage("jobs");
      },
      queued
        ? "Training queued on the bounded background worker."
        : "Training completed and the hardened checkpoint was hashed.",
    );
  }

  async function createCurve() {
    if (!attackModel || !attackDataset) return;
    await perform(async () => {
      const runs = await api.runAttackCurve({
        model_version_id: attackModel.id,
        dataset_id: attackDataset.id,
        algorithm: "pgd",
        epsilons: [2 / 255, 4 / 255, 8 / 255, 16 / 255],
        step_fraction: 0.25,
        iterations: 5,
        restarts: 1,
        seed: 1729,
        batch_size: 64,
        max_samples: 256,
      });
      setCurveRuns(runs);
      await refresh(true);
    }, "Attack strength curve completed.");
  }

  async function submitApiKey(key: string) {
    writeApiKey(key);
    setDialog(null);
    await refresh();
  }

  async function exportExperiment(baselineId: string) {
    await perform(
      () => api.downloadExperiment(baselineId),
      "Experiment envelope downloaded.",
    );
  }

  async function downloadArtifact(
    baselineId: string,
    artifactId: string,
    filename: string,
  ) {
    await perform(
      () => api.downloadArtifact(baselineId, artifactId, filename),
      "Artifact downloaded.",
    );
  }

  async function replayJournal() {
    await perform(async () => {
      const summary = await api.replayJournal();
      setReplaySummary(summary);
      await refresh(true);
    }, "Journal replayed into the in-memory index.");
  }

  async function calculateScore() {
    const ids = [...scoreSelection];
    await perform(async () => {
      setScore(await api.calculateScore(ids));
    }, `Robustness score aggregated from ${ids.length} attack runs.`);
  }

  function toggleScoreSelection(id: string) {
    setScoreSelection((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function loadDataset(payload: {
    name: DatasetRecord["name"];
    split: DatasetRecord["split"];
    download: boolean;
  }) {
    await perform(async () => {
      await api.loadDataset(payload);
      await refresh(true);
      setPage("registry");
    }, `${payload.name.toUpperCase()} ${payload.split} split loaded.`);
  }

  async function loadModel(payload: { dataset_id: string; seed: number }) {
    await perform(async () => {
      await api.loadSmallCnn(payload);
      await refresh(true);
      setPage("registry");
    }, "Content-addressed SmallCNN model created.");
  }

  async function startDemo() {
    await perform(async () => {
      let dataset = datasets.find((item) => item.name === "synthetic" && item.split === "test");
      if (!dataset) {
        dataset = await api.loadDataset({ name: "synthetic", split: "test", download: false });
      }
      let model = models.find(
        (item) =>
          item.source === "small_cnn" &&
          item.input_channels === dataset.input_shape[0] &&
          item.num_classes === dataset.num_classes,
      );
      if (!model) {
        model = await api.loadSmallCnn({ dataset_id: dataset.id, seed: 1729 });
      }
      const run = await api.runBaseline({
        model_version_id: model.id,
        dataset_id: dataset.id,
        seed: 1729,
        batch_size: 64,
        max_samples: 256,
        warmup_batches: 1,
      });
      const attack = await api.runAttack({
        model_version_id: model.id,
        dataset_id: dataset.id,
        algorithm: "fgsm",
        epsilon: 8 / 255,
        seed: 1729,
        batch_size: 64,
        max_samples: 256,
      });
      await refresh(true);
      setSelectedId(run.id);
      setSelectedAttackId(attack.id);
    }, "Local demo completed. No network download was used.");
  }

  async function verify(run: BaselineRunRecord) {
    await perform(async () => {
      const result = await api.verifyBaseline(run.id);
      setVerifications((current) => ({ ...current, [run.id]: result }));
      await refresh(true);
      setSelectedId(run.id);
    }, "Exact-configuration rerun matched the reference evidence.");
  }

  /** Send the user to whichever prerequisite is still missing before the real dialog. */
  function openWithPrerequisites(target: DialogName) {
    if (!datasets.length) {
      setDialog("dataset");
    } else if (!models.length) {
      setDialog("model");
    } else {
      setDialog(target);
    }
  }

  const navItems: Array<{ id: Page; label: string; icon: IconName; count?: number }> = [
    { id: "overview", label: "Overview", icon: "grid" },
    { id: "runs", label: "Baseline runs", icon: "activity", count: baselines.length },
    { id: "attacks", label: "Attack lab", icon: "spark", count: attacks.length },
    {
      id: "defenses",
      label: "Defense lab",
      icon: "shield",
      count: defenses.length + transfers.length,
    },
    { id: "remote", label: "Remote attacks", icon: "transfer", count: remoteAttacks.length },
    { id: "jobs", label: "Jobs & training", icon: "clock", count: jobs.length },
    { id: "registry", label: "Registry", icon: "database", count: datasets.length + models.length },
    { id: "artifacts", label: "Artifacts", icon: "archive", count: artifactCount },
    { id: "compare", label: "Compare", icon: "activity" },
    { id: "journal", label: "Journal", icon: "book", count: journal.length },
  ];

  const primaryAction: Record<string, { label: string; run: () => void }> = {
    attacks: { label: "New attack", run: () => openWithPrerequisites("attack") },
    defenses: { label: "New defense", run: () => openWithPrerequisites("defense") },
    remote: { label: "New black-box attack", run: openRemoteAttackDialog },
    jobs: { label: "Queue training", run: () => openWithPrerequisites("training") },
  };
  const action = primaryAction[page] ?? {
    label: "New baseline",
    run: () => openWithPrerequisites("baseline"),
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" type="button" onClick={() => setPage("overview")}>
          <span className="brand-mark">
            <Icon name="shield" size={22} />
          </span>
          <span className="brand-copy">
            <strong>AIShield</strong>
            <small>Research console</small>
          </span>
        </button>

        <div className="workspace-switcher">
          <span className="workspace-avatar">AS</span>
          <span>
            <small>Workspace</small>
            <b>AI Security Lab</b>
          </span>
          <Icon name="chevron" size={14} />
        </div>

        <nav aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {navItems.map((item) => (
            <button
              className={`nav-item ${page === item.id ? "active" : ""}`}
              key={item.id}
              type="button"
              onClick={() => setPage(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.count !== undefined && <b>{item.count}</b>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="integrity-card">
            <span className="integrity-icon">
              <Icon name="fingerprint" />
            </span>
            <div>
              <strong>Evidence-first</strong>
              <p>Hashes, seeds, environment and raw metrics stay attached.</p>
            </div>
          </div>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            <Icon name="terminal" size={15} />
            API documentation
            <Icon name="arrow" size={14} />
          </a>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <span className="kicker">{copy.eyebrow}</span>
            <h1>{copy.title}</h1>
            <p>{copy.description}</p>
          </div>
          <div className="top-actions">
            <span className={`api-status ${apiState}`}>
              <i />
              {apiState === "ready"
                ? `API ${health?.version} · ${health?.compute_device.toUpperCase()}`
                : apiState === "checking"
                  ? "Connecting"
                  : apiState === "unauthorized"
                    ? "API key required"
                    : "API offline"}
            </span>
            <button
              aria-label="Refresh workspace"
              className={`icon-button ${refreshing ? "spinning" : ""}`}
              type="button"
              onClick={() => void refresh()}
            >
              <Icon name="refresh" />
            </button>
            <button className="button primary compact" type="button" onClick={action.run}>
              <Icon name="plus" size={16} />
              {action.label}
            </button>
          </div>
        </header>

        {apiState === "unauthorized" && (
          <div className="offline-banner unauthorized">
            <Icon name="shield" />
            <span>
              <strong>This deployment requires an API key.</strong> The server answered but
              refused the request.
            </span>
            <button type="button" onClick={() => setDialog("api-key")}>
              Enter key
            </button>
          </div>
        )}

        {apiState === "offline" && (
          <div className="offline-banner">
            <Icon name="server" />
            <span>
              <strong>The API is offline.</strong> Start <code>aishield-api</code> or the Docker
              stack, then refresh this workspace.
            </span>
            <button type="button" onClick={() => void refresh()}>
              Retry connection
            </button>
          </div>
        )}

        {page === "overview" && (
          <OverviewPage
            apiState={apiState}
            artifactCount={artifactCount}
            baselines={baselines}
            busy={busy}
            datasets={datasets}
            models={models}
            selectedAttack={selectedAttack}
            selectedDataset={selectedDataset}
            selectedRun={selectedRun}
            verification={selectedRun ? verifications[selectedRun.id] : undefined}
            onOpenAttack={() => openWithPrerequisites("attack")}
            onOpenBaseline={() => openWithPrerequisites("baseline")}
            onSelectRun={(id) => {
              setSelectedId(id);
              setPage("runs");
            }}
            onStartDemo={() => void startDemo()}
            onViewAllRuns={() => setPage("runs")}
          />
        )}

        {page === "runs" && (
          <RunsPage
            baselines={baselines}
            busy={busy}
            datasets={datasets}
            models={models}
            selectedDataset={selectedDataset}
            selectedModel={selectedModel}
            selectedRun={selectedRun}
            verification={selectedRun ? verifications[selectedRun.id] : undefined}
            onExport={exportExperiment}
            onOpenBaseline={() => openWithPrerequisites("baseline")}
            onSelectRun={setSelectedId}
            onVerify={(run) => void verify(run)}
          />
        )}

        {page === "attacks" && (
          <AttacksPage
            attackDataset={attackDataset}
            attackModel={attackModel}
            attacks={attacks}
            busy={busy}
            curveRuns={curveRuns}
            datasets={datasets}
            models={models}
            score={score}
            scoreSelection={scoreSelection}
            selectedAttack={selectedAttack}
            onCalculateScore={() => void calculateScore()}
            onOpenAttack={() => openWithPrerequisites("attack")}
            onRunCurve={() => void createCurve()}
            onSelectAttack={setSelectedAttackId}
            onToggleScore={toggleScoreSelection}
          />
        )}

        {page === "defenses" && (
          <DefensesPage
            datasets={datasets}
            defenses={defenses}
            models={models}
            selectedDefense={selectedDefense}
            transfers={transfers}
            onOpenDefense={() => openWithPrerequisites("defense")}
            onOpenTransfer={() => openWithPrerequisites("transfer")}
            onSelectDefense={setSelectedDefenseId}
          />
        )}

        {page === "remote" && (
          <RemoteAttacksPage
            datasets={datasets}
            runs={remoteAttacks}
            onOpenRemoteAttack={openRemoteAttackDialog}
          />
        )}

        {page === "jobs" && (
          <JobsPage
            hasPendingJob={hasPendingJob}
            jobs={jobs}
            models={models}
            training={training}
            onOpenTraining={() => openWithPrerequisites("training")}
          />
        )}

        {page === "registry" && (
          <RegistryPage
            datasets={datasets}
            models={models}
            onOpenDataset={() => setDialog("dataset")}
            onOpenModel={() => setDialog("model")}
          />
        )}

        {page === "artifacts" && (
          <ArtifactsPage
            artifactCount={artifactCount}
            baselines={baselines}
            onDownload={downloadArtifact}
          />
        )}

        {page === "compare" && (
          <ComparePage
            attacks={attacks}
            baselines={baselines}
            datasets={datasets}
            models={models}
          />
        )}

        {page === "journal" && (
          <JournalPage
            busy={busy}
            entries={journal}
            summary={replaySummary}
            onReplay={() => void replayJournal()}
          />
        )}
      </main>

      {dialog === "baseline" && (
        <Dialog
          title="Run a clean baseline"
          description="Measure unperturbed model behavior and seal the complete evidence record."
          onClose={() => setDialog(null)}
        >
          <BaselineForm
            busy={busy}
            datasets={datasets}
            models={models}
            onCancel={() => setDialog(null)}
            onSubmit={createBaseline}
          />
        </Dialog>
      )}
      {dialog === "attack" && (
        <Dialog
          title="Run a bounded attack"
          description="Generate adversarial inputs and compare paired clean and robust metrics."
          onClose={() => setDialog(null)}
        >
          <AttackForm
            busy={busy}
            datasets={datasets}
            models={models}
            onCancel={() => setDialog(null)}
            onSubmit={createAttack}
          />
        </Dialog>
      )}
      {dialog === "defense" && (
        <Dialog
          title="Evaluate a preprocessing defense"
          description="Compare one sample population before the defense, after it, and under an adaptive attack."
          onClose={() => setDialog(null)}
        >
          <DefenseForm
            busy={busy}
            datasets={datasets}
            models={models}
            onCancel={() => setDialog(null)}
            onSubmit={createDefense}
          />
        </Dialog>
      )}
      {dialog === "remote-attack" && (
        <Dialog
          kicker="Authorized target"
          title="Attack a remote model"
          description="Query-only black-box attack against a classifier you are authorized to test."
          onClose={() => setDialog(null)}
        >
          <RemoteAttackForm
            busy={busy}
            datasets={datasets}
            onCancel={() => setDialog(null)}
            onSubmit={createRemoteAttack}
          />
        </Dialog>
      )}
      {dialog === "transfer" && (
        <Dialog
          title="Run a black-box transfer attack"
          description="Craft perturbations on a surrogate model and measure them against a different target."
          onClose={() => setDialog(null)}
        >
          <TransferForm
            busy={busy}
            datasets={datasets}
            models={models}
            onCancel={() => setDialog(null)}
            onSubmit={createTransfer}
          />
        </Dialog>
      )}
      {dialog === "training" && (
        <Dialog
          title="Train a hardened model"
          description="Copy a registered model and train it with bounded adversarial examples or TRADES."
          onClose={() => setDialog(null)}
        >
          <TrainingForm
            busy={busy}
            datasets={datasets}
            models={models}
            onCancel={() => setDialog(null)}
            onSubmit={createTraining}
          />
        </Dialog>
      )}
      {dialog === "api-key" && (
        <Dialog
          kicker="Access"
          title="Enter the API key"
          description="This deployment protects the registry. The key is kept for this browser tab only."
          onClose={() => setDialog(null)}
        >
          <ApiKeyForm
            busy={busy}
            onCancel={() => setDialog(null)}
            onClear={() => {
              clearApiKey();
              void refresh();
            }}
            onSubmit={submitApiKey}
          />
        </Dialog>
      )}
      {dialog === "dataset" && (
        <Dialog
          title="Load a dataset split"
          description="Use generated data locally or an explicitly approved public adapter."
          onClose={() => setDialog(null)}
        >
          <DatasetForm busy={busy} onCancel={() => setDialog(null)} onSubmit={loadDataset} />
        </Dialog>
      )}
      {dialog === "model" && (
        <Dialog
          title="Create a model version"
          description="Initialize a dataset-compatible model and bind it to content hashes."
          onClose={() => setDialog(null)}
        >
          <ModelForm
            busy={busy}
            datasets={datasets}
            onCancel={() => setDialog(null)}
            onSubmit={loadModel}
          />
        </Dialog>
      )}

      {toast && (
        <div className={`toast ${toast.tone}`} role="status">
          <span>
            <Icon name={toast.tone === "success" ? "check" : "close"} size={15} />
          </span>
          {toast.message}
          <button aria-label="Dismiss notification" type="button" onClick={() => setToast(null)}>
            <Icon name="close" size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

export default App;

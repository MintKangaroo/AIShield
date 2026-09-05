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
import { LlmRedTeamForm } from "./forms/LlmRedTeamForm";
import { RemoteAttackForm } from "./forms/RemoteAttackForm";
import { TrainingForm } from "./forms/TrainingForm";
import { TransferForm } from "./forms/TransferForm";
import { useRegistry } from "./hooks/useRegistry";
import { ArtifactsPage } from "./pages/ArtifactsPage";
import { AttacksPage } from "./pages/AttacksPage";
import { DefensesPage } from "./pages/DefensesPage";
import { ComparePage } from "./pages/ComparePage";
import { LlmRedTeamPage } from "./pages/LlmRedTeamPage";
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
  ArtifactGcReport,
  DefenseRequest,
  JournalReplaySummary,
  LlmRedTeamRequest,
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
  | "llm"
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
  | "llm-red-team"
  | "api-key"
  | null;

interface Toast {
  tone: "success" | "error";
  message: string;
}

const pageCopy: Record<Page, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: "미션 컨트롤",
    title: "연구 개요",
    description: "모델 증거·재현성·평가 상태를 실시간으로 봅니다.",
  },
  runs: {
    eyebrow: "실험 원장",
    title: "베이스라인 실행",
    description: "불변 지표를 확인하고 동일 구성 재실행을 검증합니다.",
  },
  attacks: {
    eyebrow: "적대적 실험실",
    title: "공격 평가",
    description: "경계가 있는 1차 공격에서 clean·robust 정확도를 짝지어 비교합니다.",
  },
  defenses: {
    eyebrow: "방어 실험실",
    title: "방어 & 전이",
    description:
      "전처리 방어를 적용 전·후, 그리고 방어 인지 적응 공격 하에서 측정합니다.",
  },
  remote: {
    eyebrow: "블랙박스 실험실",
    title: "원격 모델 공격",
    description:
      "인가된 배포 분류기에 이미지를 질의하고 score만 읽습니다.",
  },
  llm: {
    eyebrow: "LLM 실험실",
    title: "LLM 레드팀",
    description:
      "인가된 LLM을 prompt-injection·명령 override·jailbreak 프레이밍으로 점검합니다.",
  },
  jobs: {
    eyebrow: "실행 큐",
    title: "작업 & 학습",
    description: "경계가 있는 백그라운드 워커와 그 결과인 강화 체크포인트를 추적합니다.",
  },
  registry: {
    eyebrow: "신뢰 인벤토리",
    title: "모델 & 데이터셋 레지스트리",
    description: "모든 런타임 객체는 버전이 매겨진 콘텐츠 주소 증거에 묶입니다.",
  },
  artifacts: {
    eyebrow: "증거 보관소",
    title: "생성된 아티팩트",
    description: "기계 판독 리포트와 출판용 행렬을 내려받습니다.",
  },
  compare: {
    eyebrow: "실행 간 비교",
    title: "실행 비교",
    description: "두 실행을 나란히 놓고, 비교를 무효화하는 차이를 모두 짚어줍니다.",
  },
  journal: {
    eyebrow: "영속 감사 로그",
    title: "메타데이터 저널",
    description: "메모리 레지스트리 인덱스보다 오래 남는 append-only 기록을 봅니다.",
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
    llmRedTeams,
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
  const [gcReport, setGcReport] = useState<ArtifactGcReport | null>(null);
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
        message: error instanceof Error ? error.message : "작업을 완료할 수 없습니다.",
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
    }, "베이스라인이 재현 가능한 증거와 함께 봉인되었습니다.");
  }

  async function createAttack(payload: AttackRequest) {
    await perform(async () => {
      const attack = await api.runAttack(payload);
      await refresh(true);
      setSelectedAttackId(attack.id);
      setPage("attacks");
    }, `${payload.algorithm.toUpperCase()} 평가가 설정된 경계 안에서 완료되었습니다.`);
  }

  async function createDefense(payload: DefenseRequest) {
    await perform(async () => {
      const defense = await api.runDefense(payload);
      await refresh(true);
      setSelectedDefenseId(defense.id);
      setPage("defenses");
    }, "방어를 적용 전·후, 그리고 적응 공격 하에서 평가했습니다.");
  }

  async function createTransfer(payload: TransferRequest) {
    await perform(async () => {
      await api.runTransfer(payload);
      await refresh(true);
      setPage("defenses");
    }, "블랙박스 전이 증거를 기록했습니다.");
  }

  async function createRemoteAttack(payload: RemoteAttackRequest) {
    await perform(async () => {
      await api.runRemoteAttack(payload);
      await refresh(true);
      setPage("remote");
    }, "원격 대상에 대한 블랙박스 공격을 완료했습니다.");
  }

  // The remote attack needs a dataset to probe with, but no local model.
  function openRemoteAttackDialog() {
    setDialog(datasets.length ? "remote-attack" : "dataset");
  }

  async function createLlmRedTeam(payload: LlmRedTeamRequest) {
    await perform(async () => {
      await api.runLlmRedTeam(payload);
      await refresh(true);
      setPage("llm");
    }, "LLM 레드팀을 완료했습니다.");
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
        ? "경계가 있는 백그라운드 워커에 학습을 큐잉했습니다."
        : "학습을 완료하고 강화 체크포인트를 해시했습니다.",
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
    }, "공격 강도 곡선을 완료했습니다.");
  }

  async function submitApiKey(key: string) {
    writeApiKey(key);
    setDialog(null);
    await refresh();
  }

  async function exportExperiment(baselineId: string) {
    await perform(
      () => api.downloadExperiment(baselineId),
      "실험 envelope을 내려받았습니다.",
    );
  }

  async function downloadArtifact(
    baselineId: string,
    artifactId: string,
    filename: string,
  ) {
    await perform(
      () => api.downloadArtifact(baselineId, artifactId, filename),
      "아티팩트를 내려받았습니다.",
    );
  }

  async function collectGarbage(dryRun: boolean) {
    await perform(async () => {
      setGcReport(await api.collectArtifactGarbage(dryRun));
      if (!dryRun) await refresh(true);
    }, dryRun ? "정리 미리보기를 계산했습니다." : "아티팩트를 정리했습니다.");
  }

  async function replayJournal() {
    await perform(async () => {
      const summary = await api.replayJournal();
      setReplaySummary(summary);
      await refresh(true);
    }, "저널을 메모리 인덱스로 재생했습니다.");
  }

  async function calculateScore() {
    const ids = [...scoreSelection];
    await perform(async () => {
      setScore(await api.calculateScore(ids));
    }, `공격 실행 ${ids.length}건에서 강건성 점수를 집계했습니다.`);
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
    }, `${payload.name.toUpperCase()} ${payload.split} split을 적재했습니다.`);
  }

  async function loadModel(payload: { dataset_id: string; seed: number }) {
    await perform(async () => {
      await api.loadSmallCnn(payload);
      await refresh(true);
      setPage("registry");
    }, "콘텐츠 주소 기반 SmallCNN 모델을 생성했습니다.");
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
    }, "로컬 데모를 완료했습니다. 네트워크 다운로드는 없었습니다.");
  }

  async function verify(run: BaselineRunRecord) {
    await perform(async () => {
      const result = await api.verifyBaseline(run.id);
      setVerifications((current) => ({ ...current, [run.id]: result }));
      await refresh(true);
      setSelectedId(run.id);
    }, "동일 구성 재실행이 기준 증거와 일치했습니다.");
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
    { id: "overview", label: "개요", icon: "grid" },
    { id: "runs", label: "베이스라인 실행", icon: "activity", count: baselines.length },
    { id: "attacks", label: "공격 랩", icon: "spark", count: attacks.length },
    {
      id: "defenses",
      label: "방어 랩",
      icon: "shield",
      count: defenses.length + transfers.length,
    },
    { id: "remote", label: "원격 공격", icon: "transfer", count: remoteAttacks.length },
    { id: "llm", label: "LLM 레드팀", icon: "terminal", count: llmRedTeams.length },
    { id: "jobs", label: "작업 & 학습", icon: "clock", count: jobs.length },
    { id: "registry", label: "레지스트리", icon: "database", count: datasets.length + models.length },
    { id: "artifacts", label: "아티팩트", icon: "archive", count: artifactCount },
    { id: "compare", label: "비교", icon: "activity" },
    { id: "journal", label: "저널", icon: "book", count: journal.length },
  ];

  const primaryAction: Record<string, { label: string; run: () => void }> = {
    attacks: { label: "새 공격", run: () => openWithPrerequisites("attack") },
    defenses: { label: "새 방어", run: () => openWithPrerequisites("defense") },
    remote: { label: "새 블랙박스 공격", run: openRemoteAttackDialog },
    llm: { label: "새 LLM 레드팀", run: () => setDialog("llm-red-team") },
    jobs: { label: "학습 큐잉", run: () => openWithPrerequisites("training") },
  };
  const action = primaryAction[page] ?? {
    label: "새 베이스라인",
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
            <small>연구 콘솔</small>
          </span>
        </button>

        <div className="workspace-switcher">
          <span className="workspace-avatar">AS</span>
          <span>
            <small>워크스페이스</small>
            <b>AI Security Lab</b>
          </span>
          <Icon name="chevron" size={14} />
        </div>

        <nav aria-label="Primary navigation">
          <span className="nav-label">워크스페이스</span>
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
              <strong>증거 우선</strong>
              <p>해시·시드·환경·원본 지표가 항상 함께 남습니다.</p>
            </div>
          </div>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            <Icon name="terminal" size={15} />
            API 문서
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
                  ? "연결 중"
                  : apiState === "unauthorized"
                    ? "API 키 필요"
                    : "API 오프라인"}
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
              <strong>이 배포는 API 키가 필요합니다.</strong> 서버는 응답했지만 요청을 거부했습니다.
            </span>
            <button type="button" onClick={() => setDialog("api-key")}>
              키 입력
            </button>
          </div>
        )}

        {apiState === "offline" && (
          <div className="offline-banner">
            <Icon name="server" />
            <span>
              <strong>API가 오프라인입니다.</strong> <code>aishield-api</code> 또는 Docker 스택을 시작한 뒤 이 워크스페이스를 새로고침하세요.
            </span>
            <button type="button" onClick={() => void refresh()}>
              다시 연결
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

        {page === "llm" && (
          <LlmRedTeamPage
            runs={llmRedTeams}
            onOpenLlmRedTeam={() => setDialog("llm-red-team")}
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
            gcReport={gcReport}
            summary={replaySummary}
            onCollectGarbage={(dryRun) => void collectGarbage(dryRun)}
            onReplay={() => void replayJournal()}
          />
        )}
      </main>

      {dialog === "baseline" && (
        <Dialog
          title="clean 베이스라인 실행"
          description="변형 없는 모델 동작을 측정하고 전체 증거 기록을 봉인합니다."
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
          title="경계 공격 실행"
          description="적대적 입력을 생성하고 clean·robust 지표를 짝지어 비교합니다."
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
          title="전처리 방어 평가"
          description="같은 샘플 집단을 방어 전·후, 그리고 적응 공격 하에서 비교합니다."
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
          kicker="인가된 대상"
          title="원격 모델 공격"
          description="인가된 분류기에 대한 질의 전용 블랙박스 공격."
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
      {dialog === "llm-red-team" && (
        <Dialog
          kicker="인가된 대상"
          title="LLM 레드팀"
          description="인가된 LLM에 대한 질의 전용 prompt-injection 점검."
          onClose={() => setDialog(null)}
        >
          <LlmRedTeamForm
            busy={busy}
            onCancel={() => setDialog(null)}
            onSubmit={createLlmRedTeam}
          />
        </Dialog>
      )}
      {dialog === "transfer" && (
        <Dialog
          title="블랙박스 전이 공격 실행"
          description="대리 모델에서 섭동을 만들어 다른 대상에 대해 측정합니다."
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
          title="강화 모델 학습"
          description="등록된 모델을 복제해 경계 적대 예제 또는 TRADES로 학습합니다."
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
          kicker="접근"
          title="API 키 입력"
          description="이 배포는 레지스트리를 보호합니다. 키는 이 브라우저 탭에만 보관됩니다."
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
          title="데이터셋 split 적재"
          description="로컬 생성 데이터 또는 명시적으로 승인된 공개 어댑터를 사용합니다."
          onClose={() => setDialog(null)}
        >
          <DatasetForm busy={busy} onCancel={() => setDialog(null)} onSubmit={loadDataset} />
        </Dialog>
      )}
      {dialog === "model" && (
        <Dialog
          title="모델 버전 생성"
          description="데이터셋 호환 모델을 초기화하고 콘텐츠 해시에 묶습니다."
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
